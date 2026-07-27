import sys
import importlib
import streamlit as st

# ── Rechargement forcé pour éviter le cache Streamlit ──────────────────────
for _mod in ["src.ui_theme", "src.top_navbar"]:
    if _mod in sys.modules:
        importlib.reload(sys.modules[_mod])

from src.ui_theme import inject_theme
from src.top_navbar import top_navbar

# ── Configuration globale de la page ───────────────────────────────────────
# (Appel unique obligatoire au tout début de l'exécution)
st.set_page_config(
    page_title="Terminal Automation BI — SOMAPORT",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Injection globale du thème
inject_theme()

# Définition des pages de l'application
pages = [
    st.Page("pages/0_Accueil.py", title="Accueil", default=True),
    st.Page("pages/1_Traitement.py", title="Traitement", url_path="traitement"),
    st.Page("pages/2_Dashboard_BI.py", title="Dashboard BI", url_path="dashboard"),
    st.Page("pages/3_Historique.py", title="Historique", url_path="historique"),
   
]

# Initialisation de la navigation avec la sidebar masquée
pg = st.navigation(pages, position="hidden")

# Rendu de la Top Navigation Bar personnalisée
current_path = pg.url_path if pg else ""
top_navbar(current_path)

# Exécution de la page courante
pg.run()