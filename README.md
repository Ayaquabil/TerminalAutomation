# TerminalAutomation — Plateforme BI & Automatisation TPFREP

Automatisation du remplissage du rapport **TPFREP** (Terminal Departure and Performance Report, format UN/EDIFACT SMDG 3.0) à partir des fichiers opérationnels réels du terminal **SOMAPORT** : rapports de shift et listes de mouvements conteneurs (IMPORT/EXPORT).

Le pipeline importe, valide, nettoie, fusionne et calcule les indicateurs, puis remplit **uniquement les cellules bleues autorisées** du template Excel officiel (les formules, styles, fusions, bordures et cellules non bleues restent strictement protégés). Il génère également un classeur Dashboard Excel (`DASHBOARD.xlsx`), assure une traçabilité complète en base SQLite.

---

## 1. Installation

**Prérequis** : Python 3.12 (ou version supérieure).

```bash
# Se placer dans le dossier du projet
cd TerminalAutomation

# Créer et activer l'environnement virtuel
python3 -m venv venv
source venv/bin/activate          # Sur Windows : venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt
```

---

## 2. Structure du projet

```
TerminalAutomation/
├── app.py                    # Point d'entrée Streamlit (Top Navbar & Routing)
├── config.py                 # Pont de configuration vers settings.yaml
├── main.py                   # Point d'entrée CLI (exécution en ligne de commande)
├── requirements.txt          # Dépendances Python (streamlit, openpyxl, pandas, plotly, reportlab...)
├── README.md
├── config/
│   └── settings.yaml         # Configuration métier externalisée (terminal, grues, couleurs, seuils)
├── pages/                    # Interface Web Streamlit (4 pages)
│   ├── 0_Accueil.py          # Vue d'ensemble et accès rapide
│   ├── 1_Traitement.py       # Upload de fichiers, validation et exécution du pipeline
│   ├── 2_Dashboard_BI.py     # Graphiques interactifs et indicateurs de performance
│   └── 3_Historique.py       # Centre d'audit, traçabilité et suppression des traitements
├── src/
│   ├── logger.py             # Logging structuré (fichier + console)
│   ├── utils.py               # Parsing dates, normalisation navires, validation ISO conteneurs
│   ├── import_data.py         # Découverte intelligente et chargement des fichiers Excel (.xlsx/.xls)
│   ├── validation.py          # Contrôle de cohérence, validation des colonnes et des dates
│   ├── cleaning.py            # Structuration et nettoyage des DataFrames conteneurs & shifts
│   ├── merge.py               # Fusion dynamique shift + import/export et résolution navire/escale/voyage
│   ├── calculations.py        # Calcul des KPIs, productivité grues et contrôle de cohérence
│   ├── report_mapping.py      # Cartographie auditable (Cellule Excel -> Source -> Transformation)
│   ├── report_generator.py    # Moteur de remplissage dynamique et protégé du TPFREP (openpyxl)
│   ├── dashboard.py           # Génération du classeur Excel DASHBOARD.xlsx (XlsxWriter)
│   ├── database.py            # Journalisation et gestion de l'historique SQLite (data/history.db)
│   ├── archiving.py          # Archivage horodaté automatique des exécutions (data/archive/)
│   ├── settings_loader.py     # Chargeur de configuration YAML avec valeurs de repli
│   ├── ui_theme.py            # Design system SOMAPORT (charte graphique, composants HTML/CSS)
│   └── top_navbar.py          # Barre de navigation supérieure Streamlit
├── tests/                     # Suite de tests automatisés pytest (92+ tests)
├── data/
│   ├── input/                 # Fichiers d'entrée déposés
│   ├── template/              # Template TPFREP vierge officiel
│   ├── output/                # Fichiers générés (TPFREP_FINAL.xlsx, DASHBOARD.xlsx)
│   ├── archive/               # Archives horodatées des exécutions
│   └── history.db             # Base de données SQLite de traçabilité
└── logs/
    └── application.log         # Journal complet d'exécution
```

---

## 3. Exécution

### Option A — Application Web BI (Recommandée)

```bash
streamlit run app.py
```

L'application s'ouvre dans le navigateur (`http://localhost:8501`) avec 4 pages principales :

