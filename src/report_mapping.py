"""
src/report_mapping.py — Mapping explicite :

    Cellule Excel (template TPFREP)
        -> Source (rapport de shift / IMPORT-EXPORT MASTERYD / calculée)
        -> Donnée source
        -> Transformation
        -> Formule déjà présente dans le template (à ne jamais écraser)

Ce module ne réalise AUCUNE écriture lui-même : il décrit la correspondance
sous forme de structures de données, que report_generator.py consomme pour
écrire UNIQUEMENT dans les cellules bleues (couleur indexée 44), sans jamais
toucher aux cellules contenant une formule existante.

Toutes les coordonnées sont 0-indexed (compatibles avec les constantes de
config.py) ; report_generator.py les convertit en coordonnées openpyxl
(1-indexed) au moment de l'écriture.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

import config


class CellSource(str, Enum):
    SHIFT_REPORT = "RAPPORT_DE_SHIFT"
    MASTERYD = "IMPORT_EXPORT_MASTERYD"
    CALCULATED = "CALCULE"
    STATIC = "STATIQUE_METIER"


@dataclass(frozen=True)
class CellMapping:
    row: int                      # 0-indexed
    col: int                      # 0-indexed
    excel_cell: str                # référence lisible, ex: "D8"
    source: CellSource
    source_field: str               # nom du champ/colonne source
    transformation: str             # description humaine de la transformation appliquée
    template_formula: Optional[str] = None  # formule déjà présente (ne JAMAIS écraser si non-None)


def _excel_ref(row0: int, col0: int) -> str:
    """Convertit (row,col) 0-indexed en référence Excel lisible (ex: 0,3 -> 'D1')."""
    col_letters = ""
    c = col0 + 1
    while c > 0:
        c, rem = divmod(c - 1, 26)
        col_letters = chr(65 + rem) + col_letters
    return f"{col_letters}{row0 + 1}"


def build_identification_mapping() -> list[CellMapping]:
    """Section 0 — Identification navire (lignes Excel 6-11)."""
    specs = [
        (5, 3, CellSource.STATIC, "VESSEL_IMO_DEFAULT (non communiqué dans les sources)",
         "Valeur fixe '-' : aucun fichier source ne fournit l'IMO du navire."),
        (5, 7, CellSource.STATIC, "config.VOYAGE_IMPORT",
         "Valeur métier fixe (tirée du nom du fichier template)."),
        (6, 3, CellSource.STATIC, "VESSEL_CALL_SIGN_DEFAULT (non communiqué dans les sources)",
         "Valeur fixe '-' : aucun fichier source ne fournit le Call Sign."),
        (6, 7, CellSource.STATIC, "config.VOYAGE_EXPORT",
         "Valeur métier fixe (tirée du nom du fichier template)."),
        (7, 3, CellSource.SHIFT_REPORT, "Colonne B 'Navire' (table grues)",
         "Nom du navire tel que saisi par l'opérateur de shift, repris sans transformation."),
        (8, 3, CellSource.STATIC, "config.VESSEL_PORT_UNLOCODE",
         "Valeur métier fixe (code UN/LOCODE du port, non présent dans les sources)."),
        (9, 3, CellSource.STATIC, "config.TERMINAL_CODE",
         "Valeur métier fixe (code terminal, non présent dans les sources)."),
        (10, 3, CellSource.MASTERYD, "Colonne 'EXPLOITANT EN COURS'",
         "Code opérateur unique trouvé dans les enregistrements conteneur du navire cible."),
    ]
    return [
        CellMapping(row=r, col=c, excel_cell=_excel_ref(r, c), source=src,
                    source_field=field, transformation=transfo)
        for r, c, src, field, transfo in specs
    ]


def build_timesheet_mapping() -> list[CellMapping]:
    """Section 1.1 — Vessel Timesheet (lignes Excel 15-20). D21/D22 sont des FORMULES -> exclues."""
    specs = [
        (14, 3, "Aucune donnée 'Planned Arrival' dans les rapports de shift réels",
         "Non rempli : non disponible dans les sources fournies (à compléter manuellement si connu)."),
        (15, 3, "Idem 'Planned Departure'",
         "Non rempli : non disponible dans les sources fournies."),
        (16, 3, "Idem 'Arrival Berth'",
         "Non rempli : non disponible dans les sources fournies."),
        (17, 3, "Idem 'Sailed Berth'",
         "Non rempli : non disponible dans les sources fournies."),
        (18, 3, "Idem 'Lashing Gangs ON'",
         "Non rempli : non disponible dans les sources fournies."),
        (19, 3, "Idem 'Lashing Gangs OFF'",
         "Non rempli : non disponible dans les sources fournies."),
    ]
    return [
        CellMapping(row=r, col=c, excel_cell=_excel_ref(r, c), source=CellSource.SHIFT_REPORT,
                    source_field=field, transformation=transfo)
        for r, c, field, transfo in specs
    ]


def build_crane_timesheet_mapping() -> list[CellMapping]:
    """
    Section 2.1 — Crane Timesheet (lignes 36, 38-60, 65).
    D21 (First Crane Lift) et D22 (Last Crane Lift) sont des FORMULES
    (=MIN/MAX) déjà présentes : elles ne sont JAMAIS écrites par le code,
    elles se recalculent seules une fois les sessions remplies.
    """
    mappings: list[CellMapping] = []

    for crane_id, col in config.CRANE_TEMPLATE_COLUMN.items():
        mappings.append(CellMapping(
            row=35, col=col, excel_cell=_excel_ref(35, col), source=CellSource.STATIC,
            source_field="Type de grue (non détaillé dans les rapports de shift réels)",
            transformation="Valeur fixe 'STS' par défaut (à corriger si une grue est en réalité un MHC).",
        ))
        for i, (row_start, row_end) in enumerate(config.SESSION_ROWS):
            mappings.append(CellMapping(
                row=row_start, col=col, excel_cell=_excel_ref(row_start, col),
                source=CellSource.SHIFT_REPORT, source_field=f"Colonne 'DOC' (Shift, grue {crane_id}, session {i+1})",
                transformation="Heure DOC combinée à la date du shift -> datetime 'commenced'.",
            ))
            mappings.append(CellMapping(
                row=row_end, col=col, excel_cell=_excel_ref(row_end, col),
                source=CellSource.SHIFT_REPORT, source_field=f"Colonne 'FOC' (Shift, grue {crane_id}, session {i+1})",
                transformation="Heure FOC combinée à la date du shift (+1 jour si franchissement de minuit) -> datetime 'completed'.",
            ))
        mappings.append(CellMapping(
            row=config.TOTAL_MOVES_PER_CRANE_ROW, col=col,
            excel_cell=_excel_ref(config.TOTAL_MOVES_PER_CRANE_ROW, col),
            source=CellSource.SHIFT_REPORT,
            source_field=f"Somme des colonnes 'Total moves Import'+'Export' (grue {crane_id}, tous shifts)",
            transformation="Somme des mouvements import+export de la grue sur les 3 shifts.",
        ))

    mappings.append(CellMapping(
        row=20, col=3, excel_cell=_excel_ref(20, 3), source=CellSource.CALCULATED,
        source_field="MIN(commenced) sur toutes les sessions",
        transformation="Non écrit : cellule D21 contient déjà la formule =MIN(E38:L38).",
        template_formula="=MIN(E38:L38)",
    ))
    mappings.append(CellMapping(
        row=21, col=3, excel_cell=_excel_ref(21, 3), source=CellSource.CALCULATED,
        source_field="MAX(completed) sur toutes les sessions",
        transformation="Non écrit : cellule D22 contient déjà la formule =MAX(E39:L60).",
        template_formula="=MAX(E39:L60)",
    ))
    return mappings


def build_general_delays_mapping() -> list[CellMapping]:
    """Section 1.2 — General Delays (lignes 26-29, colonnes D/E/F = Duration/ReasonCode/Reason).

    NOTE DE CONCEPTION / EXCLUSION SHIP & CARGO DELAYS :
    La section "Delays caused by Ship or Cargo Operation" ne doit JAMAIS être renseignée
    par le pipeline, quelle que soit la donnée disponible dans les shifts ou les sources.
    Elle doit rester intégralement vide dans le rapport généré. Aucune cellule de cette
    section ne possède de mapping ici ou ne doit être écrite par le générateur de rapport.
    """
    mappings = []
    for row in config.GENERAL_DELAY_ROWS:
        mappings.append(CellMapping(
            row=row, col=3, excel_cell=_excel_ref(row, 3), source=CellSource.SHIFT_REPORT,
            source_field="Table 'Nature de retard' (colonnes Début/Fin), tous shifts",
            transformation="Durée = Fin - Début (+1 jour si franchissement minuit), au format hh:mm.",
        ))
        mappings.append(CellMapping(
            row=row, col=5, excel_cell=_excel_ref(row, 5), source=CellSource.STATIC,
            source_field="Catégorie EDIFACT TPFREP la plus proche",
            transformation="Code 'MSC' (Miscellaneous) par défaut : la source ne fournit pas de "
                            "code de catégorie EDIFACT, seulement un libellé texte libre.",
        ))
        mappings.append(CellMapping(
            row=row, col=6, excel_cell=_excel_ref(row, 6), source=CellSource.SHIFT_REPORT,
            source_field="Table 'Nature de retard', colonnes 'Nature' + 'Observations'",
            transformation="Concaténation du libellé de retard et des observations associées.",
        ))
    return mappings


def build_restow_mapping() -> list[CellMapping]:
    """
    Section 5.1 — Restow (ligne 'Common', car la source ne détaille pas de
    restow conteneur par opérateur dans IMPORT/EXPORT MASTERYD).
    """
    return [
        CellMapping(
            row=config.RESTOW_COMMON_ROW, col=3, excel_cell=_excel_ref(config.RESTOW_COMMON_ROW, 3),
            source=CellSource.STATIC, source_field="Non disponible dans les sources",
            transformation="Non rempli : aucune donnée de restow conteneur détaillée dans les fichiers fournis.",
        ),
    ]


def build_discharged_loaded_mapping() -> list[CellMapping]:
    """
    Sections 3.1 (Discharged) et 4.1 (Deepsea Loaded) — lignes alignées par
    opérateur (la colonne C de 4.1 est une formule '=C128' etc. pointant
    vers 3.1 : un même opérateur DOIT occuper la même ligne dans les deux
    tableaux, donc la liste d'opérateurs est construite une seule fois et
    partagée entre les deux sections).
    """
    mappings = []
    for i in range(config.MAX_OPERATORS):
        r_disc = config.DISCHARGED_START_ROW + i
        r_load = config.LOADED_DEEPSEA_START_ROW + i

        mappings.append(CellMapping(
            row=r_disc, col=2, excel_cell=_excel_ref(r_disc, 2), source=CellSource.MASTERYD,
            source_field="Colonne 'EXPLOITANT EN COURS' (IMPORT MASTERYD, navire cible)",
            transformation=f"Opérateur n°{i+1} de la liste triée des opérateurs trouvés en import.",
        ))
        for col, label in ((3, "full_20"), (4, "full_40"), (6, "empty_20"), (7, "empty_40")):
            mappings.append(CellMapping(
                row=r_disc, col=col, excel_cell=_excel_ref(r_disc, col), source=CellSource.MASTERYD,
                source_field="V/P='P' (full) ou 'V' (empty) x TYPE ISO (20'/40'+45'), IMPORT MASTERYD",
                transformation=f"Comptage des conteneurs {label} de cet opérateur, direction IMPORT.",
            ))
            mappings.append(CellMapping(
                row=r_load, col=col, excel_cell=_excel_ref(r_load, col), source=CellSource.MASTERYD,
                source_field="V/P='P' (full) ou 'V' (empty) x TYPE ISO (20'/40'+45'), EXPORT MASTERYD",
                transformation=f"Comptage des conteneurs {label} de cet opérateur, direction EXPORT.",
            ))
        mappings.append(CellMapping(
            row=r_load, col=2, excel_cell=_excel_ref(r_load, 2), source=CellSource.CALCULATED,
            source_field="N/A",
            transformation="Non écrit : la colonne C de 4.1 contient déjà la formule pointant vers 3.1.",
            template_formula=f"=C{r_disc + 1}",
        ))
    return mappings


def build_hatch_cover_mapping() -> list[CellMapping]:
    """Section 6 — Hatch Cover Moves (pas de donnée dans la source -> non rempli)."""
    return [
        CellMapping(
            row=config.HATCH_COVER_ROW, col=3, excel_cell=_excel_ref(config.HATCH_COVER_ROW, 3),
            source=CellSource.STATIC, source_field="Non disponible dans les sources",
            transformation="Non rempli : aucune donnée de mouvement de panneaux de cale dans les fichiers fournis.",
        ),
    ]


def build_full_mapping() -> list[CellMapping]:
    """Assemble le mapping complet, section par section."""
    mapping: list[CellMapping] = []
    mapping += build_identification_mapping()
    mapping += build_timesheet_mapping()
    mapping += build_crane_timesheet_mapping()
    mapping += build_general_delays_mapping()
    mapping += build_discharged_loaded_mapping()
    mapping += build_restow_mapping()
    mapping += build_hatch_cover_mapping()
    return mapping


def mapping_to_dataframe():
    """Représentation tabulaire du mapping complet (pour audit / export CSV / documentation)."""
    import pandas as pd
    rows = [
        {
            "excel_cell": m.excel_cell,
            "source": m.source.value,
            "source_field": m.source_field,
            "transformation": m.transformation,
            "template_formula": m.template_formula or "",
        }
        for m in build_full_mapping()
    ]
    return pd.DataFrame(rows)
