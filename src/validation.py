"""
src/validation.py — Validation des données importées AVANT nettoyage/fusion :

- présence des fichiers et feuilles
- présence des colonnes obligatoires (IMPORT/EXPORT MASTERYD)
- validité des dates (année plausible)
- doublons de numéro de conteneur (au sein d'un fichier, et entre import/export)
- valeurs obligatoires non nulles (conteneur, ISO, V/P, exploitant)

Toutes les anomalies sont collectées dans un ValidationReport plutôt que de
lever une exception au premier problème, afin de produire un diagnostic
complet en une seule passe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List

import config
from src.import_data import AllInputs, RawMasterydFile, RawShiftReport
from src.logger import get_logger
from src.utils import is_valid_container_number, normalize_container_number

logger = get_logger("validation")


class Severity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class ValidationIssue:
    severity: Severity
    source: str
    message: str


@dataclass
class ValidationReport:
    issues: List[ValidationIssue] = field(default_factory=list)

    def add(self, severity: Severity, source: str, message: str):
        self.issues.append(ValidationIssue(severity, source, message))
        log_fn = {
            Severity.ERROR: logger.error,
            Severity.WARNING: logger.warning,
            Severity.INFO: logger.info,
        }[severity]
        log_fn("[%s] %s", source, message)

    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]

    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]

    def has_errors(self) -> bool:
        return len(self.errors()) > 0

    def raise_if_errors(self):
        if self.has_errors():
            details = "\n".join(f"  - [{i.source}] {i.message}" for i in self.errors())
            raise ValueError(f"Validation échouée ({len(self.errors())} erreur(s)) :\n{details}")

    def summary(self) -> str:
        return (
            f"{len(self.issues)} anomalie(s) au total : "
            f"{len(self.errors())} erreur(s), {len(self.warnings())} avertissement(s)."
        )


REQUIRED_MASTERYD_COLUMNS = config.REQUIRED_MASTERYD_COLUMNS


def validate_masteryd_columns(masteryd: RawMasterydFile, report: ValidationReport):
    """Vérifie que les colonnes obligatoires sont présentes dans l'en-tête."""
    header_set = {str(h).strip() for h in masteryd.header if h is not None}
    missing = [col for col in REQUIRED_MASTERYD_COLUMNS if col not in header_set]
    if missing:
        report.add(
            Severity.ERROR,
            f"{masteryd.direction} MASTERYD",
            f"Colonnes obligatoires manquantes : {missing}",
        )
    else:
        report.add(
            Severity.INFO,
            f"{masteryd.direction} MASTERYD",
            "Toutes les colonnes obligatoires sont présentes.",
        )


def validate_mandatory_values(masteryd: RawMasterydFile, report: ValidationReport):
    """Vérifie qu'aucune ligne n'a de valeur manquante sur les champs obligatoires."""
    header = [str(h).strip() if h else "" for h in masteryd.header]
    try:
        idx_container = header.index("Nø CONTENEUR")
        idx_vp = header.index("V/P")
        idx_iso = header.index("TYPE ISO")
        idx_expl = header.index("EXPLOITANT EN COURS")
    except ValueError:
        report.add(
            Severity.ERROR,
            f"{masteryd.direction} MASTERYD",
            "Impossible de localiser une colonne obligatoire pour la validation des valeurs.",
        )
        return

    missing_count = 0
    for i, row in enumerate(masteryd.rows, start=2):
        for idx, label in ((idx_container, "Nø CONTENEUR"), (idx_vp, "V/P"),
                           (idx_iso, "TYPE ISO"), (idx_expl, "EXPLOITANT EN COURS")):
            if idx >= len(row) or row[idx] is None or str(row[idx]).strip() == "":
                missing_count += 1
                report.add(
                    Severity.WARNING,
                    f"{masteryd.direction} MASTERYD",
                    f"Ligne {i} : valeur obligatoire manquante pour '{label}'",
                )
    if missing_count == 0:
        report.add(
            Severity.INFO,
            f"{masteryd.direction} MASTERYD",
            "Aucune valeur obligatoire manquante.",
        )


def validate_container_number_format(masteryd: RawMasterydFile, report: ValidationReport):
    """Vérifie que chaque numéro de conteneur respecte le format ISO 6346 attendu."""
    header = [str(h).strip() if h else "" for h in masteryd.header]
    try:
        idx_container = header.index("Nø CONTENEUR")
    except ValueError:
        return

    invalid = []
    for i, row in enumerate(masteryd.rows, start=2):
        value = row[idx_container] if idx_container < len(row) else None
        if value and not is_valid_container_number(value):
            invalid.append((i, value))

    if invalid:
        report.add(
            Severity.WARNING,
            f"{masteryd.direction} MASTERYD",
            f"{len(invalid)} numéro(s) de conteneur au format inattendu, ex: {invalid[:5]}",
        )


