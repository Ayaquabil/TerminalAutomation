"""
src/cleaning.py — Nettoyage et structuration des données brutes.

Deux familles de données à nettoyer :
1. IMPORT/EXPORT MASTERYD : listes de conteneurs (une ligne = un conteneur)
   -> normalisation en DataFrame pandas avec colonnes typées.
2. Rapports de shift : tables "une ligne = une grue" + table de retards
   généraux -> normalisation en listes de dicts typés.

Toutes les fonctions sont pures (n'écrivent rien sur disque) et reçoivent/
retournent des structures en mémoire, pour rester testables unitairement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd

import config
from src.import_data import RawMasterydFile, RawShiftReport
from src.logger import get_logger
from src.utils import (
    excel_time_to_dt,
    iso_size_category,
    normalize_container_number,
    normalize_vessel_name,
    to_bool_flag,
    to_int,
    trim,
)

logger = get_logger("cleaning")

# Renommage des colonnes sources (noms réels du fichier) vers des noms
# Python normalisés (snake_case), pour le DataFrame de conteneurs.
MASTERYD_COLUMN_RENAME = {
    "N": "seq_no",
    "Nø CONTENEUR": "container_number",
    "CODE MVT": "movement_code",
    "EXP IMP TRB": "direction_code",     # 'I' import, 'E' export, 'T' transbordement
    "V/P": "full_empty_code",            # 'P' plein (full), 'V' vide (empty)
    "TYPE ISO": "iso_type",
    "Nø SCELLE ARMATEUR": "seal_number",
    "TAG FRIGO": "reefer_flag",
    "TAG DANG 0/1": "dangerous_flag",
    "TAG HG 0/1": "oversized_flag",
    "EXPLOITANT EN COURS": "operator",
    "ESCALE": "escale",
    "CODE PORT DECHA": "port_code",      # EXPORT : port de déchargement (destination)
    "CODE PORT CHAR": "port_code",       # IMPORT : port de chargement (origine)
    "AVARIES RESERVES": "damage_remarks",
    "DATE DE SAISIE": "entry_date_raw",
    "HEURE DE SAISIE": "entry_time_raw",
    "POOL": "crane_pool",
}

MOVEMENT_CODE_LABELS = {
    "DEBA": "DISCHARGE",     # Débarquement
    "EMBA": "LOAD",          # Embarquement
}


def _entry_datetime(date_raw, time_raw) -> Optional[datetime]:
    """Combine DATE DE SAISIE (AAAAMMJJ) + HEURE DE SAISIE (H[H]MMSS) en datetime."""
    if date_raw is None:
        return None
    try:
        date_str = str(int(date_raw))
        year, month, day = int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])
        base = datetime(year, month, day)
    except (ValueError, IndexError, TypeError):
        return None

    if time_raw is None:
        return base
    try:
        time_str = str(int(time_raw)).zfill(6)
        hour, minute, second = int(time_str[:2]), int(time_str[2:4]), int(time_str[4:6])
        return base.replace(hour=hour % 24, minute=minute, second=second)
    except (ValueError, IndexError, TypeError):
        return base


def map_columns_by_keywords(header: list) -> dict[str, str]:
    """Cartographie dynamiquement les noms de colonnes réels vers les noms logiques."""
    import re
    header_clean = [str(h).strip() if h else "" for h in header]
    
    keywords_map = {
        "container_number": ["CONTENEUR", "CONTAINER", "Nø CONTENEUR"],
        "movement_code": ["MVT", "MOVEMENT", "CODE MVT"],
        "direction_code": ["EXP IMP", "EXP IMP TRB", "DIRECTION", "FLUX", "IMP EXP", "TRB"],
        "full_empty_code": ["V/P", "FULL", "EMPTY", "PLEIN", "VIDE"],
        "iso_type": ["ISO", "TYPE ISO"],
        "seal_number": ["SCELLE", "SEAL", "Nø SCELLE"],
        "reefer_flag": ["FRIGO", "REEFER", "TAG FRIGO"],
        "dangerous_flag": ["DANG", "HAZARD", "DANGEREUX", "TAG DANG"],
        "oversized_flag": ["HG", "OVERSIZED", "HORS GABARIT", "TAG HG"],
        "operator": ["EXPLOITANT", "OPERATOR", "ARMATEUR"],
        "escale": ["ESCALE", "VOYAGE", "TRIP"],
        "damage_remarks": ["AVARIES", "DAMAGE", "RESERVES"],
        "entry_date_raw": ["DATE DE SAISIE", "DATE SAISIE", "DATE"],
        "entry_time_raw": ["HEURE DE SAISIE", "HEURE SAISIE", "HEURE", "TIME"],
        "crane_pool": ["POOL"],
    }
    
    mapping = {}
    for original_name in header_clean:
        if not original_name:
            continue
        orig_upper = original_name.upper()
        # Test exact match first, then partial match
        matched = False
        for logical_name, kw_list in keywords_map.items():
            if any(kw.upper() == orig_upper for kw in kw_list):
                mapping[original_name] = logical_name
                matched = True
                break
        if not matched:
            for logical_name, kw_list in keywords_map.items():
                if any(kw.upper() in orig_upper for kw in kw_list):
                    mapping[original_name] = logical_name
                    matched = True
                    break
        # Port code specific check
        if not matched and "PORT" in orig_upper:
            mapping[original_name] = "port_code"

    return mapping


def clean_masteryd(masteryd: RawMasterydFile) -> pd.DataFrame:
    """
    Transforme un RawMasterydFile en DataFrame pandas nettoyé et typé de manière 100% dynamique.
    """
    logger.info("Nettoyage du fichier %s MASTERYD (%d lignes)", masteryd.direction, len(masteryd.rows))

    header = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(masteryd.header)]
    df = pd.DataFrame(masteryd.rows, columns=header)

    rename_map = map_columns_by_keywords(header)
    df = df.rename(columns=rename_map)

    # Assurer que les colonnes indispensables existent
    required = ["container_number", "movement_code", "direction_code", "full_empty_code", "iso_type", "operator", "escale"]
    for col in required:
        if col not in df.columns:
            df[col] = None

    # Trim de toutes les colonnes texte
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(trim)

    df["container_number"] = df["container_number"].apply(normalize_container_number)
    df["movement_code"] = df["movement_code"].apply(
        lambda v: MOVEMENT_CODE_LABELS.get(str(v).strip().upper(), str(v).strip().upper()) if v else None
    )
    df["direction_code"] = df["direction_code"].apply(lambda v: str(v).strip().upper() if v else None)
    df["full_empty_code"] = df["full_empty_code"].apply(lambda v: str(v).strip().upper() if v else None)
    df["is_full"] = df["full_empty_code"] == "P"
    df["is_empty"] = df["full_empty_code"] == "V"

    df["iso_type"] = df["iso_type"].apply(lambda v: str(v).strip().upper() if v is not None else None)
    df["iso_size_category"] = df["iso_type"].apply(iso_size_category)
    df["iso_type_is_standard"] = df["iso_type"].apply(
        lambda v: bool(v) and v[0] in ("2", "4")
    )

    df["reefer_flag"] = df["reefer_flag"].apply(to_bool_flag)
    df["dangerous_flag"] = df["dangerous_flag"].apply(to_bool_flag)
    df["oversized_flag"] = df["oversized_flag"].apply(to_bool_flag)

    df["operator"] = df["operator"].apply(lambda v: str(v).strip().upper() if v else None)
    df["escale"] = df["escale"].apply(lambda v: str(v).strip() if v else None)
    df["crane_pool"] = df["crane_pool"].apply(lambda v: str(v).strip().upper() if v else None)

    if "damage_remarks" in df.columns:
        df["has_damage"] = df["damage_remarks"].apply(lambda v: bool(v) and str(v).strip() != "")
    else:
        df["has_damage"] = False

    df["entry_datetime"] = [
        _entry_datetime(d, t) for d, t in zip(df.get("entry_date_raw"), df.get("entry_time_raw"))
    ]

    df["direction"] = masteryd.direction

    n_unknown_iso = int((~df["iso_type_is_standard"]).sum())
    if n_unknown_iso:
        examples = df.loc[~df["iso_type_is_standard"], "iso_type"].unique()[:5].tolist()
        logger.warning(
            "%s MASTERYD : %d conteneur(s) avec un code ISO hors motif standard '2x'/'4x' : %s "
            "(classés en '%s' par défaut, à vérifier manuellement).",
            masteryd.direction, n_unknown_iso, examples, "40+",
        )

    logger.info(
        "%s MASTERYD nettoyé : %d conteneurs, %d colonnes.",
        masteryd.direction, len(df), len(df.columns),
    )
    return df


# ─────────────────────────────────────────────────────────────
# RAPPORTS DE SHIFT — table grues + table retards généraux
# ─────────────────────────────────────────────────────────────

@dataclass
class CraneRow:
    shift_num: int
    crane_id: str
    vessel_raw: Optional[str]
    vessel_normalized: str
    import_moves: int
    export_moves: int
    doc_raw: object
    foc_raw: object
    observations: Optional[str]
    restow_discharged: int = 0
    restow_loaded: int = 0
    hatch_cover_open: int = 0
    hatch_cover_close: int = 0


@dataclass
class GeneralDelayEntry:
    shift_num: int
    label: Optional[str]
    duration_minutes: float
    reason_text: Optional[str]


@dataclass
class CleanedShiftReport:
    shift_num: int
    shift_date: Optional[datetime]
    crane_rows: List[CraneRow] = field(default_factory=list)
    general_delays: List[GeneralDelayEntry] = field(default_factory=list)


def _find_row_index(rows, text: str, max_rows: int = 100) -> Optional[int]:
    """Index (0-based) de la première ligne dont une cellule contient `text` (insensible casse)."""
    text_lower = text.lower()
    for i, row in enumerate(rows[:max_rows]):
        for cell in row:
            if isinstance(cell, str) and text_lower in cell.strip().lower():
                return i
    return None


def _parse_crane_table(rows, shift_num: int) -> List[CraneRow]:
    header_idx = _find_row_index(rows, "Portiques")
    if header_idx is None:
        logger.error("Shift %s : en-tête 'Portiques' introuvable, table grues non lue.", shift_num)
        return []

    # Chercher la ligne de sous-en-tête (juste après 'Portiques')
    subheader_row = rows[header_idx + 1] if header_idx + 1 < len(rows) else None
    if not subheader_row:
        logger.error("Shift %s : sous-en-tête de la table grues introuvable.", shift_num)
        return []

    header_row = rows[header_idx]
    header_clean = [str(c).strip().upper() if c else "" for c in header_row]
    subheader_clean = [str(c).strip().upper() if c else "" for c in subheader_row]
    
    col_crane_id = -1
    col_vessel = -1
    col_import = -1
    col_export = -1
    col_doc = -1
    col_foc = -1
    col_obs = -1
    
    for idx in range(max(len(header_clean), len(subheader_clean))):
        h_text = header_clean[idx] if idx < len(header_clean) else ""
        s_text = subheader_clean[idx] if idx < len(subheader_clean) else ""
        combined_text = f"{h_text} {s_text}".strip()
        
        if not combined_text:
            continue
        if "PORTIQUE" in combined_text or "CRANE" in combined_text or "GRUE" in combined_text:
            col_crane_id = idx
        if "NAVIRE" in combined_text or "VESSEL" in combined_text or "SHIP" in combined_text or "NOM" in combined_text:
            col_vessel = idx
        if "IMPORT" in s_text or "DEBA" in s_text or "DISCH" in s_text:
            col_import = idx
        elif "EXPORT" in s_text or "EMBA" in s_text or "LOAD" in s_text:
            col_export = idx
        elif "IMPORT" in h_text or "DEBA" in h_text or "DISCH" in h_text:
            if col_import == -1:
                col_import = idx
        elif "EXPORT" in h_text or "EMBA" in h_text or "LOAD" in h_text:
            if col_export == -1:
                col_export = idx
        if "DOC" in combined_text or "DEBUT" in combined_text or "COMMENCE" in combined_text:
            col_doc = idx
        if "FOC" in combined_text or "FIN" in combined_text or "COMPLET" in combined_text:
            col_foc = idx
        if "OBS" in combined_text or "REMARQUE" in combined_text or "COMMENT" in combined_text:
            col_obs = idx

    # Fallbacks de configuration
    if col_crane_id == -1: col_crane_id = config.SHIFT_COL_CRANE_ID
    if col_vessel == -1: col_vessel = config.SHIFT_COL_VESSEL
    if col_import == -1: col_import = config.SHIFT_COL_IMPORT_MOVES
    if col_export == -1: col_export = config.SHIFT_COL_EXPORT_MOVES
    if col_doc == -1: col_doc = config.SHIFT_COL_DOC
    if col_foc == -1: col_foc = config.SHIFT_COL_FOC
    if col_obs == -1: col_obs = config.SHIFT_COL_OBSERVATIONS

    crane_start = header_idx + 2
    crane_rows: List[CraneRow] = []

    # BUG 1 FIX : on itère sur un maximum de lignes raisonnables (longueur
    # de CRANE_IDS × 2 + 5 pour les lignes vides / totaux intercalés) au lieu
    # d'un décompte strict. Les lignes vides sont ignorées ; la boucle s'arrête
    # dès qu'un identifiant de grue non reconnu est rencontré dans une ligne
    # non-vide, ce qui marque la fin de la table.
    max_crane_scan = len(config.CRANE_IDS) * 2 + 5
    for row in rows[crane_start: crane_start + max_crane_scan]:
        if not row or all(c is None for c in row):
            continue  # ligne vide — on la saute et on continue
        if len(row) <= col_crane_id:
            break
        crane_id = trim(row[col_crane_id])
        if not crane_id or str(crane_id).strip().upper() not in config.CRANE_IDS:
            break  # fin de la table : identifiant non reconnu dans une ligne non-vide
        crane_id = str(crane_id).strip().upper()

        vessel_raw = trim(row[col_vessel]) if len(row) > col_vessel else None
        import_moves = to_int(row[col_import]) if len(row) > col_import else 0
        export_moves = to_int(row[col_export]) if len(row) > col_export else 0
        doc_raw = row[col_doc] if len(row) > col_doc else None
        foc_raw = row[col_foc] if len(row) > col_foc else None
        observations = trim(row[col_obs]) if len(row) > col_obs else None

        crane_rows.append(CraneRow(
            shift_num=shift_num,
            crane_id=crane_id,
            vessel_raw=vessel_raw,
            vessel_normalized=normalize_vessel_name(vessel_raw),
            import_moves=import_moves,
            export_moves=export_moves,
            doc_raw=doc_raw,
            foc_raw=foc_raw,
            observations=observations,
        ))

    logger.debug("Shift %s : %d ligne(s) grue lue(s).", shift_num, len(crane_rows))
    return crane_rows


def _parse_general_delays(rows, shift_num: int) -> List[GeneralDelayEntry]:
    header_idx = _find_row_index(rows, "Nature de retard")
    if header_idx is None:
        logger.debug("Shift %s : table de retards généraux absente.", shift_num)
        return []

    header_row = rows[header_idx]
    header_clean = [str(c).strip().upper() if c else "" for c in header_row]
    
    col_label = 0
    col_start = 2
    col_end = 3
    col_reason = 5
    
    for idx, cell_text in enumerate(header_clean):
        if not cell_text:
            continue
        if "NATURE" in cell_text or "RETARD" in cell_text:
            col_label = idx
        elif "DEBUT" in cell_text or "START" in cell_text or "COMMENCE" in cell_text:
            col_start = idx
        elif "FIN" in cell_text or "END" in cell_text or "COMPLET" in cell_text:
            col_end = idx
        elif "OBS" in cell_text or "REASON" in cell_text or "MOTIF" in cell_text or "REMARQUE" in cell_text:
            col_reason = idx

    entries: List[GeneralDelayEntry] = []
    base_date = datetime(2000, 1, 1)

    for row in rows[header_idx + 1: header_idx + 20]:
        if not row or all(c is None for c in row):
            continue
        label = trim(row[col_label]) if len(row) > col_label else None
        start_raw = row[col_start] if len(row) > col_start else None
        end_raw = row[col_end] if len(row) > col_end else None
        reason_text = trim(row[col_reason]) if len(row) > col_reason else None

        start_dt = excel_time_to_dt(start_raw, base_date)
        end_dt = excel_time_to_dt(end_raw, base_date)
        if start_dt is None or end_dt is None:
            continue
        if end_dt < start_dt:
            end_dt += timedelta(days=1)
        duration_minutes = (end_dt - start_dt).total_seconds() / 60

        if duration_minutes <= 0:
            continue

        entries.append(GeneralDelayEntry(
            shift_num=shift_num,
            label=label,
            duration_minutes=duration_minutes,
            reason_text=reason_text,
        ))

    if entries:
        logger.info("Shift %s : %d retard(s) général(aux) détecté(s).", shift_num, len(entries))
    return entries


def _parse_shift_movements_table(rows) -> dict[str, dict[str, int]]:
    """Index (0-based) de la table secondaire des mouvements (ouverture/fermeture PC, shifting)."""
    header_idx = None
    for i, row in enumerate(rows):
        if i < 12:
            continue
        for cell in row:
            if isinstance(cell, str) and "portique" in cell.strip().lower():
                header_idx = i
                break
        if header_idx is not None:
            break

    crane_moves = {cid: {"shifting_discharged": 0, "shifting_loaded": 0, "hatch_open": 0, "hatch_close": 0} for cid in config.CRANE_IDS}
    if header_idx is None:
        return crane_moves

    header_row = rows[header_idx]
    crane_cols = {}
    for c_idx, cell in enumerate(header_row):
        if cell:
            c_id = str(cell).strip().upper()
            if c_id in config.CRANE_IDS:
                crane_cols[c_id] = c_idx

    for r in range(header_idx + 1, min(header_idx + 10, len(rows))):
        row = rows[r]
        if not row or all(cell is None for cell in row):
            continue
        label = ""
        for cell in row:
            if cell:
                import unicodedata
                label = unicodedata.normalize("NFKD", str(cell)).encode("ascii", "ignore").decode().strip().lower()
                break
        if not label:
            continue

        metric = None
        if "shifting" in label and ("dechar" in label or "dech" in label):
            metric = "shifting_discharged"
        elif "shifting" in label and ("char" in label or "ch" in label or "load" in label):
            metric = "shifting_loaded"
        elif "ouverture" in label or ("hatch" in label and "open" in label):
            metric = "hatch_open"
        elif "fermeture" in label or ("hatch" in label and "close" in label):
            metric = "hatch_close"

        if metric:
            for c_id, col_idx in crane_cols.items():
                if col_idx < len(row):
                    val = to_int(row[col_idx])
                    crane_moves[c_id][metric] += val
    return crane_moves


def clean_shift_report(raw: RawShiftReport) -> CleanedShiftReport:
    """Nettoie un rapport de shift brut : date, table grues, table de retards généraux."""
    logger.info("Nettoyage du rapport de Shift %s", raw.shift_num)

    shift_date = None
    for row in raw.rows[:10]:
        for cell in row:
            if isinstance(cell, datetime):
                shift_date = cell.replace(hour=0, minute=0, second=0, microsecond=0)
                break
        if shift_date:
            break
    if shift_date is None:
        logger.warning("Shift %s : date introuvable dans les 10 premières lignes.", raw.shift_num)

    crane_rows = _parse_crane_table(raw.rows, raw.shift_num)
    crane_moves = _parse_shift_movements_table(raw.rows)

    assigned_cranes = set()
    for cr in crane_rows:
        if cr.crane_id not in assigned_cranes:
            moves = crane_moves.get(cr.crane_id, {})
            cr.restow_discharged = moves.get("shifting_discharged", 0)
            cr.restow_loaded = moves.get("shifting_loaded", 0)
            cr.hatch_cover_open = moves.get("hatch_open", 0)
            cr.hatch_cover_close = moves.get("hatch_close", 0)
            assigned_cranes.add(cr.crane_id)
        else:
            cr.restow_discharged = 0
            cr.restow_loaded = 0
            cr.hatch_cover_open = 0
            cr.hatch_cover_close = 0

    general_delays = _parse_general_delays(raw.rows, raw.shift_num)

    return CleanedShiftReport(
        shift_num=raw.shift_num,
        shift_date=shift_date,
        crane_rows=crane_rows,
        general_delays=general_delays,
    )


def clean_all_shift_reports(raw_reports: dict) -> dict:
    """Applique clean_shift_report à tous les rapports {shift_num: RawShiftReport}."""
    return {num: clean_shift_report(raw) for num, raw in raw_reports.items()}
