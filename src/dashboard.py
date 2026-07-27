"""
src/dashboard.py — Génère un classeur Excel de bord (DASHBOARD.xlsx) stylisé SOMAPORT avec :
- Logo SOMAPORT en haut à gauche
- Bandeau de titre vert positionné sous le logo et centré au-dessus du tableau
- Police agrandie et mise en gras pour les données du tableau
"""

from __future__ import annotations

from pathlib import Path
import xlsxwriter

import config
from src.calculations import KPIResult
from src.logger import get_logger
from src.merge import MergedVesselDataset

logger = get_logger("dashboard")


def setup_sheet_header(ws, workbook, title: str, end_col: int = 4):
    """Met en place le logo SOMAPORT en haut et le bandeau de titre au-dessous, centré au-dessus du tableau."""
    # Définition des hauteurs de lignes pour l'en-tête
    ws.set_row(0, 10)
    ws.set_row(1, 20)
    ws.set_row(2, 20)
    ws.set_row(3, 10)
    ws.set_row(4, 22)
    ws.set_row(5, 22)
    ws.set_row(6, 12)

    # Insertion du logo
    _LOGO_PATH = Path(config.BASE_DIR) / "assets" / "somaport_logo.png"
    if _LOGO_PATH.exists():
        ws.insert_image('A2', str(_LOGO_PATH), {
            'x_scale': 0.26,
            'y_scale': 0.26,
            'positioning': 1
        })
    
    # Bandeau de titre vert SOMAPORT sous le logo, fusionné sur la largeur du tableau
    title_bar_format = workbook.add_format({
        'bold': True,
        'font_size': 13,
        'font_name': 'Onest',
        'bg_color': '#8BB346',      # Vert SOMAPORT
        'font_color': '#FFFFFF',    # Texte Blanc
        'align': 'center',
        'valign': 'vcenter',
        'border': 1,
        'border_color': '#7AA336'
    })
    
    # Fusion des cellules A5 à (end_col)6
    ws.merge_range(4, 0, 5, max(1, end_col), title, title_bar_format)


def _write_table(ws, start_row: int, start_col: int, headers: list, rows: list,
                  header_format, formats_dict: dict) -> int:
    """Écrit un tableau simple avec en-têtes et police agrandie/en gras."""
    ws.set_row(start_row, 26)
    for j, h in enumerate(headers):
        ws.write(start_row, start_col + j, h, header_format)
        
    for i, row in enumerate(rows):
        current_row = start_row + 1 + i
        ws.set_row(current_row, 22)
        for j, value in enumerate(row):
            # Choisir l'alignement (toutes les cellules sont agrandies et en gras)
            if isinstance(value, (int, float)):
                fmt = formats_dict["cell_right"]
            elif isinstance(value, str) and (value.startswith("2026-") or value in ("OK", "ÉCART", "SUCCESS", "FAILED")):
                fmt = formats_dict["cell_center"]
            else:
                fmt = formats_dict["cell"]
            ws.write(current_row, start_col + j, value, fmt)
            
    return start_row + 1 + len(rows) + 1  # Ligne suivante disponible


def build_kpi_sheet(workbook, merged: MergedVesselDataset, kpi: KPIResult, formats: dict):
    ws = workbook.add_worksheet("KPIs")
    ws.set_column(0, 0, 42)
    ws.set_column(1, 1, 20)

    # Titre au-dessous du logo et centré au-dessus du tableau (colonnes A à B)
    setup_sheet_header(ws, workbook, f"Indicateurs clés — {merged.vessel_name}", end_col=1)

    rows = [
        ("Total conteneurs (import + export)", kpi.total_containers),
        ("Total conteneurs Import", kpi.total_import_containers),
        ("Total conteneurs Export", kpi.total_export_containers),
        ("Full Import", kpi.full_import),
        ("Empty Import", kpi.empty_import),
        ("Full Export", kpi.full_export),
        ("Empty Export", kpi.empty_export),
    ]
    
    next_row = _write_table(ws, 7, 0, ["Indicateur", "Valeur"], rows, formats["header"], formats)

    if kpi.entry_time_min is not None and kpi.entry_time_max is not None:
        ws.set_row(next_row, 22)
        ws.write(next_row, 0, "Première saisie", formats["cell"])
        ws.write(next_row, 1, str(kpi.entry_time_min), formats["cell_center"])
        ws.set_row(next_row + 1, 22)
        ws.write(next_row + 1, 0, "Dernière saisie", formats["cell"])
        ws.write(next_row + 1, 1, str(kpi.entry_time_max), formats["cell_center"])


