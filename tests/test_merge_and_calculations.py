"""tests/test_merge_and_calculations.py — Tests unitaires de la fusion et des KPIs."""

from datetime import datetime, time as dtime

import pandas as pd
import pytest

from src.calculations import compute_all_kpis, compute_crane_productivity, compute_operator_breakdown
from src.cleaning import CleanedShiftReport, CraneRow
from src.merge import (
    CraneSession,
    MergedVesselDataset,
    build_merged_dataset,
    merge_crane_sessions,
    infer_escale_from_masteryd,
    infer_vessel_from_escale,
)


def make_crane_row(shift_num, crane_id, vessel, doc, foc, imp=0, exp=0):
    return CraneRow(
        shift_num=shift_num, crane_id=crane_id, vessel_raw=vessel,
        vessel_normalized="MASTERYD" if vessel and "master" in vessel.lower() else "",
        import_moves=imp, export_moves=exp, doc_raw=doc, foc_raw=foc, observations=None,
    )


class TestMergeCraneSessions:
    def test_filters_to_target_vessel_only(self):
        cleaned = {
            1: CleanedShiftReport(
                shift_num=1, shift_date=datetime(2026, 6, 2),
                crane_rows=[
                    make_crane_row(1, "P1", "NAVIOS AZURE", dtime(7, 0), dtime(14, 0)),
                    make_crane_row(1, "P4", "MASTERY D", dtime(7, 15), dtime(14, 32), imp=138),
                ],
            ),
        }
        sessions = merge_crane_sessions(cleaned, target_vessel_normalized="MASTERYD")
        # BUG A FIX : le dict est maintenant dynamique — P1 (autre navire) est absent
        assert len(sessions.get("P1", [])) == 0
        assert len(sessions.get("P4", [])) == 1
        assert sessions["P4"][0].import_moves == 138

    def test_handles_midnight_crossing(self):
        cleaned = {
            3: CleanedShiftReport(
                shift_num=3, shift_date=datetime(2026, 6, 2),
                crane_rows=[
                    make_crane_row(3, "P3", "mastery d", dtime(23, 18), dtime(4, 45), exp=50),
                ],
            ),
        }
        sessions = merge_crane_sessions(cleaned, target_vessel_normalized="MASTERYD")
        session = sessions["P3"][0]
        assert session.commenced == datetime(2026, 6, 2, 23, 18)
        assert session.completed == datetime(2026, 6, 3, 4, 45)
        assert session.completed > session.commenced

    def test_ignores_inactive_crane(self):
        """DOC == FOC (00:00=00:00) signifie une grue non utilisée -> pas de session."""
        cleaned = {
            1: CleanedShiftReport(
                shift_num=1, shift_date=datetime(2026, 6, 2),
                crane_rows=[
                    make_crane_row(1, "P1", "MASTERY D", dtime(0, 0), dtime(0, 0)),
                ],
            ),
        }
        sessions = merge_crane_sessions(cleaned, target_vessel_normalized="MASTERYD")
        # BUG A FIX : grue inactive (DOC=FOC=00:00) → session ignorée → clé absente du dict
        assert len(sessions.get("P1", [])) == 0

    def test_no_shift_date_skips_session(self):
        cleaned = {
            1: CleanedShiftReport(
                shift_num=1, shift_date=None,
                crane_rows=[make_crane_row(1, "P1", "MASTERY D", dtime(7, 0), dtime(14, 0))],
            ),
        }
        sessions = merge_crane_sessions(cleaned, target_vessel_normalized="MASTERYD")
        # BUG A FIX : shift_date=None → session ignorée → clé absente du dict
        assert len(sessions.get("P1", [])) == 0


class TestComputeOperatorBreakdown:
    def test_aggregates_by_operator(self):
        df = pd.DataFrame([
            {"operator": "AKN", "is_full": True, "is_empty": False, "iso_size_category": "20"},
            {"operator": "AKN", "is_full": True, "is_empty": False, "iso_size_category": "40+"},
            {"operator": "AKN", "is_full": False, "is_empty": True, "iso_size_category": "20"},
            {"operator": "CMA", "is_full": True, "is_empty": False, "iso_size_category": "20"},
        ])
        result = compute_operator_breakdown(df)
        assert result["AKN"] == {"full_20": 1, "full_40": 1, "empty_20": 1, "empty_40": 0}
        assert result["CMA"] == {"full_20": 1, "full_40": 0, "empty_20": 0, "empty_40": 0}

    def test_empty_dataframe_returns_empty_dict(self):
        assert compute_operator_breakdown(pd.DataFrame()) == {}


