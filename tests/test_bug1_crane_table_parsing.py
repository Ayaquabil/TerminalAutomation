"""
tests/test_bug1_crane_table_parsing.py

Test de non-régression pour BUG 1 :
La table grues des rapports de shift peut contenir des lignes vides entre les grues
(ou une ligne de total intercalée). Le parser doit ignorer ces lignes vides et lire
correctement toutes les grues du tableau, même avec 4 grues (P1..P4).

Cas testé : table avec une ligne vide entre P2 et P3, simulant un fichier réel
où une ligne vide de séparation était présente, faisant croire au parser que
la table se terminait après P2 (avec l'ancien code limité à len(CRANE_IDS)+2 lignes).
"""
from datetime import datetime, time as dtime

import pytest

from src.cleaning import _parse_crane_table, CraneRow


def _r(crane_id, vessel, doc, foc, imp=0, exp=0):
    """Construit une ligne de table grues (même structure que les vraies données)."""
    # Ordre : crane_id(0), vessel(1), ?(2), import_moves(3), export_moves(4), doc(5), foc(6), obs(7)
    return [crane_id, vessel, None, imp, exp, doc, foc, None]


class TestParseCraneTableWithBlankLines:
    """BUG 1 — Lignes vides intercalées dans la table des grues."""

    HEADER_ROW = [
        "Portiques", "Navire", "ISO", "Import", "Export", "DOC", "FOC", "Observations"
    ]
    SUBHEADER = [None, None, None, "Déba", "Emba", "Début", "Fin", None]

    def _build_rows(self, crane_data_rows, blank_after_index=None):
        """Assemble les lignes comme un vrai fichier Excel : en-tête + sous-en-tête + grues (+ vides)."""
        rows = [self.HEADER_ROW, self.SUBHEADER]
        for i, row in enumerate(crane_data_rows):
            rows.append(row)
            if blank_after_index is not None and i == blank_after_index:
                rows.append([None] * 8)  # ligne vide intercalée
        return rows

    def test_reads_all_cranes_without_blank_lines(self):
        """Sans lignes vides : toutes les grues sont lues."""
        crane_rows_input = [
            _r("P1", "MASTERY D", dtime(7, 0),  dtime(14, 0), imp=100),
            _r("P2", "MASTERY D", dtime(7, 5),  dtime(14, 5), imp=120),
            _r("P3", "MASTERY D", dtime(11, 30), dtime(14, 34), imp=80),
            _r("P4", "MASTERY D", dtime(15, 5), dtime(22, 35), exp=60),
        ]
        rows = self._build_rows(crane_rows_input)
        result = _parse_crane_table(rows, shift_num=1)
        assert len(result) == 4
        crane_ids = [r.crane_id for r in result]
        assert set(crane_ids) == {"P1", "P2", "P3", "P4"}

    def test_reads_all_cranes_with_blank_line_after_p2(self):
        """
        BUG 1 REGRESSION TEST : avec une ligne vide entre P2 et P3,
        l'ancien code (arrêt après len(CRANE_IDS)+2 lignes) ratait P3 et P4.
        Après fix, toutes les 4 grues doivent être lues.
        """
        crane_rows_input = [
            _r("P1", "MASTERY D", dtime(7, 0),  dtime(14, 0), imp=100),
            _r("P2", "MASTERY D", dtime(7, 5),  dtime(14, 5), imp=120),
            # blank après index 1 (entre P2 et P3)
            _r("P3", "MASTERY D", dtime(11, 30), dtime(14, 34), imp=80),
            _r("P4", "MASTERY D", dtime(15, 5), dtime(22, 35), exp=60),
        ]
        rows = self._build_rows(crane_rows_input, blank_after_index=1)
        result = _parse_crane_table(rows, shift_num=1)
        assert len(result) == 4, (
            f"BUG 1 RÉGRESSION : attendu 4 grues, obtenu {len(result)} : "
            f"{[r.crane_id for r in result]}"
        )
        crane_ids = [r.crane_id for r in result]
        assert "P3" in crane_ids, "P3 manquante après la ligne vide"
        assert "P4" in crane_ids, "P4 manquante après la ligne vide"

    def test_reads_all_cranes_with_blank_line_after_p1(self):
        """Ligne vide après P1 — P2, P3, P4 doivent quand même être lues."""
        crane_rows_input = [
            _r("P1", "MASTERY D", dtime(7, 0),  dtime(14, 0), imp=100),
            # blank après index 0
            _r("P2", "MASTERY D", dtime(7, 5),  dtime(14, 5), imp=120),
            _r("P3", "MASTERY D", dtime(11, 30), dtime(14, 34), imp=80),
            _r("P4", "MASTERY D", dtime(15, 5), dtime(22, 35), exp=60),
        ]
        rows = self._build_rows(crane_rows_input, blank_after_index=0)
        result = _parse_crane_table(rows, shift_num=2)
        assert len(result) == 4
        assert {r.crane_id for r in result} == {"P1", "P2", "P3", "P4"}

    def test_stops_at_non_crane_row_after_blank(self):
        """Une ligne non-vide avec un ID inconnu stoppe bien la lecture."""
        crane_rows_input = [
            _r("P1", "MASTERY D", dtime(7, 0),  dtime(14, 0), imp=100),
            _r("P2", "MASTERY D", dtime(7, 5),  dtime(14, 5), imp=120),
        ]
        rows = [self.HEADER_ROW, self.SUBHEADER]
        rows += [_r("P1", "MASTERY D", dtime(7, 0), dtime(14, 0), imp=100)]
        rows += [_r("P2", "MASTERY D", dtime(7, 5), dtime(14, 5), imp=120)]
        rows += [["TOTAL", None, None, 220, 0, None, None, None]]  # ligne TOTAL → doit stopper
        result = _parse_crane_table(rows, shift_num=3)
        assert len(result) == 2  # seules P1 et P2 lues

    def test_7_sessions_p3_across_3_shifts(self):
        """
        Test de bout-en-bout BUG 1 : 7 sessions pour P3 réparties sur 3 shifts.
        Shift 1 : P3 a 2 sessions (deux lignes dans la table)
        Shift 2 : P3 a 3 sessions
        Shift 3 : P3 a 2 sessions
        Total attendu : 7 CraneRow pour P3, triées chronologiquement.
        """
        from src.cleaning import CleanedShiftReport
        from src.merge import merge_crane_sessions

        sessions_p3_s1 = [
            _r("P3", "MASTERY D", dtime(11, 30), dtime(14, 34), imp=40),
            _r("P3", "MASTERY D", dtime(15, 5), dtime(22, 35), imp=50),
        ]
        sessions_p3_s2 = [
            _r("P3", "MASTERY D", dtime(7, 30), dtime(14, 33), imp=60),
            _r("P3", "MASTERY D", dtime(15, 19), dtime(22, 35), imp=55),
            _r("P3", "MASTERY D", dtime(23, 19), dtime(4, 20), imp=30),
        ]
        sessions_p3_s3 = [
            _r("P3", "MASTERY D", dtime(7, 26), dtime(14, 41), imp=45),
            _r("P3", "MASTERY D", dtime(15, 27), dtime(19, 11), imp=35),
        ]

        def make_shift(shift_num, date, crane_rows_raw):
            rows = [
                ["Portiques", "Navire", "ISO", "Import", "Export", "DOC", "FOC", "Obs"],
                [None, None, None, "Déba", "Emba", "Début", "Fin", None],
            ] + crane_rows_raw
            from src.import_data import RawShiftReport
            from pathlib import Path
            raw = RawShiftReport(
                shift_num=shift_num,
                file_path=Path(f"dummy_shift_{shift_num}.xlsx"),
                sheet_title=f"Shift{shift_num}",
                rows=rows,
            )
            from src.cleaning import clean_shift_report
            cleaned = clean_shift_report(raw)
            cleaned.shift_date = date
            return cleaned

        cleaned_shifts = {
            1: make_shift(1, datetime(2026, 6, 21), sessions_p3_s1),
            2: make_shift(2, datetime(2026, 6, 22), sessions_p3_s2),
            3: make_shift(3, datetime(2026, 6, 23), sessions_p3_s3),
        }

        sessions = merge_crane_sessions(cleaned_shifts, target_vessel_normalized="MASTERYD")
        p3 = sessions.get("P3", [])
        assert len(p3) == 7, (
            f"BUG 1 RÉGRESSION : 7 sessions attendues pour P3, "
            f"obtenu {len(p3)} sessions"
        )
        # Vérification ordre chronologique
        for i in range(len(p3) - 1):
            assert p3[i].commenced <= p3[i + 1].commenced, (
                f"Sessions P3 non triées chronologiquement : "
                f"{p3[i].commenced} > {p3[i+1].commenced}"
            )
        # Session 5 doit traverser minuit (shift 2, 23:19 → 04:20 du lendemain)
        s5 = p3[4]  # 5ème session (index 4)
        assert s5.completed > s5.commenced, "Session traversant minuit mal calculée"
        assert s5.completed.day > s5.commenced.day or s5.completed.date() > s5.commenced.date(), \
            "La 5ème session de P3 devrait traverser minuit"