def build_operator_sheet(workbook, kpi: KPIResult, formats: dict):
    ws = workbook.add_worksheet("Par Operateur")
    ws.set_column(0, 0, 18)
    ws.set_column(1, 5, 14)

    setup_sheet_header(ws, workbook, "Statistiques par Opérateur", end_col=5)

    ws.set_row(7, 24)
    ws.write(7, 0, "Conteneurs déchargés (Import) par opérateur", formats["section"])
    headers = ["Opérateur", "Full 20'", "Full 40'+", "Empty 20'", "Empty 40'+", "Total"]
    disc_rows = []
    for op, counts in sorted(kpi.operator_discharged.items()):
        total = sum(counts.values())
        disc_rows.append([op, counts["full_20"], counts["full_40"],
                           counts["empty_20"], counts["empty_40"], total])
                           
    next_row = _write_table(ws, 8, 0, headers, disc_rows, formats["header"], formats)

    if disc_rows:
        chart = workbook.add_chart({"type": "column"})
        n = len(disc_rows)
        chart.add_series({
            "name": "Full 20'",
            "categories": ["Par Operateur", 9, 0, 8 + n, 0],
            "values": ["Par Operateur", 9, 1, 8 + n, 1],
            "fill": {"color": "#8BB346"},  # Vert SOMAPORT
        })
        chart.add_series({
            "name": "Full 40'+",
            "categories": ["Par Operateur", 9, 0, 8 + n, 0],
            "values": ["Par Operateur", 9, 2, 8 + n, 2],
            "fill": {"color": "#2D3133"},  # Charcoal SOMAPORT
        })
        chart.set_title({"name": "Conteneurs déchargés par opérateur"})
        chart.set_x_axis({"name": "Opérateur"})
        chart.set_y_axis({"name": "Conteneurs"})
        ws.insert_chart(7, 7, chart, {"x_scale": 1.1, "y_scale": 1.1})

    ws.set_row(next_row, 24)
    ws.write(next_row, 0, "Conteneurs chargés (Export / Deepsea) par opérateur", formats["section"])
    load_rows = []
    for op, counts in sorted(kpi.operator_loaded.items()):
        total = sum(counts.values())
        load_rows.append([op, counts["full_20"], counts["full_40"],
                           counts["empty_20"], counts["empty_40"], total])
                           
    _write_table(ws, next_row + 1, 0, headers, load_rows, formats["header"], formats)


def build_crane_productivity_sheet(workbook, kpi: KPIResult, formats: dict):
    ws = workbook.add_worksheet("Productivite Grues")
    ws.set_column(0, 0, 16)
    ws.set_column(1, 6, 20)

    setup_sheet_header(ws, workbook, "Productivité des Grues de Quai", end_col=6)
    
    headers = ["Grue", "Sessions", "Moves Import", "Moves Export", "Moves Total",
               "Heures travaillées", "Moves/heure (brut)"]
    rows = []
    for crane_id, cp in sorted(kpi.crane_productivity.items()):
        rows.append([
            crane_id, cp.sessions, cp.total_import_moves, cp.total_export_moves,
            cp.total_moves, cp.total_working_hours,
            cp.gross_moves_per_hour if cp.gross_moves_per_hour is not None else "N/A",
        ])
        
    _write_table(ws, 7, 0, headers, rows, formats["header"], formats)

    if rows:
        n = len(rows)
        chart = workbook.add_chart({"type": "column"})
        chart.add_series({
            "name": "Moves Total",
            "categories": ["Productivite Grues", 8, 0, 7 + n, 0],
            "values": ["Productivite Grues", 8, 4, 7 + n, 4],
            "fill": {"color": "#8BB346"},  # Vert SOMAPORT
        })
        chart.set_title({"name": "Total des mouvements par grue"})
        chart.set_x_axis({"name": "Grue"})
        chart.set_y_axis({"name": "Mouvements"})
        ws.insert_chart(7, 8, chart, {"x_scale": 1.1, "y_scale": 1.1})


