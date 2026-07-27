from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import difflib
import re
import pandas as pd


import config
from src.cleaning import CleanedShiftReport, GeneralDelayEntry
from src.logger import get_logger
from src.utils import normalize_vessel_name, vessel_matches, clean_vessel_name

logger = get_logger("merge")


@dataclass
class CraneSession:
    shift_num: int
    commenced: datetime
    completed: datetime
    import_moves: int
    export_moves: int
    restow_discharged: int = 0
    restow_loaded: int = 0
    hatch_cover_open: int = 0
    hatch_cover_close: int = 0

    @property
    def duration_minutes(self) -> float:
        return (self.completed - self.commenced).total_seconds() / 60


@dataclass
class BreakBulkEntry:
    operator: str
    is_load: bool
    is_discharge: bool
    count: int


@dataclass
class MergedVesselDataset:
    vessel_name: str
    escale: Optional[str]
    shift_dates: Dict[int, Optional[datetime]] = field(default_factory=dict)
    crane_sessions: Dict[str, List[CraneSession]] = field(default_factory=dict)
    containers_import: pd.DataFrame = field(default_factory=pd.DataFrame)
    containers_export: pd.DataFrame = field(default_factory=pd.DataFrame)
    general_delays: List[GeneralDelayEntry] = field(default_factory=list)
    vessel_moves_in_shifts: Dict[str, int] = field(default_factory=dict)
    voyage: Optional[str] = None
    break_bulk_moves: List[BreakBulkEntry] = field(default_factory=list)



# ─────────────────────────────────────────────────────────────
# INFÉRENCE DU NOM DE NAVIRE (depuis les shifts)
# ─────────────────────────────────────────────────────────────

def infer_vessel_from_shifts(
    cleaned_shifts: Dict[int, CleanedShiftReport],
) -> Optional[str]:
    """
    Extrait le nom de navire le plus fréquent depuis la colonne vessel_raw
    des CraneRows des rapports de shift. Retourne None si aucune donnée.
    """
    counter: Counter = Counter()
    for cleaned in cleaned_shifts.values():
        for crane_row in cleaned.crane_rows:
            if crane_row.vessel_raw and str(crane_row.vessel_raw).strip():
                counter[str(crane_row.vessel_raw).strip()] += 1
    if not counter:
        return None
    name, count = counter.most_common(1)[0]
    logger.info(
        "Navire inféré depuis les shifts : '%s' (%d occurrences). Tous : %s",
        name, count, dict(counter.most_common(5)),
    )
    return name


# ─────────────────────────────────────────────────────────────
# INFÉRENCE DE L'ESCALE (depuis les MASTERYD — clé indépendante)
# ─────────────────────────────────────────────────────────────

def infer_escale_from_masteryd(
    containers_import: pd.DataFrame,
    containers_export: pd.DataFrame,
) -> Optional[str]:
    """
    Extrait la valeur d'ESCALE la plus fréquente depuis les DataFrames MASTERYD.

    CONCEPT CLEF : L'ESCALE est un identifiant de voyage/escale portuaire
    (ex : "BELITAKI_24062026") qui EST DIFFÉRENT du nom de navire
    (ex : "MASTERY D" ou "BELITAKI"). Ces deux informations ne peuvent
    pas être comparées : l'ESCALE est inférée depuis les données MASTERYD,
    jamais depuis le nom de navire fourni par l'utilisateur.

    Cette fonction est appelée SYSTÉMATIQUEMENT, qu'un vessel_name soit
    fourni ou non, car l'escale de filtrage doit toujours venir des données
    réelles et non d'une constante de configuration.
    """
    counter: Counter = Counter()
    for df in (containers_import, containers_export):
        if df is not None and not df.empty and "escale" in df.columns:
            values = df["escale"].dropna().astype(str).str.strip()
            values = values[values.str.len() > 0]
            counter.update(values.tolist())

    if not counter:
        logger.warning(
            "infer_escale_from_masteryd : aucune valeur ESCALE trouvée "
            "dans les DataFrames MASTERYD. Filtrage des conteneurs impossible."
        )
        return None

    escale, count = counter.most_common(1)[0]
    logger.info(
        "ESCALE inférée depuis MASTERYD : '%s' (%d occurrences). "
        "Toutes les escales détectées : %s",
        escale, count, dict(counter.most_common(10)),
    )

    return escale


