# TerminalAutomation

Automatisation du remplissage du rapport **TPFREP** (Terminal Departure and
Performance Report, format UN/EDIFACT SMDG 3.0) à partir des fichiers
opérationnels réels du terminal SOMAPORT : rapports de shift et listes de
mouvements conteneurs (IMPORT/EXPORT MASTERYD).

Le pipeline importe, valide, nettoie, fusionne et calcule les indicateurs,
puis remplit **uniquement les cellules bleues** du template Excel fourni
(toutes les autres cellules — formules, styles, fusions, bordures, lignes/
colonnes masquées — restent strictement inchangées), et génère en plus un
tableau de bord Excel avec graphiques.

## 1. Installation

Prérequis : Python 3.12.

```bash
cd TerminalAutomation
python3 -m venv venv
source venv/bin/activate          # Windows : venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Structure du dossier

```
TerminalAutomation/
├── config.py                 # Chemins, constantes métier, mapping grues/couleurs
├── main.py                   # Point d'entrée : orchestre tout le pipeline
├── requirements.txt
├── README.md
├── src/
│   ├── logger.py              # Logging fichier + console
│   ├── utils.py                # Fonctions génériques (dates, normalisation, ISO...)
│   ├── import_data.py          # Découverte et chargement des fichiers Excel
│   ├── validation.py           # Validation (colonnes, dates, doublons, valeurs obligatoires)
│   ├── cleaning.py             # Nettoyage et structuration des données brutes
│   ├── merge.py                # Fusion shift + MASTERYD sur le navire cible
│   ├── calculations.py         # Calcul des KPIs
│   ├── report_mapping.py       # Documentation du mapping Cellule -> Source -> Transformation
│   ├── report_generator.py     # Remplissage protégé du template TPFREP
│   └── dashboard.py            # Génération du dashboard Excel (tableaux + graphiques)
├── tests/                      # Suite de tests pytest (54 tests)
├── data/
│   ├── input/                  # Fichiers sources à déposer ici
│   ├── template/                # Template TPFREP vierge
│   └── output/                  # TPFREP_FINAL.xlsx et DASHBOARD.xlsx générés
└── logs/
    └── application.log          # Journal complet de chaque exécution
```

## 3. Exécution

### Option A — Plateforme BI (recommandée)

```bash
pip install -r requirements.txt
streamlit run app.py
```

L'application s'ouvre dans le navigateur (`http://localhost:8501`) avec
4 pages, accessibles depuis la page d'accueil ou le menu latéral :

| Page | Rôle |
|---|---|
| **📥 Traitement** | Glisser-déposer des fichiers (.xlsx ou .xls, convertis automatiquement), exécution du pipeline avec barre de progression, génération optionnelle d'un PDF, téléchargement des sorties. |
| **📊 Dashboard BI** | KPIs, filtres (direction, grues) et graphiques interactifs Plotly (full/empty, répartition ISO, productivité par grue, conteneurs par opérateur), à partir du dernier traitement effectué. |
| **🕓 Historique** | Traçabilité complète de tous les traitements (succès/échecs, fichiers utilisés, sorties générées), stockée en SQLite (`data/history.db`), avec liste des archives sur disque. |
| **⚙️ Paramètres** | Édition de `config/settings.yaml` (navire, terminal, seuils de validation, mapping grues) directement depuis l'interface, sans toucher au code. |

Chaque traitement réussi est automatiquement archivé dans
`data/archive/<AAAA-MM-JJ_HHhMMmSS>/` (copie des fichiers d'entrée et
de sortie), et journalisé dans `data/history.db`.

### Option B — Ligne de commande



1. Déposez dans `data/input/` les 5 fichiers réels : 3 rapports de shift et
   les fichiers MASTERYD import/export. **Le nom des fichiers n'a aucune
   importance** : ils sont identifiés par leur contenu (voir section 3bis).

2. Déposez le template vierge dans `data/template/`. Là aussi, **n'importe
   quel nom de fichier fonctionne**, tant que le fichier a la structure du
   template TPFREP.

3. Lancez :

```bash
python main.py
```

4. Résultats dans `data/output/` :
   - `TPFREP_FINAL.xlsx` — le rapport TPFREP rempli
   - `DASHBOARD.xlsx` — tableau de bord (KPIs, par opérateur, productivité
     grues, répartition ISO, avec graphiques)

   Journal complet dans `logs/application.log`.

## 3bis. Découverte des fichiers par contenu (pas par nom)

`src/import_data.py` n'utilise **aucun motif de nom de fichier**. Chaque
`.xlsx` trouvé dans `data/input/` et `data/template/` est ouvert et identifié
par sa structure réelle :