def build_iso_distribution_sheet(workbook, kpi: KPIResult, formats: dict):
    ws = workbook.add_worksheet("Repartition ISO")
    ws.set_column(0, 0, 16)
    ws.set_column(1, 2, 16)

    setup_sheet_header(ws, workbook, "Répartition par Taille ISO", end_col=2)
    
    headers = ["Taille", "Import", "Export"]
    sizes = sorted(set(kpi.iso_size_distribution.get("IMPORT", {}))
                    | set(kpi.iso_size_distribution.get("EXPORT", {})))
    rows = [
        [size, kpi.iso_size_distribution.get("IMPORT", {}).get(size, 0),
         kpi.iso_size_distribution.get("EXPORT", {}).get(size, 0)]
        for size in sizes
    ]
    
    _write_table(ws, 7, 0, headers, rows, formats["header"], formats)

    if rows:
        n = len(rows)
        chart = workbook.add_chart({"type": "pie"})
        chart.add_series({
            "name": "Import par taille",
            "categories": ["Repartition ISO", 8, 0, 7 + n, 0],
            "values": ["Repartition ISO", 8, 1, 7 + n, 1],
            "points": [
                {"fill": {"color": "#8BB346"}},  # Vert SOMAPORT
                {"fill": {"color": "#2D3133"}},  # Charcoal SOMAPORT
                {"fill": {"color": "#A1C965"}}
            ]
        })
        chart.set_title({"name": "Répartition Import par taille ISO"})
        ws.insert_chart(7, 5, chart, {"x_scale": 1.1, "y_scale": 1.1})


def generate_dashboard(merged: MergedVesselDataset, kpi: KPIResult,
                        output_path: Path | None = None) -> Path:
    """Point d'entrée unique : génère le classeur dashboard complet."""
    if output_path is None:
        output_path = config.OUTPUT_DASHBOARD_PATH
    logger.info("Génération du dashboard Excel pour %s", merged.vessel_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Sauvegarde défensive (PermissionError / FileCreateError) ──
    safe_output_path = output_path
    if output_path.exists():
        try:
            with open(output_path, "ab"):
                pass
        except PermissionError:
            from datetime import datetime as _dt
            stamp = _dt.now().strftime("%H%M%S")
            alt_name = output_path.stem + f"_{stamp}" + output_path.suffix
            safe_output_path = output_path.parent / alt_name
            logger.warning(
                "PermissionError : '%s' est ouvert. Sauvegarde de secours dans '%s'.",
                output_path.name, safe_output_path.name
            )

    workbook = xlsxwriter.Workbook(str(safe_output_path))

    # Formats stylisés SOMAPORT avec police agrandie et en gras
    formats = {
        "header": workbook.add_format({
            "bold": True,
            "bg_color": "#2D3133",      # Charcoal SOMAPORT
            "font_color": "#FFFFFF",     # Blanc
            "font_name": "Onest",
            "font_size": 12,
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#D9D9D9"
        }),
        "cell": workbook.add_format({
            "font_name": "Roboto",
            "font_size": 11,
            "bold": True,
            "border": 1,
            "border_color": "#E0E0E0",
            "align": "left",
            "valign": "vcenter"
        }),
        "cell_center": workbook.add_format({
            "font_name": "Roboto",
            "font_size": 11,
            "bold": True,
            "border": 1,
            "border_color": "#E0E0E0",
            "align": "center",
            "valign": "vcenter"
        }),
        "cell_right": workbook.add_format({
            "font_name": "Roboto",
            "font_size": 11,
            "bold": True,
            "border": 1,
            "border_color": "#E0E0E0",
            "align": "right",
            "valign": "vcenter"
        }),
        "section": workbook.add_format({
            "bold": True,
            "font_size": 12,
            "font_name": "Onest",
            "font_color": "#8BB346",    # Vert SOMAPORT
            "bottom": 1,
            "bottom_color": "#8BB346"
        })
    }

    build_kpi_sheet(workbook, merged, kpi, formats)
    build_operator_sheet(workbook, kpi, formats)
    build_crane_productivity_sheet(workbook, kpi, formats)
    build_iso_distribution_sheet(workbook, kpi, formats)

    workbook.close()
    logger.info("Dashboard enregistré : %s", safe_output_path)
    return safe_output_path
