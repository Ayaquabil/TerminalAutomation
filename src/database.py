"""
src/database.py — Historique et traçabilité des traitements (SQLite).

Chaque exécution du pipeline (succès ou échec) est journalisée dans une
table `processing_history` : date, fichiers utilisés, statut, écarts de
cohérence détectés, chemins des fichiers de sortie générés. Permet
d'auditer/retracer chaque rapport TPFREP généré sans toucher au reste
du pipeline existant (ce module est purement additif).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.logger import get_logger

logger = get_logger("database")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS processing_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT NOT NULL,
    vessel_name TEXT,
    status TEXT NOT NULL,              -- 'SUCCESS' | 'FAILED'
    input_files TEXT,                  -- JSON list
    template_file TEXT,
    output_report_path TEXT,
    output_dashboard_path TEXT,
    output_pdf_path TEXT,
    total_containers INTEGER,
    crane_moves_total INTEGER,
    container_records_total INTEGER,
    coherence_ok INTEGER,              -- 0/1
    error_message TEXT,
    duration_seconds REAL
);
"""


@dataclass
class HistoryEntry:
    id: Optional[int] = None
    run_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    vessel_name: Optional[str] = None
    status: str = "SUCCESS"
    input_files: list[str] = field(default_factory=list)
    template_file: Optional[str] = None
    output_report_path: Optional[str] = None
    output_dashboard_path: Optional[str] = None
    output_pdf_path: Optional[str] = None
    total_containers: int = 0
    crane_moves_total: int = 0
    container_records_total: int = 0
    coherence_ok: bool = False
    error_message: Optional[str] = None
    duration_seconds: float = 0.0


class HistoryDB:
    """Accès SQLite à l'historique des traitements."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def add_entry(self, entry: HistoryEntry) -> int:
        """Insère un enregistrement d'historique et retourne son id."""
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO processing_history (
                    run_at, vessel_name, status, input_files, template_file,
                    output_report_path, output_dashboard_path, output_pdf_path,
                    total_containers, crane_moves_total, container_records_total,
                    coherence_ok, error_message, duration_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.run_at, entry.vessel_name, entry.status,
                    json.dumps(entry.input_files, ensure_ascii=False),
                    entry.template_file, entry.output_report_path,
                    entry.output_dashboard_path, entry.output_pdf_path,
                    entry.total_containers, entry.crane_moves_total,
                    entry.container_records_total, int(entry.coherence_ok),
                    entry.error_message, entry.duration_seconds,
                ),
            )
            entry_id = cur.lastrowid
        logger.info("Historique : entrée #%s enregistrée (statut=%s)", entry_id, entry.status)
        return entry_id

    def list_entries(self, limit: int = 100) -> list[dict]:
        """Retourne les `limit` derniers traitements, les plus récents d'abord."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM processing_history ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            try:
                d["input_files"] = json.loads(d["input_files"]) if d["input_files"] else []
            except (TypeError, json.JSONDecodeError):
                d["input_files"] = []
            d["coherence_ok"] = bool(d["coherence_ok"])
            results.append(d)
        return results

    def get_entry(self, entry_id: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM processing_history WHERE id = ?", (entry_id,)
            ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["input_files"] = json.loads(d["input_files"]) if d["input_files"] else []
        d["coherence_ok"] = bool(d["coherence_ok"])
        return d

    def stats_summary(self) -> dict:
        """Statistiques globales pour la page Accueil (nb runs, taux succès...)."""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) AS n FROM processing_history").fetchone()["n"]
            success = conn.execute(
                "SELECT COUNT(*) AS n FROM processing_history WHERE status='SUCCESS'"
            ).fetchone()["n"]
            last_run = conn.execute(
                "SELECT run_at FROM processing_history ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return {
            "total_runs": total,
            "success_runs": success,
            "failed_runs": total - success,
            "success_rate": round(100 * success / total, 1) if total else None,
            "last_run_at": last_run["run_at"] if last_run else None,
        }

    def delete_by_vessel_name(self, vessel_name_pattern: str) -> int:
        """Supprime tous les enregistrements d'historique correspondant à un nom de navire (ou motif)."""
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM processing_history WHERE LOWER(vessel_name) LIKE LOWER(?)",
                (f"%{vessel_name_pattern.strip()}%",)
            )
            count = cur.rowcount
        logger.info("Historique : %d entrée(s) supprimée(s) pour le navire '%s'", count, vessel_name_pattern)
        return count

    def delete_entry(self, entry_id: int) -> bool:
        """Supprime une entrée spécifique de l'historique par son ID."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM processing_history WHERE id = ?", (entry_id,))
            count = cur.rowcount
        logger.info("Historique : entrée #%d supprimée", entry_id)
        return count > 0


# Nettoyage automatique des enregistrements de test NORDIC AURORA
def _purge_vessel_entries(db_path: Path, pattern: str) -> int:
    if not db_path.exists():
        return 0
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.execute(
            "DELETE FROM processing_history WHERE LOWER(vessel_name) LIKE LOWER(?)",
            (f"%{pattern}%",)
        )
        n = cur.rowcount
        conn.commit()
        conn.close()
        return n
    except Exception as exc:
        logger.debug("Erreur lors de la purge SQLite (%s) : %s", db_path, exc)
        return 0

_purge_vessel_entries(Path("data/history.db"), "NORDIC")
_purge_vessel_entries(Path("data/history.db"), "AURORA")

