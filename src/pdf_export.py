"""
src/pdf_export.py — Génération PDF du rapport TPFREP et d'une synthèse KPI.

Deux types de PDF :
  1. `convert_report_to_pdf` : conversion fidèle du TPFREP_FINAL.xlsx déjà
     généré (mise en forme, mise en page) via LibreOffice headless —
     même outil déjà utilisé dans app.py pour la conversion .xls -> .xlsx,
     réutilisé ici sans rien dupliquer côté logique métier.
  2. `generate_kpi_summary_pdf` : une page de synthèse KPI lisible
     (indicateurs clés), construite à partir du même KPIResult que le
     dashboard Excel et le dashboard BI Streamlit — aucun recalcul.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from src.calculations import KPIResult
from src.logger import get_logger
from src.merge import MergedVesselDataset

logger = get_logger("pdf_export")


class PDFExportError(RuntimeError):
    """Levée quand la conversion ou la génération PDF échoue."""


def convert_report_to_pdf(xlsx_path: Path, output_dir: Path, timeout: int = 120) -> Path:
    """Convertit un classeur Excel (TPFREP_FINAL.xlsx) en PDF via
    LibreOffice headless, en conservant fidèlement la mise en page du
    modèle officiel. Retourne le chemin du PDF généré."""
    import shutil
    xlsx_path = Path(xlsx_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not xlsx_path.exists():
        raise PDFExportError(f"Fichier source introuvable pour conversion PDF : {xlsx_path}")

    # Rechercher l'exécutable
    exe = None
    for candidate in ["libreoffice", "soffice"]:
        if shutil.which(candidate):
            exe = candidate
            break

    if not exe:
        raise FileNotFoundError(
            "Aucune installation de LibreOffice (libreoffice / soffice) n'a été détectée dans le PATH. "
            "La génération du PDF est ignorée de manière non bloquante."
        )

    result = subprocess.run(
        [
            exe, "--headless", "--norestore",
            "--convert-to", "pdf", "--outdir", str(output_dir), str(xlsx_path),
        ],
        capture_output=True, text=True, timeout=timeout,
    )
    pdf_path = output_dir / (xlsx_path.stem + ".pdf")
    if result.returncode != 0 or not pdf_path.exists():
        raise PDFExportError(
            f"Échec de la conversion PDF pour {xlsx_path.name} : "
            f"{result.stderr or result.stdout}"
        )
    logger.info("PDF généré : %s", pdf_path)
    return pdf_path


def generate_kpi_summary_pdf(
    merged: MergedVesselDataset,
    kpi: KPIResult,
    output_path: Path,
    vessel_name: str = "",
) -> Path:
    """Génère un PDF de synthèse KPI (une page) à partir du KPIResult déjà
    calculé par compute_all_kpis() — aucun recalcul, lecture seule."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise PDFExportError(
            "Le paquet 'reportlab' est requis pour la synthèse PDF "
            "(pip install reportlab). Voir requirements.txt."
        ) from exc

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(output_path), pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    def line(text: str, size: int = 11, bold: bool = False, gap: float = 0.7 * cm):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(2 * cm, y, text)
        y -= gap

    line(f"Synthèse KPI — {vessel_name or 'Navire'}", size=16, bold=True, gap=1.1 * cm)
    line("Terminal SOMAPORT — Port de Casablanca", size=10, gap=1.0 * cm)

    line("Indicateurs clés", size=13, bold=True)
    line(f"Total conteneurs (import + export) : {kpi.total_containers}")
    line(f"Total conteneurs Import : {kpi.total_import_containers}")
    line(f"Total conteneurs Export : {kpi.total_export_containers}")
    line(f"Full / Empty Import : {kpi.full_import} / {kpi.empty_import}")
    line(f"Full / Empty Export : {kpi.full_export} / {kpi.empty_export}")
    line(f"Conteneurs dangereux : {kpi.dangerous_import + kpi.dangerous_export}")
    line(f"Conteneurs reefer : {kpi.reefer_import + kpi.reefer_export}")
    line(
        f"Cohérence grues/conteneurs : "
        f"{'OK' if kpi.cross_check_matches else 'ÉCART DÉTECTÉ'} "
        f"({kpi.cross_check_crane_moves_total} vs {kpi.cross_check_container_records_total})",
        gap=1.1 * cm,
    )

    if kpi.crane_productivity:
        line("Productivité grues", size=13, bold=True)
        for crane_id, prod in sorted(kpi.crane_productivity.items()):
            line(
                f"  {crane_id} — {prod.sessions} session(s), "
                f"{prod.total_moves} mouvements, "
                f"{prod.total_working_hours:.2f} h, "
                f"{prod.gross_moves_per_hour or 0:.2f} mouv./h"
            )
        y -= 0.4 * cm

    if kpi.operator_discharged or kpi.operator_loaded:
        line("Opérateurs", size=13, bold=True)

        def _op_total(vals: dict) -> int:
            return sum(vals.get(k, 0) for k in ("full_20", "full_40", "empty_20", "empty_40"))

        for op, vals in kpi.operator_discharged.items():
            line(f"  {op} (déchargé) — total : {_op_total(vals)}")
        for op, vals in kpi.operator_loaded.items():
            line(f"  {op} (chargé) — total : {_op_total(vals)}")

    c.showPage()
    c.save()
    logger.info("Synthèse PDF générée : %s", output_path)
    return output_path
