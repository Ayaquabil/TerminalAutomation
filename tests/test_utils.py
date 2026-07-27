"""tests/test_utils.py — Tests unitaires des fonctions utilitaires génériques."""

from datetime import datetime, time as dtime, timedelta

import pytest

from src.utils import (
    excel_time_to_dt,
    is_valid_container_number,
    iso_size_category,
    normalize_container_number,
    normalize_vessel_name,
    sanitize_filename,
    to_bool_flag,
    to_int,
    trim,
    vessel_matches,
    clean_vessel_name,
)


class TestNormalizeVesselName:
    def test_handles_space_variants(self):
        assert normalize_vessel_name("MASTERY D") == "MASTERYD"
        assert normalize_vessel_name("MASTERYD") == "MASTERYD"
        assert normalize_vessel_name("mastery d") == "MASTERYD"
        assert normalize_vessel_name("  mastery   d  ") == "MASTERYD"

    def test_none_and_empty(self):
        assert normalize_vessel_name(None) == ""
        assert normalize_vessel_name("") == ""

    def test_vessel_matches(self):
        assert vessel_matches("MASTERY D", "MASTERYD")
        assert vessel_matches("mastery d", "MASTERYD")
        assert not vessel_matches("NAVIOS AZURE", "MASTERYD")

    def test_strips_operator_prefixes(self):
        assert normalize_vessel_name("AKPERSEUS") == "PERSEUS"
        assert normalize_vessel_name("AK PERSUS") == "PERSUS"
        assert normalize_vessel_name("CMA CGM JANE") == "JANE"
        assert normalize_vessel_name("MSL JANE") == "JANE"
        assert vessel_matches("AKPERSEUS", "PERSEUS")
        assert vessel_matches("AK PERSUS", "PERSUS")


class TestCleanVesselName:
    def test_clean_operator_prefixes(self):
        assert clean_vessel_name("AKPERSEUS") == "PERSEUS"
        assert clean_vessel_name("AK PERSUS") == "PERSUS"
        assert clean_vessel_name("CMA CGM JANE") == "JANE"
        assert clean_vessel_name("BELITAKI") == "BELITAKI"
        assert clean_vessel_name(None) == ""
        assert clean_vessel_name("") == ""


class TestTrim:
    def test_strips_strings(self):
        assert trim("  hello  ") == "hello"

    def test_passes_through_non_strings(self):
        assert trim(42) == 42
        assert trim(None) is None


class TestToInt:
    def test_valid_conversions(self):
        assert to_int(5) == 5
        assert to_int(5.7) == 5
        assert to_int("5") == 5

    def test_invalid_returns_default(self):
        assert to_int(None) == 0
        assert to_int("") == 0
        assert to_int("abc") == 0
        assert to_int("abc", default=-1) == -1


class TestToBoolFlag:
    def test_int_flags(self):
        assert to_bool_flag(1) is True
        assert to_bool_flag(0) is False

    def test_bool_passthrough(self):
        assert to_bool_flag(True) is True
        assert to_bool_flag(False) is False

    def test_invalid_returns_false(self):
        assert to_bool_flag(None) is False
        assert to_bool_flag("abc") is False


class TestExcelTimeToDt:
    def test_time_object(self):
        base = datetime(2026, 6, 2)
        result = excel_time_to_dt(dtime(7, 19), base)
        assert result == datetime(2026, 6, 2, 7, 19)

    def test_timedelta_object(self):
        base = datetime(2026, 6, 2)
        result = excel_time_to_dt(timedelta(hours=14, minutes=32), base)
        assert result == datetime(2026, 6, 2, 14, 32)

    def test_string_hh_mm(self):
        base = datetime(2026, 6, 2)
        result = excel_time_to_dt("07:19", base)
        assert result == datetime(2026, 6, 2, 7, 19)

    def test_string_hh_mm_ss(self):
        base = datetime(2026, 6, 2)
        # Moins de 30 secondes -> arrondi inférieur
        result_inf = excel_time_to_dt("07:19:25", base)
        assert result_inf == datetime(2026, 6, 2, 7, 19)
        # 30 secondes ou plus -> arrondi supérieur
        result_sup = excel_time_to_dt("07:19:30", base)
        assert result_sup == datetime(2026, 6, 2, 7, 20)

    def test_none_returns_none(self):
        assert excel_time_to_dt(None, datetime(2026, 6, 2)) is None

    def test_invalid_string_returns_none(self):
        assert excel_time_to_dt("not a time", datetime(2026, 6, 2)) is None


class TestIsoSizeCategory:
    def test_20ft_codes(self):
        assert iso_size_category("22G0") == "20"
        assert iso_size_category("22G1") == "20"

    def test_40ft_codes(self):
        assert iso_size_category("45G1") == "40+"
        assert iso_size_category("45R1") == "40+"

    def test_none_and_empty(self):
        assert iso_size_category(None) == "?"
        assert iso_size_category("") == "?"


class TestContainerNumber:
    def test_valid_format(self):
        assert is_valid_container_number("BSIU8247479")
        assert is_valid_container_number("  caau2559764  ")  # trim + case-insensitive

    def test_invalid_format(self):
        assert not is_valid_container_number("BSI8247479")    # 3 lettres seulement
        assert not is_valid_container_number("BSIU824747")    # trop court
        assert not is_valid_container_number(None)
        assert not is_valid_container_number("")

    def test_normalize_container_number(self):
        assert normalize_container_number("  bsiu 8247479  ") == "BSIU8247479"
        assert normalize_container_number(None) == ""


class TestSanitizeFilename:
    def test_replaces_unsafe_chars(self):
        result = sanitize_filename("MASTERY D / TEST:01")
        assert "/" not in result
        assert ":" not in result
        assert " " not in result

    def test_none_returns_default(self):
        assert sanitize_filename(None) == "INCONNU"


class TestVesselMatches:
    def test_exact_match(self):
        assert vessel_matches("MASTERY D", "MASTERYD") is True

    def test_prefix_in_shift_longer(self):
        # "SEATRADE CHILE" dans le shift, "SEATRADE" extrait de l'ESCALE
        assert vessel_matches("SEATRADE CHILE", "SEATRADE") is True

    def test_prefix_in_target_longer(self):
        # "SEATRADE" dans le shift, "SEATRADECHILE" comme cible (cas inverse)
        assert vessel_matches("SEATRADE", "SEATRADECHILE") is True

    def test_completely_different_vessels_no_match(self):
        assert vessel_matches("CMA CGM TAGE", "SEATRADE") is False

    def test_short_prefix_no_false_positive(self):
        # "MSC" ne doit PAS matcher "MSCCECILIA" (préfixe trop court = 3 car < 4)
        assert vessel_matches("MSC", "MSCCECILIA") is False

    def test_none_returns_false(self):
        assert vessel_matches(None, "SEATRADE") is False
        assert vessel_matches("SEATRADE CHILE", "") is False

