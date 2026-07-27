"""tests/test_archiving.py — Tests de src.archiving."""

from __future__ import annotations

from pathlib import Path

from src.archiving import archive_run, build_run_archive_dir, list_archived_runs


def _make_file(path: Path, content: bytes = b"data") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_build_run_archive_dir_creates_folder(tmp_path: Path):
    run_dir = build_run_archive_dir(tmp_path)
    assert run_dir.exists()
    assert run_dir.parent == tmp_path


def test_archive_run_copies_inputs_and_outputs(tmp_path: Path):
    archive_root = tmp_path / "archive"
    input_file = _make_file(tmp_path / "input" / "shift1.xlsx")
    template_file = _make_file(tmp_path / "template" / "template.xlsx")
    output_file = _make_file(tmp_path / "output" / "TPFREP_FINAL.xlsx")

    run_dir = archive_run(
        archive_root,
        input_files=[input_file],
        template_file=template_file,
        output_files=[output_file],
    )

    assert (run_dir / "inputs" / "shift1.xlsx").exists()
    assert (run_dir / "inputs" / "template.xlsx").exists()
    assert (run_dir / "outputs" / "TPFREP_FINAL.xlsx").exists()

    # Le fichier source ne doit jamais être supprimé (copie, pas déplacement).
    assert input_file.exists()
    assert template_file.exists()


def test_archive_run_ignores_missing_files_without_crashing(tmp_path: Path):
    archive_root = tmp_path / "archive"
    missing_file = tmp_path / "does_not_exist.xlsx"

    run_dir = archive_run(
        archive_root, input_files=[missing_file], template_file=None, output_files=[],
    )

    assert run_dir.exists()
    assert not (run_dir / "inputs" / "does_not_exist.xlsx").exists()


def test_list_archived_runs_returns_most_recent_first(tmp_path: Path):
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    (archive_root / "2024-01-01_10h00m00").mkdir()
    (archive_root / "2025-06-15_08h30m00").mkdir()

    runs = list_archived_runs(archive_root)
    assert len(runs) == 2
    assert runs[0].name == "2025-06-15_08h30m00"


def test_list_archived_runs_empty_when_no_archive_dir(tmp_path: Path):
    assert list_archived_runs(tmp_path / "nonexistent") == []