def _resolve_crane_session(crane_row, shift_date: Optional[datetime]) -> Optional[CraneSession]:
    """Construit une CraneSession à partir d'une CraneRow + la date du shift."""
    from datetime import timedelta, time as dtime

    if shift_date is None:
        return None

    def _extract_time_of_day(val):
        if val is None:
            return None
        if isinstance(val, datetime):
            return val.time()
        if isinstance(val, dtime):
            return val
        if isinstance(val, timedelta):
            tot_sec = int(val.total_seconds()) % 86400
            return dtime(tot_sec // 3600, (tot_sec % 3600) // 60, tot_sec % 60)
        if isinstance(val, (int, float)):
            tot_sec = int(float(val) * 86400) % 86400
            return dtime(tot_sec // 3600, (tot_sec % 3600) // 60, tot_sec % 60)
        if isinstance(val, str):
            parts = val.strip().split(":")
            if len(parts) >= 2:
                try:
                    return dtime(int(parts[0]) % 24, int(parts[1]) % 60)
                except ValueError:
                    return None
        return None

    doc_time = _extract_time_of_day(crane_row.doc_raw)
    foc_time = _extract_time_of_day(crane_row.foc_raw)

    has_moves = (crane_row.import_moves > 0 or crane_row.export_moves > 0)

    if doc_time is None or foc_time is None:
        if has_moves:
            commenced = shift_date
            completed = shift_date + timedelta(minutes=1)
        else:
            return None
    else:
        commenced = shift_date.replace(hour=doc_time.hour, minute=doc_time.minute, second=doc_time.second, microsecond=0)
        completed = shift_date.replace(hour=foc_time.hour, minute=foc_time.minute, second=foc_time.second, microsecond=0)
        if completed < commenced:
            completed += timedelta(days=1)  # Shift traversant minuit (ex: 23:19 -> 04:20)
        elif commenced == completed:
            if has_moves:
                completed = commenced + timedelta(minutes=1)
            else:
                return None  # Grue inactive (00:00 = 00:00 sans mouvements)

    # RC5 FIX — Correction de date pour les sessions en tout début de nuit
    # (DOC entre 00h00 et 05h59) dans un shift nocturne.
    #
    # Problème : un shift daté du jour J peut couvrir la plage 22h-06h.
    # Une session DOC=00:10 reçoit base_date=J alors qu'elle appartient à J+1.
    # Détection heuristique : si l'heure de début est dans [00h, 06h[
    # ET que le shift lui-même contient au moins une autre session débutant
    # après 20h00 (indicateur de shift nocturne traversant minuit), on avance
    # la date de la session de +1 jour.
    #
    # IMPORTANT : ce correctif ne s'applique qu'à la session concernée,
    # pas à toutes les sessions du shift, pour ne pas perturber les sessions
    # diurnes du même shift.
    if 0 <= commenced.hour < 6:
        # Vérifier si le shift est bien un shift nocturne : la présence d'une
        # autre session démarrant après 20h sera détectée dans merge_crane_sessions
        # en passant un flag. Ici on utilise un marqueur sur la CraneRow si
        # disponible, sinon on laisse merge_crane_sessions corriger a posteriori.
        pass  # Correction appliquée a posteriori dans merge_crane_sessions

    duration_h = (completed - commenced).total_seconds() / 3600
    if duration_h > config.MAX_REASONABLE_SESSION_HOURS:
        logger.warning(
            "Shift %s grue %s : durée suspecte (%.1f h), session ignorée.",
            crane_row.shift_num, crane_row.crane_id, duration_h,
        )
        return None

    return CraneSession(
        shift_num=crane_row.shift_num,
        commenced=commenced,
        completed=completed,
        import_moves=crane_row.import_moves,
        export_moves=crane_row.export_moves,
        restow_discharged=getattr(crane_row, "restow_discharged", 0),
        restow_loaded=getattr(crane_row, "restow_loaded", 0),
        hatch_cover_open=getattr(crane_row, "hatch_cover_open", 0),
        hatch_cover_close=getattr(crane_row, "hatch_cover_close", 0),
    )


def merge_crane_sessions(
    cleaned_shifts: Dict[int, CleanedShiftReport],
    target_vessel_normalized: str,
) -> Dict[str, List[CraneSession]]:
    """
    Regroupe par grue les sessions où le navire travaillé correspond au
    navire cible (comparaison sur vessel_raw des shifts, pas sur ESCALE).

    RC3 FIX : déduplication des sessions par (commenced, completed) à 1 minute
    près. Evite le double-comptage des mouvements quand une session traversant
    minuit est signalée à la fois en fin de shift N et en début de shift N+1.

    RC5 FIX : correction de date a posteriori pour les sessions dont DOC est
    entre 00h00 et 05h59 dans un shift nocturne (shift contenant au moins une
    session démarrant après 20h). La date de ces sessions est avancée de +1 jour.
    """
    logger.debug("Fusion sessions grues (navire normalise : '%s')", target_vessel_normalized)
    # BUG A FIX : construction dynamique du dict pour accepter toute grue
    # présente dans les données (pas seulement celles listées dans config.CRANE_IDS).
    sessions: Dict[str, List[CraneSession]] = {}

    for shift_num, cleaned in sorted(cleaned_shifts.items()):
        for crane_row in cleaned.crane_rows:
            if not vessel_matches(crane_row.vessel_raw, target_vessel_normalized):
                continue
            session = _resolve_crane_session(crane_row, cleaned.shift_date)
            if session is None:
                continue
            sessions.setdefault(crane_row.crane_id, []).append(session)
            logger.info(
                "Shift %s : grue %s affectée à %s -> %s -> %s (imp=%d exp=%d)",
                shift_num, crane_row.crane_id, crane_row.vessel_raw,
                session.commenced.strftime("%d/%m %H:%M"),
                session.completed.strftime("%d/%m %H:%M"),
                session.import_moves, session.export_moves,
            )

    # RC5 FIX — Correction de date pour les sessions des shifts nocturnes.
    # Un shift nocturne (ou de nuit) couvre typiquement de 22h00 (J-1) à 06h00 (J).
    # - Les sessions démarrant en début de nuit (DOC < 06h00) appartiennent à J.
    # - Les sessions démarrant en début de shift (DOC >= 20h00) appartiennent à J-1.
    #
    # Nous ajustons donc les dates pour que toutes les sessions d'un même shift
    # nocturne soient cohérentes et alignées temporellement.
    NIGHT_SHIFT_START_HOUR = 20  # seuil : session après 20h = début du shift nocturne (J-1)
    EARLY_MORNING_MAX_HOUR = 6   # seuil : session avant 06h = fin du shift nocturne (J)

    for crane_id, crane_sessions_list in sessions.items():
        # Regrouper les sessions par shift_num pour raisonner par shift
        by_shift: Dict[int, List[CraneSession]] = {}
        for s in crane_sessions_list:
            by_shift.setdefault(s.shift_num, []).append(s)

        for shift_num, shift_sessions in by_shift.items():
            # Détecter si ce shift est nocturne (contient des sessions tardives OU est le shift 3)
            is_nocturne = shift_num == 3 or any(
                s.commenced.hour >= NIGHT_SHIFT_START_HOUR
                for s in shift_sessions
            )
            if not is_nocturne:
                continue

            # Ajuster les dates des sessions du shift nocturne :
            # Si le shift_date du rapport est le jour J (date de fin de nuit/matin) :
            # - Les sessions avec DOC >= 20h ont démarré le jour précédent (J-1).
            # - Les sessions avec DOC < 6h ont démarré le jour J.
            # (Pour s'aligner, on vérifie si la date du shift correspond au jour de fin ou de début.
            # En France/Maroc, les rapports de Shift 3 de nuit sont souvent datés du jour de début du shift,
            # ou du jour de fin. Si le shift contient à la fois des sessions >20h et <6h, on les aligne).
            has_morning = any(0 <= s.commenced.hour < EARLY_MORNING_MAX_HOUR for s in shift_sessions)
            has_evening = any(s.commenced.hour >= NIGHT_SHIFT_START_HOUR for s in shift_sessions)

            for s in shift_sessions:
                # Si le rapport a été daté du jour de fin de nuit (J), alors les soirées sont à J-1.
                # Si le rapport a été daté du jour de début (J-1), alors les matinées sont à J.
                # Pour harmoniser : si le shift a les deux, ou si on est en shift 3, on s'assure de l'écart d'un jour.
                if 0 <= s.commenced.hour < EARLY_MORNING_MAX_HOUR:
                    # Session de fin de nuit (matin)
                    # Si une session de soirée existe dans le même shift et est sur la même date de base,
                    # alors les matinées doivent être à J+1 par rapport à cette date de base.
                    if has_evening:
                        # Les soirées ont pris J, les matinées doivent prendre J + 1 jour
                        old_commenced = s.commenced
                        old_completed = s.completed
                        s.commenced += timedelta(days=1)
                        s.completed += timedelta(days=1)
                        logger.info(
                            "RC5 (Matin) — Shift %s grue %s : session matinale décalée de +1 jour "
                            "(%s→%s) — présence de sessions de soirée dans le même shift.",
                            shift_num, crane_id,
                            old_commenced.strftime("%d/%m %H:%M"), s.commenced.strftime("%d/%m %H:%M")
                        )
                elif s.commenced.hour >= NIGHT_SHIFT_START_HOUR:
                    # Session de début de nuit (soirée)
                    # Si le shift contient des matinées qui ont la même date de base que les soirées,
                    # cela signifie que la date de base était la date de fin (J). Donc les soirées doivent faire -1 jour.
                    # Ou si c'est le shift 3 et qu'on n'a pas de session matinale mais que la date du shift de nuit
                    # est la date du lendemain.
                    if has_morning:
                        # Les matinées ont pris J, les soirées doivent prendre J - 1 jour
                        old_commenced = s.commenced
                        old_completed = s.completed
                        s.commenced -= timedelta(days=1)
                        s.completed -= timedelta(days=1)
                        logger.info(
                            "RC5 (Soirée) — Shift %s grue %s : session de soirée décalée de -1 jour "
                            "(%s→%s) — présence de sessions matinales dans le même shift.",
                            shift_num, crane_id,
                            old_commenced.strftime("%d/%m %H:%M"), s.commenced.strftime("%d/%m %H:%M")
                        )

    # RC3 FIX — Déduplication par (crane_id, commenced, completed).
    # Seuil : deux sessions dont les débuts sont à moins de 1 minute l'un de
    # l'autre ET dont les fins sont à moins de 1 minute l'une de l'autre sont
    # considérées comme la même session (double-enregistrement entre deux shifts).
    # On garde celle qui a le plus de mouvements (la plus informative).
    DEDUP_THRESHOLD_SECONDS = 60

    for crane_id, crane_sessions_list in sessions.items():
        crane_sessions_list.sort(key=lambda s: s.commenced)
        deduplicated: List[CraneSession] = []
        for s in crane_sessions_list:
            is_dup = False
            for existing in deduplicated:
                delta_start = abs((s.commenced - existing.commenced).total_seconds())
                delta_end   = abs((s.completed  - existing.completed ).total_seconds())
                if delta_start <= DEDUP_THRESHOLD_SECONDS and delta_end <= DEDUP_THRESHOLD_SECONDS:
                    # Session dupliquée : on garde celle avec le plus de mouvements
                    if (s.import_moves + s.export_moves) > (existing.import_moves + existing.export_moves):
                        deduplicated.remove(existing)
                        deduplicated.append(s)
                        logger.info(
                            "RC3 — Grue %s : session dupliquée remplacée par la version avec plus "
                            "de mouvements (%d+%d vs %d+%d) — comm=%s.",
                            crane_id,
                            s.import_moves, s.export_moves,
                            existing.import_moves, existing.export_moves,
                            s.commenced.strftime("%d/%m %H:%M"),
                        )
                    else:
                        logger.info(
                            "RC3 — Grue %s : session dupliquée ignorée (comm=%s, "
                            "imp=%d exp=%d) — déjà présente avec imp=%d exp=%d.",
                            crane_id,
                            s.commenced.strftime("%d/%m %H:%M"),
                            s.import_moves, s.export_moves,
                            existing.import_moves, existing.export_moves,
                        )
                    is_dup = True
                    break
            if not is_dup:
                deduplicated.append(s)
        if len(deduplicated) < len(crane_sessions_list):
            logger.info(
                "RC3 — Grue %s : %d session(s) sur %d supprimées par déduplication.",
                crane_id, len(crane_sessions_list) - len(deduplicated), len(crane_sessions_list),
            )
        sessions[crane_id] = deduplicated

    # Avertir si des grues détectées ne sont pas référencées dans le template
    template_col_map = config.CRANE_TEMPLATE_COLUMN  # dict crane_id -> col
    unknown_cranes = [cid for cid in sessions if cid not in template_col_map]
    if unknown_cranes:
        logger.warning(
            "Grue(s) détectée(s) dans les données mais ABSENTE(S) de "
            "config.CRANE_TEMPLATE_COLUMN (settings.yaml) : %s. "
            "Leurs sessions ne pourront pas être écrites dans le template "
            "tant que celui-ci ne les référence pas.",
            unknown_cranes,
        )

    # Si aucune session trouvée avec le navire cible, logger les navires
    # réellement présents dans les shifts pour aider au diagnostic
    total_sessions = sum(len(v) for v in sessions.values())
    if total_sessions == 0:
        all_vessels = {
            cr.vessel_raw
            for cleaned in cleaned_shifts.values()
            for cr in cleaned.crane_rows
            if cr.vessel_raw
        }
        logger.warning(
            "Aucune session grue trouvée pour le navire cible '%s'. "
            "Navires présents dans les shifts : %s",
            target_vessel_normalized, sorted(all_vessels),
        )

    for cid in sessions:
        sessions[cid].sort(key=lambda s: s.commenced)

    return sessions


def filter_containers_by_escale(
    df: pd.DataFrame,
    escale_filter: str,
) -> pd.DataFrame:
    """
    Filtre un DataFrame MASTERYD sur les lignes dont la colonne ESCALE
    correspond à `escale_filter` (valeur exacte, insensible à la casse).

    `escale_filter` doit être la valeur brute de la colonne ESCALE
    (ex : "BELITAKI_24062026"), inférée par infer_escale_from_masteryd()
    — jamais le nom du navire fourni par l'utilisateur.
    """
    if df.empty or "escale" not in df.columns:
        return df

    target_clean = escale_filter.strip().upper()
    mask = df["escale"].apply(
        lambda e: str(e).strip().upper() == target_clean if e else False
    )
    filtered = df[mask].copy()

    if filtered.empty:
        # Diagnostic : lister les escales disponibles
        available = df["escale"].dropna().unique()[:10].tolist()
        logger.warning(
            "Filtrage ESCALE : AUCUN conteneur retenu pour l'escale '%s'. "
            "Valeurs disponibles dans le fichier : %s.",
            escale_filter, available,
        )
    else:
        logger.info(
            "Filtrage ESCALE '%s' : %d/%d lignes retenues.",
            escale_filter, len(filtered), len(df),
        )

    return filtered


def merge_general_delays(cleaned_shifts: Dict[int, CleanedShiftReport]) -> List[GeneralDelayEntry]:
    """Concatène les retards généraux de tous les shifts."""
    all_delays: List[GeneralDelayEntry] = []
    for shift_num, cleaned in sorted(cleaned_shifts.items()):
        all_delays.extend(cleaned.general_delays)
    if all_delays:
        logger.warning(
            "%d retard(s) général(aux) trouvé(s) dans les rapports de shift. "
            "Non associés à un navire spécifique -> à valider manuellement.",
            len(all_delays),
        )
    return all_delays


def infer_vessel_from_escale(escale_filter: Optional[str], cleaned_shifts: Dict[int, CleanedShiftReport]) -> str:
    """Déduit dynamiquement le nom du navire à partir de l'escale et des shifts.

    Stratégie à 5 niveaux (du plus précis au plus générique) :
      1. Correspondance exacte ou inclusion entre le nom normalisé du navire et l'escale normalisée.
      2. Extraction du préfixe alphabétique de l'escale (avant underscore/chiffres) et recherche
         de navire dont le nom normalisé commence par ce préfixe.
         Ex : 'SEATRADE_09062026' -> préfixe 'SEATRADE' -> match 'SEATRADE CHILE'.
      3. Fuzzy match (SequenceMatcher) avec seuil abaissé à 0.45 pour tolérer les noms composés.
      4. Fallback sur config.TARGET_VESSEL_NAME (settings.yaml) avec avertissement explicite.
      5. Dernier recours : premier segment de l'escale.
    """
    if not escale_filter:
        inferred = infer_vessel_from_shifts(cleaned_shifts)
        return inferred or "UNKNOWN_VESSEL"

    esc_norm = normalize_vessel_name(escale_filter)

    # Récupérer tous les noms de navires uniques des shifts
    vessels_in_shifts = set()
    for report in cleaned_shifts.values():
        for row in report.crane_rows:
            if row.vessel_raw:
                vessels_in_shifts.add(row.vessel_raw)

    # 1. Correspondance exacte ou inclusion simple (normalisé)
    for v in vessels_in_shifts:
        v_norm = normalize_vessel_name(v)
        if v_norm and (v_norm in esc_norm or esc_norm in v_norm):
            logger.info("Relation Escale -> Navire trouvée : '%s' -> '%s'", escale_filter, v)
            return v

    # 2. Préfixe alphabétique de l'escale (partie avant underscore/chiffres)
    #    Ex: "SEATRADE_09062026" -> premier segment "SEATRADE" (digits finaux retirés)
    #        "BELITAKI_24062026" -> "BELITAKI"
    #        "AURORA_7VK12X4AB" -> "AURORA"
    esc_parts = re.split(r"[_\s]+", escale_filter)
    esc_alpha_prefix = re.sub(r"\d+$", "", esc_parts[0])  # segment 0, chiffres finaux retirés
    esc_alpha_prefix_norm = normalize_vessel_name(esc_alpha_prefix)

    if esc_alpha_prefix_norm and len(esc_alpha_prefix_norm) >= 4:
        for v in sorted(vessels_in_shifts):  # tri pour résultat déterministe
            v_norm = normalize_vessel_name(v)
            if v_norm and (v_norm.startswith(esc_alpha_prefix_norm)
                           or esc_alpha_prefix_norm in v_norm):
                logger.info(
                    "Relation Escale -> Navire (préfixe '%s') : '%s' -> '%s'",
                    esc_alpha_prefix, escale_filter, v,
                )
                return v

    # 3. Fuzzy match avec seuil 0.45 (tolérant les noms composés)
    best_v = None
    best_ratio = 0.0
    for v in vessels_in_shifts:
        v_norm = normalize_vessel_name(v)
        ratio = difflib.SequenceMatcher(None, v_norm, esc_norm).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_v = v

    if best_v and best_ratio >= 0.45:
        logger.info(
            "Relation Escale -> Navire (Fuzzy, ratio=%.2f) : '%s' -> '%s'",
            best_ratio, escale_filter, best_v,
        )
        return best_v

    # 4. Fallback sur config.TARGET_VESSEL_NAME (settings.yaml) avec avertissement
    configured_name = config.TARGET_VESSEL_NAME
    if configured_name:
        logger.warning(
            "Aucun navire des shifts ne correspond à l'escale '%s'. "
            "Fallback sur config.TARGET_VESSEL_NAME : '%s'. "
            "Mettez à jour vessel.target_name dans settings.yaml si ce navire est incorrect.",
            escale_filter, configured_name,
        )
        return configured_name

    # 4. Dernier recours : préfixe de l'escale avant le premier underscore/espace
    parts = re.split(r"[_\s]+", escale_filter)
    if parts:
        fallback = parts[0]
        logger.info(
            "Aucun navire configuré. Fallback sur le préfixe d'escale : '%s'", fallback
        )
        return fallback

    return "UNKNOWN_VESSEL"


def build_merged_dataset(
    cleaned_shifts: Dict[int, CleanedShiftReport],
    containers_import: pd.DataFrame,
    containers_export: pd.DataFrame,
    target_vessel_name: Optional[str] = None,
    target_vessel_normalized: Optional[str] = None,
) -> MergedVesselDataset:
    """
    Point d'entrée unique de la fusion.
    Entièrement piloté par les données pour Tâche 2 et Tâche 6.
    """
    logger.debug("Etape 4 : Fusion des donnees (escale auto-detectee)")

    # ── 1. Résolution de l'ESCALE (depuis les données MASTERYD) ──────────
    escale_filter = infer_escale_from_masteryd(containers_import, containers_export)

    if escale_filter is None:
        logger.error(
            "Impossible de déterminer l'ESCALE depuis les fichiers MASTERYD. "
            "Les DataFrames de conteneurs seront vides."
        )

    # ── 2. Résolution du nom de navire (déduit dynamiquement de l'escale) ──
    inferred_vessel = infer_vessel_from_escale(escale_filter, cleaned_shifts)
    target_vessel_name = clean_vessel_name(inferred_vessel)
    target_vessel_normalized = normalize_vessel_name(target_vessel_name)

    logger.info(
        "Fusion pour le navire cible détecté : '%s' (normalisé : '%s')",
        target_vessel_name, target_vessel_normalized,
    )

    # Compter les mouvements par navire dans tous les shifts pour le contrôle de cohérence
    vessel_moves_in_shifts: Dict[str, int] = {}
    for shift_num, cleaned in cleaned_shifts.items():
        # Tâche 12.4 : Vérifier si le shift appartient réellement à l'opération
        vessels_in_shift = {cr.vessel_raw for cr in cleaned.crane_rows if cr.vessel_raw}
        has_target = any(vessel_matches(v, target_vessel_normalized) for v in vessels_in_shift)
        
        if vessels_in_shift and not has_target:
            logger.warning(
                "Le rapport Shift %d ne contient aucune opération pour le navire cible '%s' "
                "(navires trouvés : %s). Il se peut que ce fichier appartienne à une autre escale.",
                shift_num, target_vessel_name, list(vessels_in_shift)
            )

        for crane_row in cleaned.crane_rows:
            v_raw = crane_row.vessel_raw or "INCONNU"
            v_moves = crane_row.import_moves + crane_row.export_moves
            vessel_moves_in_shifts[v_raw] = vessel_moves_in_shifts.get(v_raw, 0) + v_moves

    # ── 3. Fusion ─────────────────────────────────────────────────────────
    shift_dates = {num: c.shift_date for num, c in cleaned_shifts.items()}
    crane_sessions = merge_crane_sessions(cleaned_shifts, target_vessel_normalized)

    if escale_filter:
        filtered_import = filter_containers_by_escale(containers_import, escale_filter)
        filtered_export = filter_containers_by_escale(containers_export, escale_filter)
    else:
        filtered_import = containers_import.copy() if not containers_import.empty else containers_import
        filtered_export = containers_export.copy() if not containers_export.empty else containers_export
        logger.warning("ESCALE non déterminée : conteneurs importés sans filtrage.")

    # L'escale de référence pour le rapport = valeur de la 1ère ligne filtrée
    escale = escale_filter
    if escale is None:
        for df in (filtered_import, filtered_export):
            if not df.empty and "escale" in df.columns:
                escale = df["escale"].iloc[0]
                break

    general_delays = merge_general_delays(cleaned_shifts)

    # ── Extraction dynamique du voyage (BUG 2 FIX) ───────────────────────
    # Priorité 1 : colonne dédiée "voyage" ou "n_voyage" dans les DataFrames MASTERYD.
    #   Les fichiers MASTERYD peuvent contenir une colonne "VOYAGE" ou "N° VOYAGE"
    #   distincte de la colonne ESCALE ; on la lit en priorité.
    voyage = None
    for df in (filtered_import, filtered_export, containers_import, containers_export):
        if df is None or df.empty:
            continue
        for col_candidate in ("voyage", "n_voyage", "voyage_number", "voyage_no"):
            if col_candidate in df.columns:
                vals = df[col_candidate].dropna().astype(str).str.strip()
                vals = vals[vals.str.len() > 0]
                if not vals.empty:
                    voyage = vals.iloc[0].upper()
                    logger.info("Voyage extrait depuis la colonne '%s' du MASTERYD : %s", col_candidate, voyage)
                    break
        if voyage:
            break

    # Priorité 2 : segment mixte lettres+chiffres dans le code ESCALE.
    #   Fonctionne quand l'escale est encodée comme "VESSELNAME_VOYAGECODE_DDMMYYYY".
    if not voyage and escale:
        parts = re.split(r"[_\s]+", escale)
        for part in parts:
            p_upper = part.upper()
            if len(part) >= 5 and len(part) <= 12:
                if re.search(r"[A-Z]", p_upper) and re.search(r"[0-9]", p_upper):
                    # Rejeter les segments qui ressemblent à une date (ex: 24062026)
                    if not re.fullmatch(r"\d{6,8}", p_upper):
                        voyage = p_upper
                        logger.info("Voyage extrait depuis le code ESCALE '%s' : %s", escale, voyage)
                        break

    # Priorité 3 : segment mixte dans le nom du fichier template.
    if not voyage:
        try:
            template_files = [p for p in config.TEMPLATE_DIR.glob("*.xlsx") if not p.name.startswith("~$")]
            if template_files:
                filename = template_files[0].stem
                parts = re.split(r"[_\s]+", filename)
                skip_words = {"TPFREP", "TEMPLATE", "FINAL", "EXPORT", "IMPORT", "REPORT", "MASTERY"}
                for part in parts:
                    p_upper = part.upper()
                    if p_upper in skip_words:
                        continue
                    if len(part) >= 5 and len(part) <= 12:
                        if re.search(r"[A-Z]", p_upper) and re.search(r"[0-9]", p_upper):
                            if not re.fullmatch(r"\d{6,8}", p_upper):
                                voyage = p_upper
                                logger.info("Voyage extrait depuis le nom du template '%s' : %s", filename, voyage)
                                break
        except Exception as exc:
            logger.debug("Extraction voyage depuis le dossier template impossible : %s", exc)

    if voyage:
        logger.info("Voyage detecte dynamiquement : %s", voyage)
    else:
        logger.info("Aucun voyage detecte dynamiquement, utilisation des valeurs de configuration.")

    n_crane_sessions = sum(len(v) for v in crane_sessions.values())
    logger.info(
        "Fusion terminée : %d session(s) grue, %d conteneur(s) import, "
        "%d conteneur(s) export, %d retard(s).",
        n_crane_sessions, len(filtered_import), len(filtered_export), len(general_delays),
    )

    # ── Extraction des mouvements Break Bulk ─────────────────────────────
    break_bulk_moves = []
    op_prefixes = {
        "CMA": ["CMA", "ECMU", "APL", "ANL"],
        "TAR": ["TAR", "TARO"],
        "MSL": ["MSL", "MAERSK", "MSK", "PONU", "SEGU", "SUDU"],
    }
    for shift_num, cleaned in cleaned_shifts.items():
        for cr in cleaned.crane_rows:
            if not vessel_matches(cr.vessel_raw, target_vessel_normalized):
                continue
            obs = cr.observations
            if not obs:
                continue
            obs_lower = obs.lower()
            # Normaliser les accents (ex: "déchargement" → "dechargement") pour la détection
            import unicodedata as _ud
            _obs_nfd = _ud.normalize("NFD", obs_lower)
            obs_ascii = "".join(c for c in _obs_nfd if _ud.category(c) != "Mn")
            if any(w in obs_lower for w in ["elingue", "sling", "beba", "break bulk", "breakbulk", "bb"]):
                # Vérifier les mots-clés de déchargement sans accents pour couvrir
                # "déchargement", "débarquement", etc.
                is_discharge = any(w in obs_ascii for w in ["dechar", "disch", "debarq", "import"])
                is_load = not is_discharge and any(
                    w in obs_ascii for w in ["emba", "load", "export", "charge"]
                )
                if not is_discharge and not is_load:
                    is_discharge = True  # Déchargement par défaut

                found_operators = []
                for op, prefixes in op_prefixes.items():
                    for pref in prefixes:
                        if re.search(r'\b' + re.escape(pref) + r'\b', obs, re.IGNORECASE) or pref.lower() in obs_lower:
                            found_operators.append(op)
                            break
                if not found_operators:
                    found_operators = ["Common"]
                for op in set(found_operators):
                    break_bulk_moves.append(BreakBulkEntry(
                        operator=op,
                        is_load=is_load,
                        is_discharge=is_discharge,
                        count=1
                    ))

    return MergedVesselDataset(
        vessel_name=target_vessel_name,
        escale=escale,
        shift_dates=shift_dates,
        crane_sessions=crane_sessions,
        containers_import=filtered_import,
        containers_export=filtered_export,
        general_delays=general_delays,
        vessel_moves_in_shifts=vessel_moves_in_shifts,
        voyage=voyage,
        break_bulk_moves=break_bulk_moves,
    )