def validate_duplicate_containers(masteryd: RawMasterydFile, report: ValidationReport):
    """Détecte les doublons de numéro de conteneur au sein du même fichier."""
    header = [str(h).strip() if h else "" for h in masteryd.header]
    try:
        idx_container = header.index("Nø CONTENEUR")
    except ValueError:
        return

    seen = {}
    duplicates = []
    for i, row in enumerate(masteryd.rows, start=2):
        value = row[idx_container] if idx_container < len(row) else None
        if not value:
            continue
        norm = normalize_container_number(value)
        if norm in seen:
            duplicates.append((norm, seen[norm], i))
        else:
            seen[norm] = i

    if duplicates:
        report.add(
            Severity.WARNING,
            f"{masteryd.direction} MASTERYD",
            f"{len(duplicates)} doublon(s) de numéro de conteneur détecté(s) : {duplicates[:5]}",
        )
    else:
        report.add(
            Severity.INFO,
            f"{masteryd.direction} MASTERYD",
            "Aucun doublon de numéro de conteneur.",
        )


def validate_dates(masteryd: RawMasterydFile, report: ValidationReport):
    """Vérifie que DATE DE SAISIE (format AAAAMMJJ) tombe dans une plage plausible."""
    header = [str(h).strip() if h else "" for h in masteryd.header]
    try:
        idx_date = header.index("DATE DE SAISIE")
    except ValueError:
        return

    invalid = []
    for i, row in enumerate(masteryd.rows, start=2):
        raw = row[idx_date] if idx_date < len(row) else None
        if raw is None:
            continue
        try:
            s = str(int(raw))
            year = int(s[:4])
            month = int(s[4:6])
            day = int(s[6:8])
            datetime(year, month, day)
            if not (config.MIN_VALID_YEAR <= year <= config.MAX_VALID_YEAR):
                invalid.append((i, raw))
        except (ValueError, IndexError):
            invalid.append((i, raw))

    if invalid:
        report.add(
            Severity.WARNING,
            f"{masteryd.direction} MASTERYD",
            f"{len(invalid)} date(s) DE SAISIE invalide(s) ou hors plage plausible : {invalid[:5]}",
        )
    else:
        report.add(
            Severity.INFO,
            f"{masteryd.direction} MASTERYD",
            "Toutes les dates DE SAISIE sont valides.",
        )


def validate_cross_file_duplicates(import_masteryd: RawMasterydFile,
                                    export_masteryd: RawMasterydFile,
                                    report: ValidationReport):
    """Signale (avertissement) les numéros de conteneur présents à la fois en IMPORT et EXPORT."""
    def container_set(m: RawMasterydFile) -> set:
        header = [str(h).strip() if h else "" for h in m.header]
        try:
            idx = header.index("Nø CONTENEUR")
        except ValueError:
            return set()
        return {
            normalize_container_number(row[idx])
            for row in m.rows if idx < len(row) and row[idx]
        }

    common = container_set(import_masteryd) & container_set(export_masteryd)
    if common:
        report.add(
            Severity.INFO,
            "IMPORT/EXPORT MASTERYD",
            f"{len(common)} conteneur(s) présents à la fois en import et en export "
            f"(transbordement plausible) : {sorted(common)[:5]}",
        )


def validate_shift_report_structure(shift: RawShiftReport, report: ValidationReport):
    """Vérifie qu'un rapport de shift contient bien l'en-tête de table grues attendu."""
    header_found = any(
        row and any(str(c).strip().startswith("Portiques") for c in row if c is not None)
        for row in shift.rows[:10]
    )
    if not header_found:
        report.add(
            Severity.ERROR,
            f"Shift {shift.shift_num}",
            "En-tête de table grues ('Portiques') introuvable dans les 10 premières lignes.",
        )
    else:
        report.add(Severity.INFO, f"Shift {shift.shift_num}", "Structure de table grues détectée.")


def validate_all(inputs: AllInputs) -> ValidationReport:
    """Exécute toutes les validations sur l'ensemble des fichiers chargés."""
    logger.info("Démarrage de la validation complète des données importées.")
    report = ValidationReport()

    for shift in inputs.shift_reports.values():
        validate_shift_report_structure(shift, report)

    for masteryd in (inputs.import_masteryd, inputs.export_masteryd):
        validate_masteryd_columns(masteryd, report)
        validate_mandatory_values(masteryd, report)
        validate_container_number_format(masteryd, report)
        validate_duplicate_containers(masteryd, report)
        validate_dates(masteryd, report)

    validate_cross_file_duplicates(inputs.import_masteryd, inputs.export_masteryd, report)

    logger.info("Validation terminée : %s", report.summary())
    return report
