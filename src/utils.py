"""
src/utils.py — Fonctions utilitaires génériques réutilisées par tous les
autres modules : parsing de dates/heures Excel, normalisation de chaînes,
classification des codes ISO conteneur, validation de numéro de conteneur.
"""

from __future__ import annotations

import re
from datetime import datetime, time as dtime, timedelta
from typing import Optional, Union

# Numéro de conteneur ISO 6346 : 4 lettres (3 propriétaire + 1 catégorie U/J/Z)
# + 6 chiffres + 1 chiffre de contrôle. On valide le FORMAT, pas le chiffre
# de contrôle (qui demanderait l'algorithme complet ISO 6346).
CONTAINER_NUMBER_RE = re.compile(r"^[A-Z]{3}[UJZ]\d{6}\d$")


def clean_vessel_name(name: Optional[str]) -> str:
    """
    Supprime les préfixes d'opérateurs courants (ex: CMA, MSL, AK, AKN)
    du nom du navire pour éviter la pollution (ex: AKPERSEUS -> PERSEUS).
    """
    if not name:
        return ""
    cleaned = str(name).strip()
    # Liste des préfixes d'opérateurs connus
    prefixes = [
        "CMA CGM", "CMA", "MAERSK", "MSK", "MSC", "APL", "ANL", 
        "SAFMARINE", "HAPAG LLOYD", "HAPAG", "ONE", "COSCO", "OOCL",
        "YANG MING", "PIL", "ZIM", "WAN HAI", "GRIMALDI", "MESSINA",
        "AKN", "AK", "TAR", "MSL"
    ]
    # Trier par longueur décroissante pour faire matcher les plus longs en premier
    prefixes = sorted(prefixes, key=len, reverse=True)
    for pref in prefixes:
        # Match au début, suivi d'une transition mot ou d'un séparateur, ou suivi d'une lettre majuscule
        pattern = re.compile(r'^' + re.escape(pref) + r'\b[\s\-_]*|^' + re.escape(pref) + r'(?=[A-Z])', re.IGNORECASE)
        new_val = pattern.sub('', cleaned)
        if new_val != cleaned:
            cleaned = new_val
            break
    return cleaned.strip()


def normalize_vessel_name(name: Optional[str]) -> str:
    """
    Normalise un nom de navire pour comparaison robuste aux variations
    d'espacement/casse/ponctuation/accents observées dans les fichiers réels.
    """
    if not name:
        return ""
    import unicodedata
    # Nettoyer d'abord le préfixe opérateur
    cleaned_name = clean_vessel_name(name)
    # Enlever les accents
    nfkd_form = unicodedata.normalize('NFKD', str(cleaned_name))
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('ASCII')
    # Enlever tout caractère non alpha-numérique (espaces, tirets, underscores, etc.)
    res = re.sub(r"[^A-Za-z0-9]+", "", only_ascii).strip().upper()
    return res


def vessel_matches(name: Optional[str], target_normalized: str) -> bool:
    """
    Retourne True si le nom de navire `name` correspond à `target_normalized`
    après normalisation.

    Utilise une correspondance préfixe bidirectionnelle pour gérer les cas
    où le nom dans le shift est plus spécifique que le nom extrait de l'ESCALE
    (ex : "SEATRADE CHILE" vs "SEATRADE", ou "MASTERY D" vs "MASTERYD").
    La correspondance est valide si l'un des deux est un préfixe de l'autre
    ET que le préfixe fait au moins 4 caractères (pour éviter les faux positifs
    sur des préfixes trop courts comme "MSC").
    """
    if not name or not target_normalized:
        return False
    a = normalize_vessel_name(name)
    b = normalize_vessel_name(target_normalized)
    if not a or not b:
        return False
    # Correspondance exacte (cas nominal)
    if a == b:
        return True
    # Correspondance préfixe bidirectionnelle avec seuil minimum de 4 caractères
    min_len = 4
    if len(b) >= min_len and a.startswith(b):
        from src.logger import get_logger
        get_logger("utils").debug("Vessel match par préfixe : '%s' (%s) commence par '%s'", name, a, b)
        return True
    if len(a) >= min_len and b.startswith(a):
        from src.logger import get_logger
        get_logger("utils").debug("Vessel match par préfixe inverse : '%s' (%s) est préfixe de '%s'", target_normalized, b, a)
        return True
    return False


def trim(value):
    """Trim générique : strip() si str, sinon retourne la valeur inchangée."""
    if isinstance(value, str):
        return value.strip()
    return value


def to_int(value, default: int = 0) -> int:
    """Conversion robuste en int ; retourne `default` si impossible."""
    if value is None:
        return default
    if isinstance(value, str) and value.strip() == "":
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def to_bool_flag(value) -> bool:
    """Convertit un flag 0/1 (ou '0'/'1', True/False) en bool."""
    if isinstance(value, bool):
        return value
    try:
        return int(value) == 1
    except (ValueError, TypeError):
        return False


