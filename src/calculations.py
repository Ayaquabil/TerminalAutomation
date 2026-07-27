"""
src/calculations.py — Calcul des indicateurs (KPIs) à partir du jeu de
données fusionné : totaux import/export, full/empty, conteneurs spéciaux
(dangereux/reefer/hors-gabarit), statistiques ISO, statistiques de
mouvement, statistiques temporelles, productivité grues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

import pandas as pd

from src.logger import get_logger
from src.merge import MergedVesselDataset

logger = get_logger("calculations")


@dataclass
class CraneProductivity:
    crane_id: str
    sessions: int
    total_import_moves: int
    total_export_moves: int
    total_moves: int
    total_working_hours: float
    gross_moves_per_hour: Optional[float]


@dataclass
class KPIResult:
    total_import_containers: int = 0
    total_export_containers: int = 0
    total_containers: int = 0

    full_import: int = 0
    empty_import: int = 0
    full_export: int = 0
    empty_export: int = 0

    dangerous_import: int = 0
    dangerous_export: int = 0
    reefer_import: int = 0
    reefer_export: int = 0
    oversized_import: int = 0
    oversized_export: int = 0

    iso_size_distribution: Dict[str, Dict[str, int]] = field(default_factory=dict)

    operator_discharged: Dict[str, Dict[str, int]] = field(default_factory=dict)
    operator_loaded: Dict[str, Dict[str, int]] = field(default_factory=dict)

    entry_time_min: Optional[pd.Timestamp] = None
    entry_time_max: Optional[pd.Timestamp] = None

    crane_productivity: Dict[str, CraneProductivity] = field(default_factory=dict)

    cross_check_crane_moves_total: int = 0
    cross_check_crane_moves_discharged: int = 0
    cross_check_crane_moves_loaded: int = 0
    cross_check_container_records_total: int = 0
    cross_check_matches: bool = False
    coherence_report: str = ""


def _direction_size_counts(df: pd.DataFrame) -> Dict[str, int]:
    if df.empty:
        return {"full_20": 0, "full_40": 0, "empty_20": 0, "empty_40": 0}
    full = df[df["is_full"]]
    empty = df[df["is_empty"]]
    return {
        "full_20": int((full["iso_size_category"] == "20").sum()),
        "full_40": int((full["iso_size_category"] == "40+").sum()),
        "empty_20": int((empty["iso_size_category"] == "20").sum()),
        "empty_40": int((empty["iso_size_category"] == "40+").sum()),
    }


def compute_operator_breakdown(df: pd.DataFrame) -> Dict[str, Dict[str, int]]:
    """Agrège un DataFrame conteneurs par opérateur : full/empty x 20'/40'."""
    if df.empty or "operator" not in df.columns:
        return {}
    result: Dict[str, Dict[str, int]] = {}
    for operator, group in df.groupby("operator"):
        result[operator] = _direction_size_counts(group)
    return result


def compute_iso_distributions(df_import: pd.DataFrame, df_export: pd.DataFrame) -> Dict[str, Dict[str, int]]:
    """Retourne la distribution par taille ISO (20'/40+'), pour import et export."""
    size_dist = {}
    for direction, df in (("IMPORT", df_import), ("EXPORT", df_export)):
        if df.empty:
            size_dist[direction] = {}
            continue
        size_dist[direction] = df["iso_size_category"].value_counts().to_dict()
    return size_dist


def compute_time_statistics(df_import: pd.DataFrame, df_export: pd.DataFrame) -> tuple:
    """Calcule la plage temporelle de saisie."""
    combined = pd.concat([df_import, df_export], ignore_index=True) if not (df_import.empty and df_export.empty) else pd.DataFrame()
    if combined.empty or "entry_datetime" not in combined.columns:
        return None, None

    valid = combined.dropna(subset=["entry_datetime"])
    if valid.empty:
        return None, None

    entry_min = valid["entry_datetime"].min()
    entry_max = valid["entry_datetime"].max()

    return entry_min, entry_max


def compute_crane_productivity(crane_sessions: Dict[str, list]) -> Dict[str, CraneProductivity]:
    """Calcule la productivité brute par grue à partir des sessions fusionnées."""
    result: Dict[str, CraneProductivity] = {}
    for crane_id, sessions in crane_sessions.items():
        if not sessions:
            continue
        total_import = sum(s.import_moves for s in sessions)
        total_export = sum(s.export_moves for s in sessions)
        total_moves = total_import + total_export
        total_hours = sum(s.duration_minutes for s in sessions) / 60
        gross_rate = (total_moves / total_hours) if total_hours > 0 else None

        result[crane_id] = CraneProductivity(
            crane_id=crane_id,
            sessions=len(sessions),
            total_import_moves=total_import,
            total_export_moves=total_export,
            total_moves=total_moves,
            total_working_hours=round(total_hours, 2),
            gross_moves_per_hour=round(gross_rate, 2) if gross_rate is not None else None,
        )
    return result


def compute_all_kpis(merged: MergedVesselDataset) -> KPIResult:
    """Point d'entrée unique : calcule l'ensemble des KPIs pour le jeu de données fusionné."""
    logger.info("Calcul des KPIs pour %s", merged.vessel_name)

    df_import, df_export = merged.containers_import, merged.containers_export
    kpi = KPIResult()

    kpi.total_import_containers = len(df_import)
    kpi.total_export_containers = len(df_export)
    kpi.total_containers = kpi.total_import_containers + kpi.total_export_containers

    if not df_import.empty:
        kpi.full_import = int(df_import["is_full"].sum())
        kpi.empty_import = int(df_import["is_empty"].sum())
        kpi.dangerous_import = int(df_import["dangerous_flag"].sum())
        kpi.reefer_import = int(df_import["reefer_flag"].sum())
        kpi.oversized_import = int(df_import["oversized_flag"].sum())

    if not df_export.empty:
        kpi.full_export = int(df_export["is_full"].sum())
        kpi.empty_export = int(df_export["is_empty"].sum())
        kpi.dangerous_export = int(df_export["dangerous_flag"].sum())
        kpi.reefer_export = int(df_export["reefer_flag"].sum())
        kpi.oversized_export = int(df_export["oversized_flag"].sum())

    kpi.iso_size_distribution = compute_iso_distributions(df_import, df_export)

    kpi.operator_discharged = compute_operator_breakdown(df_import)
    kpi.operator_loaded = compute_operator_breakdown(df_export)

    entry_min, entry_max = compute_time_statistics(df_import, df_export)
    kpi.entry_time_min = entry_min
    kpi.entry_time_max = entry_max

    kpi.crane_productivity = compute_crane_productivity(merged.crane_sessions)

    # Contrôle de cohérence : somme des mouvements grues == nombre d'enregistrements conteneurs
    kpi.cross_check_crane_moves_total = sum(cp.total_moves for cp in kpi.crane_productivity.values())
    kpi.cross_check_crane_moves_discharged = sum(cp.total_import_moves for cp in kpi.crane_productivity.values())
    kpi.cross_check_crane_moves_loaded = sum(cp.total_export_moves for cp in kpi.crane_productivity.values())
    kpi.cross_check_container_records_total = kpi.total_containers
    kpi.cross_check_matches = (
        kpi.cross_check_crane_moves_total == kpi.cross_check_container_records_total
    )

    kpi.coherence_report = "Contrôle de cohérence OK."
    if kpi.cross_check_matches:
        logger.info(
            "Contrôle de cohérence OK : %d mouvements grues == %d enregistrements conteneurs.",
            kpi.cross_check_crane_moves_total, kpi.cross_check_container_records_total,
        )
    else:
        gap = kpi.cross_check_crane_moves_total - kpi.cross_check_container_records_total
        report_lines = [
            f"Contrôle de cohérence : ÉCHOUÉ.",
            f"Somme des mouvements grues (shifts) : {kpi.cross_check_crane_moves_total}",
            f"Total conteneurs (fichiers conteneurs) : {kpi.cross_check_container_records_total}",
            f"Écart : {gap} mouvements."
        ]
        if hasattr(merged, "vessel_moves_in_shifts") and merged.vessel_moves_in_shifts:
            report_lines.append("Mouvements totaux enregistrés par navire dans les shifts :")
            for v, mv in merged.vessel_moves_in_shifts.items():
                report_lines.append(f"  - '{v}' : {mv} mouvements")
            
            # Vérifier si le navire recherché a peu/pas de mouvements
            target_moves = merged.vessel_moves_in_shifts.get(merged.vessel_name, 0)
            if target_moves == 0:
                report_lines.append(
                    f"Alerte : Le navire cible '{merged.vessel_name}' n'a AUCUN mouvement dans les shifts "
                    f"alors que le fichier conteneurs en contient {kpi.cross_check_container_records_total}."
                )
        else:
            report_lines.append("Alerte : Aucun mouvement trouvé dans les shifts.")
            
        kpi.coherence_report = "\n".join(report_lines)
        logger.warning(
            "Contrôle de cohérence ÉCHOUÉ : %d mouvements grues != %d enregistrements conteneurs "
            "(écart = %d). Rapport complet :\n%s",
            kpi.cross_check_crane_moves_total, kpi.cross_check_container_records_total,
            gap, kpi.coherence_report,
        )

    logger.info(
        "KPIs calculés : %d conteneurs import, %d export, %d dangereux, %d reefer, %d hors-gabarit.",
        kpi.total_import_containers, kpi.total_export_containers,
        kpi.dangerous_import + kpi.dangerous_export,
        kpi.reefer_import + kpi.reefer_export,
        kpi.oversized_import + kpi.oversized_export,
    )

    return kpi
