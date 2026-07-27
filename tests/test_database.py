"""tests/test_database.py — Tests de src.database.HistoryDB."""

from __future__ import annotations

from pathlib import Path

from src.database import HistoryDB, HistoryEntry


def test_history_db_creates_schema(tmp_path: Path):
    db = HistoryDB(tmp_path / "history.db")
    assert db.db_path.exists()


def test_add_and_list_entry(tmp_path: Path):
    db = HistoryDB(tmp_path / "history.db")
    entry = HistoryEntry(
        status="SUCCESS", vessel_name="MASTERY D", total_containers=547,
        crane_moves_total=547, container_records_total=547, coherence_ok=True,
        input_files=["a.xlsx", "b.xlsx"],
    )
    entry_id = db.add_entry(entry)
    assert entry_id == 1

    entries = db.list_entries()
    assert len(entries) == 1
    assert entries[0]["status"] == "SUCCESS"
    assert entries[0]["total_containers"] == 547
    assert entries[0]["input_files"] == ["a.xlsx", "b.xlsx"]
    assert entries[0]["coherence_ok"] is True


def test_get_entry_by_id(tmp_path: Path):
    db = HistoryDB(tmp_path / "history.db")
    entry_id = db.add_entry(HistoryEntry(status="FAILED", error_message="boom"))
    fetched = db.get_entry(entry_id)
    assert fetched is not None
    assert fetched["status"] == "FAILED"
    assert fetched["error_message"] == "boom"


def test_get_entry_missing_returns_none(tmp_path: Path):
    db = HistoryDB(tmp_path / "history.db")
    assert db.get_entry(999) is None


def test_stats_summary(tmp_path: Path):
    db = HistoryDB(tmp_path / "history.db")
    db.add_entry(HistoryEntry(status="SUCCESS"))
    db.add_entry(HistoryEntry(status="SUCCESS"))
    db.add_entry(HistoryEntry(status="FAILED"))
    stats = db.stats_summary()
    assert stats["total_runs"] == 3
    assert stats["success_runs"] == 2
    assert stats["failed_runs"] == 1
    assert stats["success_rate"] == round(200 / 3, 1)


def test_stats_summary_empty_db(tmp_path: Path):
    db = HistoryDB(tmp_path / "history.db")
    stats = db.stats_summary()
    assert stats["total_runs"] == 0
    assert stats["success_rate"] is None
    assert stats["last_run_at"] is None
