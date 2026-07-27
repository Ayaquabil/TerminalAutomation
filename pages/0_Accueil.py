"""
pages/0_Accueil.py — Executive Dashboard d'accueil SOMAPORT.
"""

import sys
import importlib
import streamlit as st
from datetime import datetime
from src.ui_theme import inject_theme, stat_card, section_title, hero_header, kpi_row, COLORS
# ── Rechargement forcé pour éviter le cache Streamlit ──────────────────────
for _mod in ["src.ui_theme"]:
    if _mod in sys.modules:
        importlib.reload(sys.modules[_mod])

import config
from src.database import HistoryDB

# On s'assure que le thème est injecté
inject_theme()

# ── Récupération dynamique des statistiques depuis la base de données ──────
db = HistoryDB(config.DATABASE_FILE)
entries = db.list_entries(limit=100)

# Valeurs de démonstration par défaut
last_vessel = "MSC BEIJING"
containers_today = "1 540"
avg_time = "2.8 s"
sys_avail = "99.8 %"
last_sync = "Il y a 5 min"
archived_count = "156"

if entries:
    success_entries = [e for e in entries if e.get("status") == "SUCCESS"]
    if success_entries:
        last_vessel = success_entries[0].get("vessel_name") or "MSC BEIJING"
        
        last_containers_val = success_entries[0].get("total_containers") or 0
        containers_today = f"{last_containers_val:,}".replace(",", " ")
            
        times = [e.get("duration_seconds") for e in success_entries if e.get("duration_seconds")]
        if times:
            avg_time = f"{sum(times)/len(times):.1f} s"
            
        total_runs = len(entries)
        success_runs = len(success_entries)
        sys_avail = f"{(success_runs / total_runs) * 100:.1f} %"
        
        last_sync_raw = success_entries[0].get("run_at", "")
        try:
            dt = datetime.fromisoformat(last_sync_raw)
            last_sync = dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            last_sync = last_sync_raw
            
        archived_count = f"{success_runs}"

# ── Hero ───────────────────────────────────────────────────────────────────
st.markdown(
    hero_header(
        title="Plateforme SOMAPORT",
        subtitle="Système de gestion et d'automatisation des rapports d'escale — TPFREP, Dashboard BI et suivi opérationnel.",
        chips=["Gestion d'Escale", "Rapports TPFREP", "Dashboard BI", "Audit & Traçabilité"]
    ),
    unsafe_allow_html=True,
)