| Type de fichier | Signature recherchée |
|---|---|
| Template TPFREP | Texte `"TERMINAL DEPARTURE AND PERFORMANCE REPORT"` dans les 10 premières lignes, ou à défaut plus de 100 cellules à remplissage indexé 44 (le bleu du template) |
| Rapport de shift | Une cellule contenant `"Portiques"` dans les 15 premières lignes (en-tête de la table grues) |
| Fichier MASTERYD | En-tête (ligne 1) contenant à la fois les colonnes `"Nø CONTENEUR"` et `"EXPLOITANT EN COURS"` |
| Direction IMPORT vs EXPORT | Valeur majoritaire de la colonne `"EXP IMP TRB"` (`'I'` ou `'E'`) — **le nom du fichier n'est jamais consulté pour cette décision** |
| Numéro de Shift (1/2/3) | Texte `"SHIFT n"` / `"n eme shift"` trouvé dans la feuille ; si absent, le fichier est ordonné par l'heure DOC la plus précoce de sa table grues (les shifts se suivent chronologiquement dans la journée) |

Conséquences pratiques :
- Vous pouvez renommer les fichiers comme vous voulez (`fichier1.xlsx`,
  `export_final_v3.xlsx`, sans extension de date, etc.) : le pipeline
  fonctionne à l'identique.
- Si **plusieurs fichiers** correspondent à la même signature (ex : deux
  fichiers ressemblant à un template), le premier trouvé est utilisé et un
  avertissement est journalisé — vérifiez `logs/application.log` dans ce cas.
- Si **aucun fichier** ne correspond à une signature attendue (ex : aucun
  fichier MASTERYD reconnu), `InputDiscoveryError` est levée avec un message
  explicite plutôt que de planter silencieusement.
- Un fichier `.xlsx` parasite (qui ne correspond à aucune signature) est
  simplement ignoré, avec une trace en niveau DEBUG.



## 4. Configuration

Toute la configuration a été externalisée dans `config/settings.yaml` pour permettre une exécution générique et multi-navires sans modification du code source.

### Paramètres dynamiques (détectés ou calculés automatiquement)
Le pipeline extrait ou calcule automatiquement les valeurs suivantes à partir des données d'entrée :
- **Nom du Navire et Escale** : Déduits dynamiquement depuis les fichiers de shift et les colonnes `ESCALE` des fichiers MASTERYD.
- **Voyage** : Extrait en priorité depuis une colonne dédiée `VOYAGE` ou `N° VOYAGE` du MASTERYD, ou par recherche de segments mixtes dans la valeur `ESCALE` ou le nom du fichier template.
- **Sessions grues** : Localisées et appariées dynamiquement dans le template (lignes et colonnes bleues de la section grue) avec tri chronologique et détection des franchissements de minuit.
- **Totaux grues** : Cherchés et écrits dynamiquement à la suite des sessions.

### Paramètres à ajuster manuellement dans `config/settings.yaml`
Si vous traitez un navire sur un autre terminal ou port, seuls les éléments suivants de `config/settings.yaml` doivent être mis à jour :
- **`terminal.vessel_port_unlocode`** : Code UN/LOCODE du port d'escale (ex: `MACAS`, `GBHUL`...).
- **`terminal.terminal_code`** : Code du terminal portuaire (ex: `SOMAPORT`, `NHVTERMINAL`...).
- **`cranes.crane_ids` et `cranes.template_column`** : Liste des identifiants des grues et colonnes Excel correspondantes (0-indexed).
- **`template_layout`** : Numéros de lignes du template pour les sessions, les totaux, et les tableaux de conteneurs.

