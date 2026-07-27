"""
config.py — Point d'entrée de compatibilité pour la configuration.

Historique : ce module contenait auparavant toutes les constantes
métier codées en dur. Elles ont été déplacées vers config/settings.yaml
(lecture via src/settings_loader.Settings) pour permettre de modifier
la configuration sans toucher au code Python (chemins, mapping de
colonnes/cellules, seuils, infos terminal...).

Ce fichier reste le point d'entrée utilisé par tout le reste du code
(`import config; config.XXX`) : chaque constante historique est
réexposée ici avec exactement le même nom et la même valeur par
défaut qu'avant, pour ne rien casser dans src/*.

Pour changer une valeur : éditer config/settings.yaml, PAS ce fichier.
"""

from __future__ import annotations

from pathlib import Path

from src.settings_loader import get_settings

_settings = get_settings()

# ─────────────────────────────────────────────────────────────
# CHEMINS
# ─────────────────────────────────────────────────────────────
BASE_DIR = _settings.base_dir

DATA_DIR = _settings.path("data_dir")
INPUT_DIR = _settings.path("input_dir")
TEMPLATE_DIR = _settings.path("template_dir")
OUTPUT_DIR = _settings.path("output_dir")
ARCHIVE_DIR = _settings.path("archive_dir")
LOGS_DIR = _settings.path("logs_dir")

LOG_FILE = _settings.path("log_file")
DATABASE_FILE = _settings.path("database_file")

TEMPLATE_FILENAME = _settings.get("paths", "template_filename")
TEMPLATE_PATH = TEMPLATE_DIR / TEMPLATE_FILENAME

OUTPUT_REPORT_FILENAME = _settings.get("paths", "output_report_filename")
OUTPUT_REPORT_PATH = OUTPUT_DIR / OUTPUT_REPORT_FILENAME

OUTPUT_DASHBOARD_FILENAME = _settings.get("paths", "output_dashboard_filename")
OUTPUT_DASHBOARD_PATH = OUTPUT_DIR / OUTPUT_DASHBOARD_FILENAME

# Motifs de noms de fichiers attendus dans data/input (insensibles à la casse,
# espaces multiples tolérés). Utilisés par import_data.discover_input_files().
SHIFT_FILENAME_PATTERNS = _settings.get("file_detection", "shift_filename_patterns")
IMPORT_MASTERYD_PATTERN = _settings.get("file_detection", "import_masteryd_pattern")
EXPORT_MASTERYD_PATTERN = _settings.get("file_detection", "export_masteryd_pattern")

# ─────────────────────────────────────────────────────────────
# NAVIRE CIBLE
# ─────────────────────────────────────────────────────────────
TARGET_VESSEL_NAME = _settings.get("vessel", "target_name")
TARGET_VESSEL_NORMALIZED = _settings.get("vessel", "target_normalized")

# ─────────────────────────────────────────────────────────────
# MÉTIER / NON PRÉSENT DANS LES FICHIERS SOURCE
# ─────────────────────────────────────────────────────────────
VESSEL_PORT_UNLOCODE = _settings.get("terminal", "vessel_port_unlocode")
TERMINAL_CODE = _settings.get("terminal", "terminal_code")
VOYAGE_IMPORT = _settings.get("terminal", "voyage_import")
VOYAGE_EXPORT = _settings.get("terminal", "voyage_export")
VESSEL_IMO_DEFAULT = _settings.get("terminal", "vessel_imo_default")
VESSEL_CALL_SIGN_DEFAULT = _settings.get("terminal", "vessel_call_sign_default")

# ─────────────────────────────────────────────────────────────
# GRUES
# ─────────────────────────────────────────────────────────────
CRANE_IDS = tuple(_settings.get("cranes", "crane_ids"))
CRANE_TEMPLATE_COLUMN = dict(_settings.get("cranes", "template_column"))

# Colonnes (0-indexed) des rapports de shift réels (table par grue) :
# A=Crane ID(0) | B=Vessel(1) | D=Import moves(3) | E=Export moves(4)
# | F=DOC(5) | G=FOC(6) | H=Observations(7)
SHIFT_COL_CRANE_ID = _settings.get("shift_columns", "crane_id")
SHIFT_COL_VESSEL = _settings.get("shift_columns", "vessel")
SHIFT_COL_IMPORT_MOVES = _settings.get("shift_columns", "import_moves")
SHIFT_COL_EXPORT_MOVES = _settings.get("shift_columns", "export_moves")
SHIFT_COL_DOC = _settings.get("shift_columns", "doc")
SHIFT_COL_FOC = _settings.get("shift_columns", "foc")
SHIFT_COL_OBSERVATIONS = _settings.get("shift_columns", "observations")

# ─────────────────────────────────────────────────────────────
# TEMPLATE TPFREP — couleur bleue et lignes/colonnes (0-indexed)
# ─────────────────────────────────────────────────────────────
# Couleur bleue = couleur INDEXÉE 44 du classeur (confirmé par inspection :
# openpyxl renvoie un indexed color, pas un rgb direct, pour ce fichier).
BLUE_INDEXED = _settings.get("template_color", "blue_indexed")

# Si le template original est fourni en .xls et converti en .xlsx (via
# LibreOffice), la couleur indexée 44 est réécrite en RVB direct lors de
# la conversion (indexed=44 -> rgb='FF99CCFF'). On l'accepte donc aussi
# comme bleu, sans rien changer au comportement existant pour les .xlsx
# natifs.
BLUE_RGB_FALLBACK = _settings.get("template_color", "blue_rgb_fallback")

MAX_SESSIONS_PER_CRANE = _settings.get("template_layout", "max_sessions_per_crane")
SESSION_ROWS = [tuple(pair) for pair in _settings.get("template_layout", "session_rows")]

TOTAL_MOVES_PER_CRANE_ROW = _settings.get("template_layout", "total_moves_per_crane_row")

GENERAL_DELAY_ROWS = list(_settings.get("template_layout", "general_delay_rows"))
GENERAL_DELAY_MAX_ENTRIES = len(GENERAL_DELAY_ROWS)

RESTOW_COMMON_ROW = _settings.get("template_layout", "restow_common_row")
HATCH_COVER_ROW = _settings.get("template_layout", "hatch_cover_row")

DISCHARGED_START_ROW = _settings.get("template_layout", "discharged_start_row")
LOADED_DEEPSEA_START_ROW = _settings.get("template_layout", "loaded_deepsea_start_row")
MAX_OPERATORS = _settings.get("template_layout", "max_operators")

# ─────────────────────────────────────────────────────────────
# SEUILS DE VALIDATION
# ─────────────────────────────────────────────────────────────
MAX_REASONABLE_SESSION_HOURS = _settings.get("validation", "max_reasonable_session_hours")
MIN_VALID_YEAR = _settings.get("validation", "min_valid_year")
MAX_VALID_YEAR = _settings.get("validation", "max_valid_year")
SHIFT_DATE_MARGIN_DAYS = _settings.get("validation", "shift_date_margin_days", default=1)
REQUIRED_MASTERYD_COLUMNS = tuple(_settings.get("validation", "required_masteryd_columns"))