class TestComputeCraneProductivity:
    def test_computes_rates_correctly(self):
        sessions = {
            "P4": [
                CraneSession(shift_num=1, commenced=datetime(2026, 6, 2, 7, 0),
                              completed=datetime(2026, 6, 2, 9, 0), import_moves=20, export_moves=10),
            ],
            "P1": [],
        }
        result = compute_crane_productivity(sessions)
        assert "P1" not in result  # pas de session -> pas d'entrée
        p4 = result["P4"]
        assert p4.total_moves == 30
        assert p4.total_working_hours == 2.0
        assert p4.gross_moves_per_hour == 15.0


class TestComputeAllKpis:
    def test_cross_check_matches_when_consistent(self):
        df_import = pd.DataFrame([
            {"operator": "AKN", "is_full": True, "is_empty": False, "iso_size_category": "20",
             "dangerous_flag": False, "reefer_flag": False, "oversized_flag": False,
             "iso_type": "22G0", "movement_code": "DISCHARGE", "crane_pool": "P4",
             "entry_datetime": datetime(2026, 6, 2, 10, 0)},
        ])
        merged = MergedVesselDataset(
            vessel_name="MASTERY D", escale="MASTERYD_01062026",
            crane_sessions={
                "P4": [CraneSession(shift_num=1, commenced=datetime(2026, 6, 2, 7, 0),
                                     completed=datetime(2026, 6, 2, 8, 0),
                                     import_moves=1, export_moves=0)],
            },
            containers_import=df_import, containers_export=pd.DataFrame(),
        )
        kpi = compute_all_kpis(merged)
        assert kpi.total_import_containers == 1
        assert kpi.cross_check_matches is True

    def test_cross_check_fails_when_inconsistent(self):
        df_import = pd.DataFrame([
            {"operator": "AKN", "is_full": True, "is_empty": False, "iso_size_category": "20",
             "dangerous_flag": False, "reefer_flag": False, "oversized_flag": False,
             "iso_type": "22G0", "movement_code": "DISCHARGE", "crane_pool": "P4",
             "entry_datetime": datetime(2026, 6, 2, 10, 0)},
        ])
        merged = MergedVesselDataset(
            vessel_name="MASTERY D", escale="MASTERYD_01062026",
            crane_sessions={
                "P4": [CraneSession(shift_num=1, commenced=datetime(2026, 6, 2, 7, 0),
                                     completed=datetime(2026, 6, 2, 8, 0),
                                     import_moves=5, export_moves=0)],  # 5 != 1 conteneur
            },
            containers_import=df_import, containers_export=pd.DataFrame(),
        )
        kpi = compute_all_kpis(merged)
        assert kpi.cross_check_matches is False


def test_crane_sessions_sorting_and_midnight():
    """Vérifie que les sessions de grue sont correctement triées chronologiquement et gèrent minuit."""
    cleaned = {
        1: CleanedShiftReport(
            shift_num=1, shift_date=datetime(2026, 6, 2),
            crane_rows=[make_crane_row(1, "P3", "MASTERY D", dtime(11, 30), dtime(14, 30), imp=10)]
        ),
        2: CleanedShiftReport(
            shift_num=2, shift_date=datetime(2026, 6, 2),
            crane_rows=[make_crane_row(2, "P3", "MASTERY D", dtime(23, 15), dtime(4, 30), imp=20)]
        ),
        3: CleanedShiftReport(
            shift_num=3, shift_date=datetime(2026, 6, 3),
            crane_rows=[make_crane_row(3, "P3", "MASTERY D", dtime(7, 10), dtime(12, 0), imp=30)]
        ),
    }
    sessions = merge_crane_sessions(cleaned, target_vessel_normalized="MASTERYD")
    p3_sessions = sessions["P3"]
    assert len(p3_sessions) == 3
    # Vérification du tri
    assert p3_sessions[0].commenced == datetime(2026, 6, 2, 11, 30)
    assert p3_sessions[1].commenced == datetime(2026, 6, 2, 23, 15)
    assert p3_sessions[1].completed == datetime(2026, 6, 3, 4, 30)  # Traversée de minuit
    assert p3_sessions[2].commenced == datetime(2026, 6, 3, 7, 10)


