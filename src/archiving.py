"""
src/archiving.py — Archivage automatique des fichiers traités.

Après chaque exécution réussie du pipeline, les fichiers d'entrée
(rapports de shift, MASTERYD, template) et les sorties générées
(TPFREP_FINAL.xlsx, DASHBOARD.xlsx, PDF) sont déplacés/copiés vers
`data/archive/<AAAA-MM-JJ>_<HHhMMmSS>/` pour garder une trace complète
et éviter d'écraser les traitements précédents. Module purement
additif, n'impacte aucun autre composant du pipeline.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable

from src.logger import get_logger

logger = get_logger("archiving")


def build_run_archive_dir(archive_root: Path, run_at: datetime | None = None) -> Path:
    """Construit (et crée) le dossier d'archive pour un run donné."""
    run_at = run_at or datetime.now()
    folder_name = run_at.strftime("%Y-%m-%d_%Hh%Mm%S")
    run_dir = Path(archive_root) / folder_name
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def archive_run(
    archive_root: Path,
    input_files: Iterable[Path],
    template_file: Path | None,
    output_files: Iterable[Path],
    run_at: datetime | None = None,
) -> Path:
    """Copie les fichiers d'entrée et de sortie d'un run vers un dossier
    d'archive horodaté. Retourne le chemin du dossier créé.

    Les fichiers sources ne sont jamais supprimés de data/input ou
    data/template (copie, pas déplacement) afin de ne jamais perdre de
    données en cas d'erreur d'archivage."""
    run_dir = build_run_archive_dir(archive_root, run_at)
    inputs_dir = run_dir / "inputs"
    outputs_dir = run_dir / "outputs"
    inputs_dir.mkdir(exist_ok=True)
    outputs_dir.mkdir(exist_ok=True)

    copied, skipped = [], []

    for f in input_files:
        f = Path(f)
        if f.exists():
            shutil.copy2(f, inputs_dir / f.name)
            copied.append(f.name)
        else:
            skipped.append(str(f))

    if template_file is not None:
        template_file = Path(template_file)
        if template_file.exists():
            shutil.copy2(template_file, inputs_dir / template_file.name)
            copied.append(template_file.name)
        else:
            skipped.append(str(template_file))

    for f in output_files:
        f = Path(f)
        if f.exists():
            shutil.copy2(f, outputs_dir / f.name)
            copied.append(f.name)
        else:
            skipped.append(str(f))

    logger.info(
        "Archivage terminé -> %s (%d fichier(s) copié(s)%s)",
        run_dir, len(copied),
        f", {len(skipped)} introuvable(s) ignoré(s)" if skipped else "",
    )
    if skipped:
        logger.debug("Fichiers ignorés à l'archivage (introuvables) : %s", skipped)

    return run_dir


def list_archived_runs(archive_root: Path) -> list[Path]:
    """Liste les dossiers d'archive existants, du plus récent au plus ancien."""
    archive_root = Path(archive_root)
    if not archive_root.exists():
        return []
    runs = [p for p in archive_root.iterdir() if p.is_dir()]
    return sorted(runs, key=lambda p: p.name, reverse=True)
