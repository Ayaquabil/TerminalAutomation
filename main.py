"""
main.py — Point d'entrée principal de TerminalAutomation.

Pipeline complet :
  1. Import automatique de tous les fichiers Excel depuis data/input/
  2. Validation (fichiers, colonnes, dates, doublons, valeurs obligatoires)
  3. Nettoyage (trim, normalisation dates/heures, conteneurs, ISO, mouvements)
  4. Fusion (rapports de shift + IMPORT/EXPORT MASTERYD) sur le navire cible
  5. Calcul des KPIs
  6. Remplissage automatique du template TPFREP -> data/output/TPFREP_FINAL.xlsx
  7. Génération du dashboard Excel -> data/output/DASHBOARD.xlsx

Usage :
    python main.py
"""

from __future__ import annotations

import sys
import traceback

import config
from src.calculations import compute_all_kpis
from src.cleaning import clean_all_shift_reports, clean_masteryd
from src.dashboard import generate_dashboard
from src.import_data import InputDiscoveryError, load_all_inputs
from src.logger import get_logger
from src.merge import build_merged_dataset
from src.report_generator import generate_tpfrep_report
from src.validation import validate_all

logger = get_logger("main", log_file=config.LOG_FILE)


def run_pipeline() -> int:
    """Exécute le pipeline complet. Retourne un code de sortie (0 = succès)."""
    logger.info("=" * 78)
    logger.info("DÉMARRAGE DE TERMINALAUTOMATION")
    logger.info("=" * 78)

    try:
        # 1. IMPORT
        logger.info("Étape 1/6 — Import des fichiers d'entrée")
        inputs = load_all_inputs()

        # 2. VALIDATION
        logger.info("Étape 2/6 — Validation des données")
        validation_report = validate_all(inputs)
        logger.info(validation_report.summary())
        if validation_report.has_errors():
            logger.error(
                "Des erreurs bloquantes ont été détectées ; le pipeline s'arrête "
                "avant le nettoyage. Corrigez les fichiers source et relancez."
            )
            for issue in validation_report.errors():
                logger.error("  - [%s] %s", issue.source, issue.message)
            return 1

        # 3. NETTOYAGE
        logger.info("Étape 3/6 — Nettoyage des données")
        cleaned_shifts = clean_all_shift_reports(inputs.shift_reports)
        df_import = clean_masteryd(inputs.import_masteryd)
        df_export = clean_masteryd(inputs.export_masteryd)

        # 4. FUSION
        logger.info("Étape 4/6 — Fusion des données sur le navire cible")
        merged = build_merged_dataset(cleaned_shifts, df_import, df_export)

        if merged.containers_import.empty and merged.containers_export.empty:
            logger.error(
                "Aucun conteneur trouvé pour le navire cible '%s' après filtrage par "
                "ESCALE. Vérifiez que les fichiers IMPORT/EXPORT MASTERYD correspondent "
                "bien à l'escale attendue. Le pipeline continue mais le rapport TPFREP "
                "sera très incomplet.",
                config.TARGET_VESSEL_NAME,
            )

        # 5. CALCULS
        logger.info("Étape 5/6 — Calcul des indicateurs (KPIs)")
        kpi = compute_all_kpis(merged)

        # 6. GÉNÉRATION DES SORTIES
        logger.info("Étape 6/6 — Génération des rapports de sortie")
        tpfrep_path = generate_tpfrep_report(merged, kpi, template_path=inputs.template_path)
        dashboard_path = generate_dashboard(merged, kpi)

        logger.info("=" * 78)
        logger.info("PIPELINE TERMINÉ AVEC SUCCÈS")
        logger.info("  Rapport TPFREP : %s", tpfrep_path)
        logger.info("  Dashboard      : %s", dashboard_path)
        logger.info("=" * 78)
        return 0

    except InputDiscoveryError as exc:
        logger.error("Erreur de découverte des fichiers d'entrée : %s", exc)
        return 2
    except ValueError as exc:
        logger.error("Erreur de validation : %s", exc)
        return 3
    except Exception:
        logger.error("Erreur inattendue dans le pipeline :\n%s", traceback.format_exc())
        return 4


if __name__ == "__main__":
    sys.exit(run_pipeline())