| Page | Rôle & Fonctionnalités |
|---|---|
| **🏠 Accueil** | Synthèse globale des activités, accès rapide aux fonctionnalités et métriques clés. |
| **📥 Traitement** | Upload glisser-déposer des rapports de shift et fichiers import/export, sélection interactive en cas d'escales multiples, exécution du pipeline en 6 étapes avec progression visuelle et téléchargement des sorties (Excel  ). |
| **📊 Dashboard BI** | Visualisation analytique avancée : graphiques interactifs Plotly (Full/Empty, répartition ISO, productivité brut/nette des portiques, conteneurs par opérateur). |
| **🕓 Historique** | Centre d'audit complet : traçabilité de chaque run (succès/échec, durée, volume), timeline d'exécution, fichiers utilisés et **bouton de suppression des entrées** (`🗑️ Supprimer l'entrée`). |

### Option B — Ligne de commande (CLI)

1. Déposez dans `data/input/` vos rapports de shift et fichiers  (Import/Export).
2. Déposez dans `data/template/` le modèle TPFREP vierge.
3. Exécutez :
   ```bash
   python main.py
   ```
4. Retrouvez les résultats dans `data/output/` (`TPFREP_FINAL.xlsx` et `DASHBOARD.xlsx`).

---

## 4. Découverte intelligente des fichiers (par contenu)

Le pipeline n'impose aucun nom de fichier strict. Les fichiers `.xlsx` et `.xls` sont identifiés automatiquement selon leur structure :

| Type de fichier | Signature recherchée dans le contenu |
|---|---|
| **Template TPFREP** | Titre `"TERMINAL DEPARTURE AND PERFORMANCE REPORT"` ou présence de cellules bleues (index 44 / RVB `FF99CCFF`). |
| **Rapport de Shift** | Tableau d'en-tête de portiques avec la cellule `"Portiques"`. |
| **Fichier import/export** | Présence des colonnes `"Nø CONTENEUR"` et `"EXPLOITANT EN COURS"`. |
| **Sens IMPORT vs EXPORT** | Valeur majoritaire dans la colonne `"EXP IMP TRB"` (`I` pour Import, `E` pour Export). |

---

## 5. Fonctionnalités et Automatismes métier

- **Résolution dynamique du navire** : Le nom du navire est extrait dynamiquement des données de traitement (ex: `MASTERYD` ou `BELITAKI`) et directement inscrit dans la cellule **D8** du TPFREP, sans forcer de valeur fixe.
- **Section 1.1 Vessel Timesheet** : Calcul et remplissage automatique des dates/heures de berthing, lashing, arrival et departure à partir des sessions portiques.
- **Mouvements par Opérateur & Taille ISO** : Ventilation automatique des conteneurs (Discharged / Loaded) par opérateur et par taille (`20'`, `40'`, `45'`, Full / Empty).
- **Gestion des Retards & Break Bulk** : Identification dynamique des retards généraux/portiques et intégration des mouvements Break Bulk par opérateur (`CMA`, `TAR`, `MSL`, `Common`).
- **Protection intégrale du Template** : Seules les cellules bleues autorisées sans formule existante sont écrites. Les formules Excel du template (`=MIN()`, `=MAX()`, `=SUM()`) sont préservées.

---

## 6. Contrôle de cohérence & Audit

- **Contrôle de cohérence** : Vérification automatique entre le total des mouvements déclarés dans les shifts et le nombre d'enregistrements conteneurs dans les fichiers import/export.
- **Base de données SQLite (`data/history.db`)** : Chaque exécution est enregistrée pour des fins d'audit avec possibilité de suppression d'enregistrements depuis la page Historique.
- **Archivage automatique** : Sauvegarde des fichiers d'entrée, du template et des résultats générés dans `data/archive/<AAAA-MM-JJ_HHhMMmSS>/`.

---

## 7. Tests automatisés

Pour exécuter la suite complète de 92+ tests unitaire et d'intégration :

```bash
pytest tests/ -v
```

---

## 8. Support & Dépannage

- En cas d'erreur de traitement, consultez la page **Historique** ou le fichier journal `logs/application.log`.
- Pour ajuster les codes de port, de terminal ou les identifiants de portiques, modifiez le fichier `config/settings.yaml`.