Le mapping complet **Cellule Excel -> Source -> Transformation** reste disponible de façon exécutable et auditable dans `src/report_mapping.py` (`build_full_mapping()` retourne la liste complète ; `mapping_to_dataframe()` permet de l'exporter en CSV pour audit).

## 5. Ce qui est rempli automatiquement — et ce qui ne l'est pas

D'après l'inspection réelle des fichiers fournis :

**Rempli automatiquement :**
- Identification navire (nom du navire, voyage, port, terminal, exploitant)
- Sessions grues (DOC/FOC) par grue, par shift, avec gestion du
  franchissement de minuit
- Total des mouvements par grue
- Conteneurs déchargés/chargés par opérateur, ventilés Full/Empty x 20'/40'+45'
- `First Crane Lift` / `Last Crane Lift` : **non écrits** par le code — ce
  sont des formules Excel déjà présentes dans le template
  (`=MIN(...)`/`=MAX(...)`) qui se recalculent automatiquement à l'ouverture

**NON rempli (donnée absente des fichiers sources fournis), avec
avertissement explicite dans les logs :**
- Section 1.1 Vessel Timesheet (Planned/Actual Arrival/Departure, Lashing
  Gangs ON/OFF) : ces informations ne figurent dans aucun rapport de shift
  réel fourni (qui ne contient que les heures DOC/FOC par grue)
- Section 5.1 Restow par opérateur : aucun détail de restow conteneur par
  opérateur dans IMPORT/EXPORT MASTERYD
- Section 6 Hatch Cover Moves : absent des fichiers fournis
- Section 7 Break Bulk Moves : absent des fichiers fournis
- Section 1.2 General Delays : rempli **uniquement** si la table "Nature de
  retard" du rapport de shift contient des entrées valides ; le code de
  catégorie EDIFACT (PLT/LAS/WEA/MSC...) n'étant pas fourni dans la source,
  la catégorie générique `MSC` est utilisée par défaut — à corriger
  manuellement si la vraie cause est connue.

Ces sections resteront vides dans `TPFREP_FINAL.xlsx` ; complétez-les
manuellement dans Excel si l'information existe ailleurs.

## 6. Contrôle de cohérence intégré

À chaque exécution, le pipeline vérifie que le total des mouvements grues
(somme import+export saisie dans les rapports de shift, pour le navire
cible) correspond exactement au nombre d'enregistrements conteneurs
(IMPORT + EXPORT MASTERYD, filtrés sur la même escale). Le résultat
(`OK` ou `ÉCART DÉTECTÉ`) est journalisé et reporté dans la feuille `KPIs`
du dashboard — un écart signale typiquement un mauvais filtrage par navire
ou un fichier source incomplet.

## 7. Tests

```bash
python -m pytest tests/ -v
```

92 tests couvrant : normalisation et validation (utils), nettoyage des
conteneurs et des tables grues/retards (cleaning), fusion sur le navire
cible avec gestion du franchissement de minuit (merge), calcul des KPIs et
du contrôle de cohérence (calculations), la protection en écriture du
template (seules les cellules bleues sans formule existante sont
modifiées), et la découverte de fichiers par contenu indépendamment de
leur nom (content_detection).

## 8. Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| `InputDiscoveryError: Aucun template TPFREP reconnu` | Le fichier template n'a pas la signature attendue (texte du titre ou >100 cellules bleues indexées 44) | Vérifiez que le bon fichier est présent et qu'il n'a pas été altéré (styles supprimés, etc.) |
| `InputDiscoveryError: Seulement N rapport(s) de shift reconnu(s)` | Un ou plusieurs rapports de shift n'ont pas de cellule contenant "Portiques" dans les 15 premières lignes | Vérifiez la structure du fichier (table grues présente et non décalée) |
| `Colonnes obligatoires manquantes` | En-têtes du fichier MASTERYD différents de l'attendu | Comparez avec `REQUIRED_MASTERYD_COLUMNS` dans `src/validation.py` |
| `Aucun fichier MASTERYD de direction IMPORT/EXPORT reconnu` | La colonne `EXP IMP TRB` est absente ou ne contient aucune valeur 'I'/'E' exploitable | Vérifiez le contenu réel de cette colonne (pas le nom du fichier, qui n'est jamais utilisé) |
| Numéro de shift mal assigné (log "assigné par ordre chronologique") | Aucun texte "SHIFT n" trouvé dans la feuille | Vérifiez l'heure DOC de la première grue active de chaque fichier — c'est elle qui détermine l'ordre de repli |
| `Aucun conteneur trouvé pour le navire cible` après filtrage | La valeur `ESCALE` des fichiers MASTERYD ne contient pas le nom du navire cible normalisé | Vérifiez `config.TARGET_VESSEL_NORMALIZED` et la colonne `ESCALE` des fichiers |
| `Contrôle de cohérence ÉCHOUÉ` | Écart entre mouvements grues et enregistrements conteneurs | Vérifiez que les rapports de shift et les fichiers MASTERYD correspondent bien à la même escale/journée |
| Cellule attendue restée vide dans `TPFREP_FINAL.xlsx` | La cellule du template n'est pas réellement de couleur indexée 44, ou contient déjà une formule | Consultez `logs/application.log` (niveau DEBUG) pour voir les lignes `SKIP` |
| `pip install` échoue sur `xlsxwriter`/`openpyxl` | Environnement Python non isolé | Utilisez un environnement virtuel (`venv`) comme indiqué en section 1 |

Pour un diagnostic complet, consultez `logs/application.log`, qui
journalise chaque étape (import, validation, nettoyage, fusion, calculs,
génération) avec le détail des cellules écrites ou ignorées.
