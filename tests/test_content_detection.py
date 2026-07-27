"""tests/test_content_detection.py — Tests de la découverte de fichiers PAR
CONTENU (src.import_data), indépendamment de tout nom de fichier."""

from datetime import time as dtime

import pytest

from src.import_data import (
    detect_masteryd_direction,
    detect_shift_number,
    looks_like_masteryd,
    looks_like_shift_report,
)


class TestLooksLikeShiftReport:
    def test_detects_portiques_header(self):
        rows = [
            ("ANYTHING", None, None),
            ("Portiques ", "Navire", "Total moves"),
        ]
        assert looks_like_shift_report(rows) is True

    def test_rejects_unrelated_content(self):
        rows = [("foo", "bar"), ("baz", "qux")]
        assert looks_like_shift_report(rows) is False

    def test_case_and_accent_insensitive_enough(self):
        rows = [("PORTIQUES ", None)]
        assert looks_like_shift_report(rows) is True


class TestLooksLikeMasteryd:
    def test_detects_required_columns_regardless_of_order(self):
        header = ("EXPLOITANT EN COURS", "N", "Nø CONTENEUR", "AUTRE COLONNE")
        assert looks_like_masteryd(header) is True

    def test_rejects_missing_column(self):
        header = ("N", "Nø CONTENEUR", "AUTRE COLONNE")  # pas d'exploitant
        assert looks_like_masteryd(header) is False

    def test_rejects_unrelated_header(self):
        header = ("Date", "Montant", "Client")
        assert looks_like_masteryd(header) is False


class TestDetectMasterydDirection:
    HEADER = ("N", "Nø CONTENEUR", "CODE MVT", "EXP IMP TRB", "EXPLOITANT EN COURS")

    def test_detects_import_from_majority_i(self):
        rows = [(1, "X1", "DEBA", "I", "AKN")] * 5 + [(2, "X2", "DEBA", "E", "AKN")]
        result = detect_masteryd_direction(self.HEADER, rows)
        assert result == "IMPORT"

    def test_detects_export_from_majority_e(self):
        rows = [(1, "X1", "EMBA", "E", "AKN")] * 5 + [(2, "X2", "EMBA", "I", "AKN")]
        result = detect_masteryd_direction(self.HEADER, rows)
        assert result == "EXPORT"

    def test_returns_none_when_column_absent(self):
        header_no_dir = ("N", "Nø CONTENEUR", "EXPLOITANT EN COURS")
        result = detect_masteryd_direction(header_no_dir, [(1, "X1", "AKN")])
        assert result is None

    def test_returns_none_when_no_values(self):
        rows = [(1, "X1", "DEBA", None, "AKN")]
        result = detect_masteryd_direction(self.HEADER, rows)
        assert result is None

    def test_works_regardless_of_filename_implication(self):
        """Le nom du fichier pourrait dire 'EXPORT' mais le contenu dit IMPORT :
        le contenu doit toujours gagner (c'est le but de cette fonction)."""
        rows = [(1, "X1", "DEBA", "I", "AKN")] * 10
        result = detect_masteryd_direction(self.HEADER, rows)
        assert result == "IMPORT"


class TestDetectShiftNumber:
    def test_detects_shift_1(self):
        rows = [("SHIFT 1",), ("other",)]
        assert detect_shift_number(rows) == 1

    def test_detects_shift_2_no_space(self):
        rows = [("SHIFT2",)]
        assert detect_shift_number(rows) == 2

    def test_detects_french_eme_shift(self):
        rows = [("3eme shift",)]
        assert detect_shift_number(rows) == 3

    def test_returns_none_when_absent(self):
        rows = [("nothing relevant here",), (None, "still nothing")]
        assert detect_shift_number(rows) is None