# ── Executive KPIs ────────────────────────────────────────────────────────
st.markdown(section_title("Tableau de bord de direction"), unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
st.markdown("<br>", unsafe_allow_html=True)
col4, col5, col6 = st.columns(3)

# Utilisation des Material Symbols (directions_boat, inventory_2, etc.)
kpis = [
    (col1, last_vessel,      "Dernier navire",            "directions_boat", ""),
    (col2, containers_today, "Conteneurs traités",        "inventory_2",     ""),
    (col3, avg_time,         "Temps génération",          "speed",           ""),
    (col4, sys_avail,        "Disponibilité système",     "check_circle",    "success"),
    (col5, last_sync,        "Dernière synchronisation",  "sync",            ""),
    (col6, archived_count,   "Rapports archivés",         "folder_zip",      ""),
]

for col, val, lbl, ico, color in kpis:
    with col:
        st.markdown(stat_card(val, lbl, ico, color), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Cycle de Traitement ───────────────────────────────────────────────────
st.markdown(
    section_title("Cycle de traitement des données"),
    unsafe_allow_html=True,
)

# Pipeline avec Material Symbols
st.markdown(
    """<div class="ta-card ta-animate" style="width:100%; padding:2.5rem; margin-top:1rem; margin-bottom:2rem;">
<div style="display:flex; justify-content:space-between; align-items:center; gap:0.5rem; flex-wrap:wrap;">
    <div class="pipeline-step"><div class="pipeline-icon"><span class="mat-icon">upload_file</span></div><div class="pipeline-title">Import</div></div>
    <div class="pipeline-arrow"><span class="mat-icon">arrow_forward_ios</span></div>
    <div class="pipeline-step"><div class="pipeline-icon"><span class="mat-icon">rule</span></div><div class="pipeline-title">Validation</div></div>
    <div class="pipeline-arrow"><span class="mat-icon">arrow_forward_ios</span></div>
    <div class="pipeline-step"><div class="pipeline-icon"><span class="mat-icon">cleaning_services</span></div><div class="pipeline-title">Nettoyage</div></div>
    <div class="pipeline-arrow"><span class="mat-icon">arrow_forward_ios</span></div>
    <div class="pipeline-step"><div class="pipeline-icon"><span class="mat-icon">merge</span></div><div class="pipeline-title">Fusion</div></div>
    <div class="pipeline-arrow"><span class="mat-icon">arrow_forward_ios</span></div>
    <div class="pipeline-step"><div class="pipeline-icon"><span class="mat-icon">query_stats</span></div><div class="pipeline-title">Calcul KPI</div></div>
    <div class="pipeline-arrow"><span class="mat-icon">arrow_forward_ios</span></div>
    <div class="pipeline-step"><div class="pipeline-icon"><span class="mat-icon">description</span></div><div class="pipeline-title">TPFREP</div></div>
    <div class="pipeline-arrow"><span class="mat-icon">arrow_forward_ios</span></div>
    <div class="pipeline-step"><div class="pipeline-icon"><span class="mat-icon">stacked_bar_chart</span></div><div class="pipeline-title">Dashboard BI</div></div>
</div>
</div>""",
    unsafe_allow_html=True,
)# ── Navigation rapide ──────────────────────────────────────────────────────
st.markdown(section_title("Navigation rapide"), unsafe_allow_html=True)

nav_cards = [
    ("cloud_upload", "Traitement",   "Importer les rapports de shift et lancer le pipeline.", "./traitement"),
    ("analytics",    "Dashboard BI", "KPIs, graphiques et analyse de performance.",             "./dashboard"),
    ("history",      "Historique",   "Traçabilité complète des runs et archives.",                "./historique"),
]

nav_cols = st.columns(3)
for col, (icon, title, desc, page) in zip(nav_cols, nav_cards):
    with col:
        st.markdown(
            f"""
            <a href="{page}" target="_self" style="text-decoration: none; color: inherit; display: block;">
                <div class="ta-card ta-animate" style="text-align:center; padding:1.8rem 1.2rem; min-height: 235px; display: flex; flex-direction: column; justify-content: space-between; margin-bottom: 1rem;">
                    <div>
                        <div style="margin-bottom:0.75rem; color:{COLORS['accent']};">
                            <span class="mat-icon" style="font-size: 2.4rem;">{icon}</span>
                        </div>
                        <div style="
                            font-size:1rem; font-weight:600;
                            color:{COLORS['text_primary']};
                            font-family:'Onest',sans-serif;
                            text-transform:uppercase;
                            letter-spacing:0.04em;
                            margin-bottom:0.6rem;
                        ">{title}</div>
                        <div style="
                            font-size:0.84rem; font-weight:400;
                            color:{COLORS['text_muted']};
                            font-family:'Roboto',sans-serif;
                            line-height:1.5;
                            margin-bottom:1rem;
                        ">{desc}</div>
                    </div>
                    <div style="border-top: 1px solid {COLORS['border_glass']}; padding-top: 0.8rem; text-align: center; color: {COLORS['accent']}; font-weight: 600; font-size: 0.9rem; font-family: 'Onest', sans-serif; text-transform: uppercase; letter-spacing: 0.05em;">
                        Ouvrir &rarr;
                    </div>
                </div>
            </a>
            """,
            unsafe_allow_html=True,
        )