"""tests/test_cleaning.py — Tests unitaires du nettoyage de données."""

from datetime import datetime, time as dtime

import pandas as pd
import pytest

from src.cleaning import (
    CleanedShiftReport,
    _entry_datetime,
    _parse_crane_table,
    _parse_general_delays,
    clean_masteryd,
)
from src.import_data import RawMasterydFile


def make_masteryd(direction: str, header: tuple, rows: list) -> RawMasterydFile:
    return RawMasterydFile(direction=direction, file_path=None, header=header, rows=rows)


class TestEntryDatetime:
    def test_valid_date_and_time(self):
        result = _entry_datetime(20260602, 153038)
        assert result == datetime(2026, 6, 2, 15, 30, 38)

    def test_date_only(self):
        result = _entry_datetime(20260602, None)
        assert result == datetime(2026, 6, 2)

    def test_invalid_date_returns_none(self):
        assert _entry_datetime(None, 153038) is None
        assert _entry_datetime("not a date", 153038) is None


class TestCleanMasteryd:
    HEADER = (
        "N", "Nø CONTENEUR", "CODE MVT", "EXP IMP TRB", "V/P", "TYPE ISO",
        "Nø SCELLE ARMATEUR", "TAG FRIGO", "TAG DANG 0/1", "TAG HG 0/1",
        "EXPLOITANT EN COURS", "ESCALE", "CODE PORT DECHA", "AVARIES RESERVES",
        "DATE DE SAISIE", "HEURE DE SAISIE", "POOL",
    )

    def _row(self, **overrides):
        base = {
            "N": 1, "Nø CONTENEUR": "BSIU8247479", "CODE MVT": "EMBA",
            "EXP IMP TRB": "E", "V/P": "V", "TYPE ISO": "22G0",
            "Nø SCELLE ARMATEUR": None, "TAG FRIGO": 0, "TAG DANG 0/1": 0,
            "TAG HG 0/1": 0, "EXPLOITANT EN COURS": "AKN",
            "ESCALE": "MASTERYD_01062026", "CODE PORT DECHA": "ESVLC",
            "AVARIES RESERVES": None, "DATE DE SAISIE": 20260602,
            "HEURE DE SAISIE": 153038, "POOL": "P4",
        }
        base.update(overrides)
        return tuple(base[col] for col in self.HEADER)

    def test_basic_cleaning(self):
        masteryd = make_masteryd("EXPORT", self.HEADER, [self._row()])
        df = clean_masteryd(masteryd)
        assert len(df) == 1
        assert df.iloc[0]["container_number"] == "BSIU8247479"
        assert df.iloc[0]["movement_code"] == "LOAD"  # EMBA -> LOAD
        assert df.iloc[0]["is_empty"] is True or df.iloc[0]["is_empty"] == True
        assert df.iloc[0]["is_full"] in (False, 0)
        assert df.iloc[0]["iso_size_category"] == "20"
        assert df.iloc[0]["operator"] == "AKN"
        assert df.iloc[0]["direction"] == "EXPORT"

    def test_full_container_flagged_correctly(self):
        masteryd = make_masteryd("IMPORT", self.HEADER,
                                   [self._row(**{"V/P": "P", "TYPE ISO": "45G1"})])
        df = clean_masteryd(masteryd)
        assert df.iloc[0]["is_full"] == True
        assert df.iloc[0]["is_empty"] == False
        assert df.iloc[0]["iso_size_category"] == "40+"

    def test_reefer_and_dangerous_flags(self):
        masteryd = make_masteryd("IMPORT", self.HEADER,
                                   [self._row(**{"TAG FRIGO": 1, "TAG DANG 0/1": 1})])
        df = clean_masteryd(masteryd)
        assert bool(df.iloc[0]["reefer_flag"]) is True
        assert bool(df.iloc[0]["dangerous_flag"]) is True

    def test_container_number_normalized(self):
        masteryd = make_masteryd("IMPORT", self.HEADER,
                                   [self._row(**{"Nø CONTENEUR": "  bsiu 8247479  "})])
        df = clean_masteryd(masteryd)
        assert df.iloc[0]["container_number"] == "BSIU8247479"

    def test_entry_datetime_computed(self):
        masteryd = make_masteryd("IMPORT", self.HEADER, [self._row()])
        df = clean_masteryd(masteryd)
        assert df.iloc[0]["entry_datetime"] == datetime(2026, 6, 2, 15, 30, 38)


class TestParseCraneTable:
    def test_parses_basic_crane_rows(self):
        rows = [
            (None,) * 10,
            ("Portiques ", "Navire", None, "Total moves", None, "DOC", "FOC", "Observations"),
            (None, None, None, "Import", "Export", None, None, None),
            ("P1", "NAVIOS AZURE", None, 0, 0, dtime(0, 0), dtime(0, 0), None),
            ("P4", "MASTERY D", None, 138, 0, dtime(7, 15), dtime(14, 32), "obs"),
        ]
        result = _parse_crane_table(rows, shift_num=1)
        assert len(result) == 2
        p4 = next(r for r in result if r.crane_id == "P4")
        assert p4.vessel_raw == "MASTERY D"
        assert p4.vessel_normalized == "MASTERYD"
        assert p4.import_moves == 138
        assert p4.export_moves == 0

    def test_missing_header_returns_empty(self):
        rows = [(None,) * 5 for _ in range(5)]
        result = _parse_crane_table(rows, shift_num=1)
        assert result == []


class TestParseGeneralDelays:
    def test_parses_valid_delay(self):
        rows = [
            (None,) * 6,
            ("Nature de retard", None, "Début", "Fin", "Durée", "Observations"),
            ("Congestion", None, dtime(23, 0), dtime(1, 0), None, "obs texte"),
        ]
        result = _parse_general_delays(rows, shift_num=3)
        assert len(result) == 1
        assert result[0].label == "Congestion"
        assert result[0].duration_minutes == 120  # 23:00 -> 01:00 (+1j) = 2h

    def test_skips_zero_duration_rows(self):
        rows = [
            (None,) * 6,
            ("Nature de retard", None, "Début", "Fin", "Durée", "Observations"),
            (None, None, dtime(0, 0), dtime(0, 0), None, None),
        ]
        result = _parse_general_delays(rows, shift_num=1)
        assert result == []

    def test_missing_header_returns_empty(self):
        rows = [(None,) * 5 for _ in range(5)]
        result = _parse_general_delays(rows, shift_num=1)
        assert result == []