def round_to_nearest_minute(val) -> Optional[datetime]:
    """Arrondit un datetime à la minute la plus proche (si second >= 30, ajoute 1 minute)."""
    if val is None or not isinstance(val, datetime):
        return val
    dt = val
    if dt.microsecond >= 500000:
        dt += timedelta(seconds=1)
    if dt.second >= 30:
        dt += timedelta(minutes=1)
    return dt.replace(second=0, microsecond=0)


def excel_time_to_dt(t_val, base_date: datetime) -> Optional[datetime]:
    """
    Combine une valeur d'heure Excel (datetime, datetime.time, timedelta, str 'HH:MM[:SS]'
    ou nombre décimal de jour) avec une date de référence `base_date`.
    Arrondit à la minute la plus proche pour éviter les décalages d'une minute.
    """
    if t_val is None:
        return None

    if isinstance(t_val, datetime):
        dt = t_val
        if dt.year in (1899, 1900):
            day_offset = max(0, dt.day - 1)
            dt = base_date.replace(hour=dt.hour, minute=dt.minute, second=dt.second, microsecond=dt.microsecond) + timedelta(days=day_offset)
        if dt.microsecond >= 500000:
            dt += timedelta(seconds=1)
        if dt.second >= 30:
            dt += timedelta(minutes=1)
        return dt.replace(second=0, microsecond=0)

    if isinstance(t_val, dtime):
        dt = base_date.replace(hour=t_val.hour, minute=t_val.minute, second=t_val.second)
        if t_val.microsecond >= 500000:
            dt += timedelta(seconds=1)
        if dt.second >= 30:
            dt += timedelta(minutes=1)
        return dt.replace(second=0, microsecond=0)

    if isinstance(t_val, timedelta):
        total_seconds = round(t_val.total_seconds())
        dt = base_date + timedelta(seconds=total_seconds)
        if dt.second >= 30:
            dt += timedelta(minutes=1)
        return dt.replace(second=0, microsecond=0)

    if isinstance(t_val, (int, float)):
        total_seconds = round(float(t_val) * 86400)
        dt = base_date + timedelta(seconds=total_seconds)
        if dt.second >= 30:
            dt += timedelta(minutes=1)
        return dt.replace(second=0, microsecond=0)

    if isinstance(t_val, str):
        s = t_val.strip()
        if not s:
            return None
        parts = s.split(":")
        try:
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            sec = int(parts[2]) if len(parts) > 2 else 0
            dt = base_date.replace(hour=h % 24, minute=m, second=sec, microsecond=0)
            if sec >= 30:
                dt += timedelta(minutes=1)
            return dt.replace(second=0, microsecond=0)
        except (ValueError, IndexError):
            return None

    return None


def parse_excel_datetime_str(value, fmt: str = "%d.%m.%Y %H:%M") -> Optional[datetime]:
    """Parse une date/heure fournie en chaîne, ou retourne directement si déjà datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, fmt)
    except ValueError:
        return None


def find_first_datetime_cell(rows, max_rows: int = 10) -> Optional[datetime]:
    """Cherche la première cellule de type datetime dans les `max_rows` premières lignes."""
    for row in rows[:max_rows]:
        for cell in row:
            if isinstance(cell, datetime):
                return cell.replace(hour=0, minute=0, second=0, microsecond=0)
    return None


def iso_size_category(iso_code) -> str:
    """
    Classe un code ISO conteneur en '20' ou '40+', selon la règle SMDG :
    premier caractère '2' -> 20 pieds, sinon (4, L, etc.) -> 40'/45'.
    """
    if iso_code is None:
        return "?"
    s = str(iso_code).strip()
    if not s:
        return "?"
    return "20" if s[0] == "2" else "40+"


def is_standard_iso_prefix(iso_code) -> bool:
    """True si le code ISO commence par un chiffre '2' ou '4' (cas standard)."""
    if iso_code is None:
        return False
    s = str(iso_code).strip()
    return bool(s) and s[0] in ("2", "4")


def is_valid_container_number(value) -> bool:
    """Valide le FORMAT d'un numéro de conteneur ISO 6346 (sans le chiffre de contrôle)."""
    if value is None:
        return False
    s = normalize_container_number(value)
    return bool(CONTAINER_NUMBER_RE.match(s))


def normalize_container_number(value) -> str:
    """Normalise un numéro de conteneur : trim, majuscules, espaces internes retirés."""
    if value is None:
        return ""
    return re.sub(r"\s+", "", str(value).strip().upper())


def sanitize_filename(value: Optional[str]) -> str:
    """Rend une chaîne sûre pour un nom de fichier (majuscule, séparateurs -> '_')."""
    s = (value or "INCONNU").strip().upper()
    for ch in " /\\:.,*?\"<>|":
        s = s.replace(ch, "_")
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "INCONNU"


def safe_str(value) -> str:
    """Représentation chaîne sûre (jamais None)."""
    return "" if value is None else str(value).strip()