class TestInferenceFunctions:
    """AMÉLIORATION 2 — Tests unitaires pour l'inférence d'escale et de navire."""

    def test_infer_escale_from_masteryd_majority(self):
        df_import = pd.DataFrame([
            {"escale": "BELITAKI_24062026"},
            {"escale": "BELITAKI_24062026"},
        ])
        df_export = pd.DataFrame([
            {"escale": "BELITAKI_24062026"},
            {"escale": "AUTRE_ESCALE"},
        ])
        res = infer_escale_from_masteryd(df_import, df_export)
        assert res == "BELITAKI_24062026"

    def test_infer_escale_empty_returns_none(self):
        assert infer_escale_from_masteryd(pd.DataFrame(), pd.DataFrame()) is None

    def test_infer_vessel_exact_match(self):
        cleaned_shifts = {
            1: CleanedShiftReport(
                shift_num=1, shift_date=datetime(2026, 6, 2),
                crane_rows=[
                    make_crane_row(1, "P1", "MASTERY D", dtime(7, 0), dtime(14, 0)),
                ]
            )
        }
        # escale_filter contient 'MASTERYD'
        res = infer_vessel_from_escale("MASTERYD_01062026", cleaned_shifts)
        assert res == "MASTERY D"

    def test_infer_vessel_fuzzy_match(self):
        cleaned_shifts = {
            1: CleanedShiftReport(
                shift_num=1, shift_date=datetime(2026, 6, 2),
                crane_rows=[
                    make_crane_row(1, "P1", "OCEANIC STAR", dtime(7, 0), dtime(14, 0)),
                ]
            )
        }
        # escale_filter contient 'OCEANIC' -> fuzzy match ratio élevé
        res = infer_vessel_from_escale("OCEANIC_STAR_123", cleaned_shifts)
        assert res == "OCEANIC STAR"

    def test_infer_vessel_config_fallback(self):
        import config
        # Aucun navire dans les shifts ne correspond à l'escale 'INCONNU'
        cleaned_shifts = {
            1: CleanedShiftReport(
                shift_num=1, shift_date=datetime(2026, 6, 2),
                crane_rows=[
                    make_crane_row(1, "P1", "AUTRE NAVIRE", dtime(7, 0), dtime(14, 0)),
                ]
            )
        }
        res = infer_vessel_from_escale("INCONNU_123", cleaned_shifts)
        # doit retomber sur le navire configuré (ex: MASTERY D)
        assert res == config.TARGET_VESSEL_NAME

    def test_infer_vessel_alphabetic_prefix_seatrade(self):
        """Cas réel SEATRADE CHILE : l'escale 'SEATRADE_09062026' doit matcher
        le navire 'SEATRADE CHILE' via le préfixe alphabétique 'SEATRADE'."""
        cleaned_shifts = {
            1: CleanedShiftReport(
                shift_num=1, shift_date=datetime(2026, 6, 5),
                crane_rows=[
                    make_crane_row(1, "P3", "SEATRADE CHILE", dtime(8, 9), dtime(14, 30), imp=128),
                    make_crane_row(1, "P4", "CC OSAKA", dtime(7, 0), dtime(14, 0), imp=50),
                ]
            )
        }
        res = infer_vessel_from_escale("SEATRADE_09062026", cleaned_shifts)
        assert res == "SEATRADE CHILE"

    def test_infer_vessel_belitaki_prefix(self):
        """Cas BELITAKI : l'escale 'BELITAKI_24062026' doit matcher le navire
        'BELITAKI' (ou similaire) via le préfixe alphabétique."""
        cleaned_shifts = {
            1: CleanedShiftReport(
                shift_num=1, shift_date=datetime(2026, 6, 21),
                crane_rows=[
                    make_crane_row(1, "P3", "BELITAKI", dtime(23, 49), dtime(5, 18), imp=50),
                ]
            )
        }
        res = infer_vessel_from_escale("BELITAKI_24062026", cleaned_shifts)
        assert res == "BELITAKI"

    def test_infer_vessel_no_escale_falls_back_to_shifts(self):
        """Sans escale, le navire le plus fréquent des shifts doit être retourné."""
        cleaned_shifts = {
            1: CleanedShiftReport(
                shift_num=1, shift_date=datetime(2026, 6, 2),
                crane_rows=[
                    make_crane_row(1, "P1", "NORDIC AURORA", dtime(7, 0), dtime(14, 0), imp=10),
                    make_crane_row(1, "P2", "NORDIC AURORA", dtime(7, 0), dtime(14, 0), imp=20),
                    make_crane_row(1, "P3", "OTHER VESSEL", dtime(7, 0), dtime(14, 0), imp=5),
                ]
            )
        }
        res = infer_vessel_from_escale(None, cleaned_shifts)
        assert res == "NORDIC AURORA"




