"""
src/settings_loader.py — Chargement de la configuration métier depuis
config/settings.yaml.

Ce module remplace les constantes auparavant codées en dur dans
config.py par une lecture déclarative, sans changer le comportement du
pipeline existant. `config.py` reste le point d'entrée utilisé par
tout le reste du code (src/*) : il instancie `Settings` une seule fois
et réexpose chaque constante avec son nom historique.

Toute clé manquante dans le YAML retombe sur la valeur par défaut
correspondante (issue de l'ancien config.py), pour qu'un fichier
settings.yaml partiellement édité ne casse jamais le pipeline.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "Le paquet 'pyyaml' est requis (pip install pyyaml). "
        "Voir requirements.txt."
    ) from exc

_logger = logging.getLogger("terminal_automation.settings")

DEFAULT_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"

# Valeurs par défaut = comportement historique de l'ancien config.py.
# Utilisées si le fichier settings.yaml est absent, illisible, ou si une
# clé précise manque.
_DEFAULTS: dict[str, Any] = {
    "paths": {
        "data_dir": "data",
        "input_dir": "data/input",
        "template_dir": "data/template",
        "output_dir": "data/output",
        "archive_dir": "data/archive",
        "logs_dir": "logs",
        "log_file": "logs/application.log",
        "database_file": "data/history.db",
        "template_filename": "TPFREP MASTERY D MAD0426W.xlsx",
        "output_report_filename": "TPFREP_FINAL.xlsx",
        "output_dashboard_filename": "DASHBOARD.xlsx",
    },
    "file_detection": {
        "shift_filename_patterns": {
            1: r"rapport\s+de\s+1\s+shift",
            2: r"rapport\s+de\s+2\s+shift",
            3: r"rapport\s+de\s+3\s+shift",
        },
        "import_masteryd_pattern": r"import\s+masteryd",
        "export_masteryd_pattern": r"export\s+masteryd",
        "blue_cell_template_threshold": 100,
    },
    "vessel": {
        "target_name": "MASTERY D",
        "target_normalized": "MASTERYD",
    },
    "terminal": {
        "vessel_port_unlocode": "MACAS",
        "terminal_code": "SOMAPORT",
        "voyage_import": "MAD0426W",
        "voyage_export": "MAD0426W",
        "vessel_imo_default": "-",
        "vessel_call_sign_default": "-",
    },
    "cranes": {
        "crane_ids": ["P1", "P2", "P3", "P4"],
        "template_column": {"P1": 4, "P2": 5, "P4": 6, "P3": 7},
    },
    "shift_columns": {
        "crane_id": 0,
        "vessel": 1,
        "import_moves": 3,
        "export_moves": 4,
        "doc": 5,
        "foc": 6,
        "observations": 7,
    },
    "template_color": {
        "blue_indexed": 44,
        "blue_rgb_fallback": "FF99CCFF",
    },
    "template_layout": {
        "max_sessions_per_crane": 8,
        "session_rows": [
            [37, 38], [40, 41], [43, 44], [46, 47],
            [49, 50], [52, 53], [55, 56], [58, 59],
        ],
        "total_moves_per_crane_row": 64,
        "general_delay_rows": [26, 27, 28, 29],
        "restow_common_row": 202,
        "hatch_cover_row": 232,
        "discharged_start_row": 127,
        "loaded_deepsea_start_row": 158,
        "max_operators": 10,
    },
    "validation": {
        "max_reasonable_session_hours": 20,
        "min_valid_year": 2020,
        "max_valid_year": 2035,
        "required_masteryd_columns": [
            "Nø CONTENEUR", "CODE MVT", "EXP IMP TRB", "V/P", "TYPE ISO",
            "TAG FRIGO", "TAG DANG 0/1", "TAG HG 0/1",
            "EXPLOITANT EN COURS", "ESCALE", "DATE DE SAISIE",
        ],
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Fusionne `override` dans `base` récursivement (override gagne),
    sans muter `base`."""
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Settings:
    """Configuration métier chargée depuis settings.yaml, avec repli sur
    des valeurs par défaut sûres pour chaque clé manquante."""

    def __init__(self, yaml_path: Optional[Path] = None, base_dir: Optional[Path] = None):
        self.base_dir = (base_dir or DEFAULT_SETTINGS_PATH.parent.parent).resolve()
        self.yaml_path = Path(yaml_path) if yaml_path else DEFAULT_SETTINGS_PATH
        self._data = self._load()

    def _load(self) -> dict:
        if not self.yaml_path.exists():
            _logger.warning(
                "settings.yaml introuvable (%s) — utilisation des valeurs "
                "par défaut historiques.", self.yaml_path,
            )
            return _DEFAULTS
        try:
            with open(self.yaml_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
        except Exception as exc:
            _logger.error(
                "Impossible de lire settings.yaml (%s) : %s — utilisation "
                "des valeurs par défaut.", self.yaml_path, exc,
            )
            return _DEFAULTS
        return _deep_merge(_DEFAULTS, raw)

    def reload(self) -> None:
        """Recharge le fichier YAML (utile depuis la page Paramètres)."""
        self._data = self._load()

    def get(self, *path: str, default: Any = None) -> Any:
        """Accès sûr à une valeur imbriquée, ex : get('paths', 'input_dir')."""
        node: Any = self._data
        for key in path:
            if isinstance(node, dict) and key in node:
                node = node[key]
            else:
                return default
        return node

    # ── Chemins résolus (absolus, basés sur base_dir) ──────────────────
    def path(self, *keys: str) -> Path:
        rel = self.get("paths", *keys)
        return (self.base_dir / rel).resolve() if rel else self.base_dir

    def as_dict(self) -> dict:
        """Copie de la configuration complète (pour affichage/édition UI)."""
        import copy
        return copy.deepcopy(self._data)


_settings_instance: Optional[Settings] = None


def get_settings(force_reload: bool = False) -> Settings:
    """Retourne l'instance Settings unique (singleton), en la créant si
    nécessaire. `force_reload=True` recharge le YAML depuis le disque."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    elif force_reload:
        _settings_instance.reload()
    return _settings_instance
