"""
src/logger.py — Logging centralisé pour TerminalAutomation.

Toutes les opérations (import, validation, nettoyage, fusion, calculs,
génération de rapport, erreurs) sont journalisées dans logs/application.log
ainsi que sur la console.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_CONFIGURED = False


def get_logger(name: str = "terminal_automation", log_file: Path | None = None) -> logging.Logger:
    """
    Retourne un logger configuré. Le handler fichier + console n'est
    installé qu'une seule fois sur le logger racine 'terminal_automation'
    (les sous-loggers en héritent), même si get_logger est appelé
    plusieurs fois depuis différents modules.
    """
    global _CONFIGURED

    root_logger = logging.getLogger("terminal_automation")

    if not _CONFIGURED:
        root_logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        if log_file is not None:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        _CONFIGURED = True

    if name == "terminal_automation":
        return root_logger
    return logging.getLogger(f"terminal_automation.{name}")
