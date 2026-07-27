"""
src/pipeline_runner.py — Orchestration du pipeline complet, ré-exécutable
depuis l'interface (app.py) ou la ligne de commande (main.py reste
inchangé et continue de fonctionner seul).

Ce module est additif : il appelle les mêmes fonctions que main.py
(import -> validation -> nettoyage -> fusion -> calculs -> génération),
sans dupliquer leur logique, puis branche autour : mesure du temps,
génération PDF optionnelle, écriture en historique SQLite, archivage
des fichiers traités.
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import config
from src.archiving import archive_run
from src.calculations import KPIResult, compute_all_kpis
from src.cleaning import clean_all_shift_reports, clean_masteryd
from src.dashboard import generate_dashboard
from src.database import HistoryDB, HistoryEntry
from src.import_data import InputDiscoveryError, load_all_inputs
from src.logger import get_logger
from src.merge import MergedVesselDataset, build_merged_dataset, infer_escale_from_masteryd, infer_vessel_from_escale
from src.report_generator import generate_tpfrep_report
from src.utils import normalize_vessel_name
from src.validation import ValidationReport, validate_all

logger = get_logger("pipeline_runner", log_file=config.LOG_FILE)


@dataclass
class PipelineRunResult:
    success: bool
    merged: Optional[MergedVesselDataset] = None
    kpi: Optional[KPIResult] = None
    validation_report: Optional[ValidationReport] = None
    tpfrep_path: Optional[Path] = None
    dashboard_path: Optional[Path] = None
    error_message: Optional[str] = None
    duration_seconds: float = 0.0
    history_id: Optional[int] = None
    requires_escale_selection: bool = False
    available_escales: Optional[list] = None
    excluded_shifts: Optional[list] = None

def run_full_pipeline(
    archive_after_success: bool = True,
    progress_callback=None,
    vessel_name: Optional[str] = None,
    vessel_normalized: Optional[str] = None,
    target_escale: Optional[str] = None,
) -> PipelineRunResult:
    """Exécute le pipeline complet et journalise le résultat en base.

    `vessel_name` / `vessel_normalized` : nom du navire à traiter pour ce
    run. Si None, les valeurs de config.TARGET_VESSEL_NAME /
    config.TARGET_VESSEL_NORMALIZED sont utilisées (comportement historique).
    Cela permet de traiter n'importe quel navire sans modifier settings.yaml.

    `progress_callback(step: int, total: int, message: str)` est appelé
    à chaque étape si fourni (utilisé par l'UI Streamlit pour la barre
    de progression) ; ce paramètre est optionnel pour ne rien casser
    chez un appelant qui ne le fournit pas (ex : tests).
    """
    started_at = time.time()
    db = HistoryDB(config.DATABASE_FILE)

    # Résolution du nom de navire : paramètre fourni > config settings.yaml
    _vessel_name = (
        vessel_name.strip()
        if vessel_name and vessel_name.strip()
        else config.TARGET_VESSEL_NAME
    )
    _vessel_normalized = (
        vessel_normalized.strip()
        if vessel_normalized and vessel_normalized.strip()
        else normalize_vessel_name(_vessel_name)
    )
    logger.info(
        "Navire cible pour ce run : '%s' (normalisé : '%s')",
        _vessel_name, _vessel_normalized,
    )

    def notify(step: int, total: int, message: str) -> None:
        logger.info(message)
        if progress_callback:
            progress_callback(step, total, message)

    input_file_names: list[str] = []
    template_file_name: Optional[str] = None

    try:
        notify(1, 6, "Étape 1/6 — Import des fichiers d'entrée")
        from src.import_data import MultipleEscalesError
        try:
            inputs = load_all_inputs(target_escale=target_escale)
        except MultipleEscalesError as e:
            logger.warning(e)
            duration = time.time() - started_at
            return PipelineRunResult(
                success=False,
                error_message=str(e),
                duration_seconds=duration,
                requires_escale_selection=True,
                available_escales=e.escales
            )
            
        input_file_names = sorted(
            {s.file_path.name for s in inputs.shift_reports.values()}
            | {inputs.import_masteryd.file_path.name}
            | {inputs.export_masteryd.file_path.name}
        )
        template_file_name = inputs.template_path.name

        notify(2, 6, "Étape 2/6 — Validation des données")
        validation_report = validate_all(inputs)
        if validation_report.has_errors():
            error_msg = "Erreurs de validation bloquantes : " + "; ".join(
                f"[{i.source}] {i.message}" for i in validation_report.errors()
            )
            return _finalize_failure(
                db, started_at, input_file_names, template_file_name,
                error_msg, validation_report,
            )

        notify(3, 6, "Étape 3/6 — Nettoyage des données")
        cleaned_shifts = clean_all_shift_reports(inputs.shift_reports)
        df_import = clean_masteryd(inputs.import_masteryd)
        df_export = clean_masteryd(inputs.export_masteryd)

        # Déduire dynamiquement le navire cible via l'escale et les shifts
        escale_filter = infer_escale_from_masteryd(df_import, df_export)
        _vessel_name = infer_vessel_from_escale(escale_filter, cleaned_shifts)
        _vessel_normalized = normalize_vessel_name(_vessel_name)
        logger.info("Navire résolu dynamiquement des données : %s", _vessel_name)

        notify(4, 6, f"Étape 4/6 — Fusion des données sur le navire cible '{_vessel_name}'")
        merged = build_merged_dataset(
            cleaned_shifts, df_import, df_export,
            target_vessel_name=_vessel_name,
            target_vessel_normalized=_vessel_normalized,
        )

        if merged.containers_import.empty and merged.containers_export.empty:
            logger.error(
                "Aucun conteneur trouvé pour le navire cible '%s' après filtrage par "
                "ESCALE. Vérifiez que les fichiers IMPORT/EXPORT MASTERYD correspondent "
                "bien à l'escale attendue. Le pipeline continue mais le rapport TPFREP "
                "sera très incomplet.",
                _vessel_name,
            )

        notify(5, 6, "Étape 5/6 — Calcul des indicateurs (KPIs)")
        kpi = compute_all_kpis(merged)

        notify(6, 6, "Étape 6/6 — Génération des rapports de sortie")
        tpfrep_path = generate_tpfrep_report(merged, kpi, template_path=inputs.template_path)
        dashboard_path = generate_dashboard(merged, kpi)


        duration = time.time() - started_at
        logger.info("Pipeline terminé en %.2fs (statut=SUCCESS)", duration)

        history_id = db.add_entry(HistoryEntry(
            vessel_name=_vessel_name,
            status="SUCCESS",
            input_files=input_file_names,
            template_file=template_file_name,
            output_report_path=str(tpfrep_path),
            output_dashboard_path=str(dashboard_path),
            total_containers=kpi.total_containers,
            duration_seconds=duration,
        ))

        if archive_after_success:
            try:
                outputs = [p for p in (tpfrep_path, dashboard_path) if p]
                archive_run(
                    config.ARCHIVE_DIR,
                    input_files=[s.file_path for s in inputs.shift_reports.values()]
                    + [inputs.import_masteryd.file_path, inputs.export_masteryd.file_path],
                    template_file=inputs.template_path,
                    output_files=outputs,
                )
            except Exception as exc:  # archivage non bloquant
                logger.warning("Archivage non bloquant en échec : %s", exc)

        return PipelineRunResult(
            success=True, merged=merged, kpi=kpi, validation_report=validation_report,
            tpfrep_path=tpfrep_path, dashboard_path=dashboard_path,
            duration_seconds=duration, history_id=history_id,
            excluded_shifts=inputs.excluded_shifts,
        )

    except InputDiscoveryError as exc:
        return _finalize_failure(db, started_at, input_file_names, template_file_name, str(exc))
    except ValueError as exc:
        return _finalize_failure(db, started_at, input_file_names, template_file_name, str(exc))
    except Exception as e:
        tb = traceback.format_exc()
        logger.error("Erreur inattendue dans le pipeline :\n%s", tb)
        try:
            with open(config.DATA_DIR / "error.txt", "w", encoding="utf-8") as f:
                f.write(tb)

        except Exception as _write_err:
            logger.debug("Impossible d'ecrire data/error.txt : %s", _write_err)

        return _finalize_failure(
            db, started_at, input_file_names, template_file_name,
            "Erreur inattendue — voir logs/application.log pour le détail.",
        )


def _finalize_failure(
    db: HistoryDB, started_at: float, input_files: list[str],
    template_file: Optional[str], error_message: str,
    validation_report: Optional[ValidationReport] = None,
) -> PipelineRunResult:
    duration = time.time() - started_at
    logger.info("Pipeline terminé en %.2fs (statut=FAILED) - Erreur: %s", duration, error_message)
    history_id = db.add_entry(HistoryEntry(
        status="FAILED",
        input_files=input_files,
        template_file=template_file,
        error_message=error_message,
        duration_seconds=duration,
    ))
    return PipelineRunResult(
        success=False, error_message=error_message,
        validation_report=validation_report,
        duration_seconds=duration, history_id=history_id,
    )
