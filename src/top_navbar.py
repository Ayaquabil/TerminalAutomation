"""
src/top_navbar.py — Composant réutilisable pour la Top Navigation Bar SOMAPORT.
"""

import streamlit as st
import base64
from pathlib import Path
from src.ui_theme import COLORS

# ── Chemin du logo SOMAPORT ───────────────────────────────────────────
_LOGO_PATH = Path(__file__).parent.parent / "assets" / "somaport_logo.png"

def top_navbar(current_page_path: str = "") -> None:
    """
    Affiche une barre de navigation horizontale professionnelle et fixe en haut de la page.
    Masque complètement la sidebar native et les entêtes de Streamlit.
    """
    # Encodage du logo en base64 pour un rendu immédiat et sans requêtes HTTP externes
    if _LOGO_PATH.exists():
        try:
            img_b64 = base64.b64encode(_LOGO_PATH.read_bytes()).decode()
            logo_html = f'<img src="data:image/png;base64,{img_b64}" alt="SOMAPORT Logo" />'
        except Exception:
            logo_html = f'<div class="smp-navbar-fallback">SOMAPORT</div>'
    else:
        logo_html = f'<div class="smp-navbar-fallback">SOMAPORT</div>'

    # Définition des éléments du menu
    menu_items = [
        {"path": "", "label": "Accueil"},
        {"path": "traitement", "label": "Traitement"},
        {"path": "dashboard", "label": "Dashboard BI"},
        {"path": "historique", "label": "Historique"},
        
    ]

    # Normalisation du chemin courant
    normalized_active = current_page_path.strip("/").lower()

    links_html = ""
    for item in menu_items:
        is_active = (normalized_active == item["path"].lower())
        active_class = "active" if is_active else ""
        
        # Navigation relative compatible avec Streamlit st.navigation
        href = f"./{item['path']}" if item['path'] else "./"
        
        links_html += f"""
        <a href="{href}" class="smp-nav-link {active_class}" target="_self">
            <span class="smp-nav-label">{item['label']}</span>
        </a>
        """

    navbar_html = f"""
    <style>
    /* ── MASQUAGE DES ÉLÉMENTS STREAMLIT PAR DÉFAUT ── */
    header[data-testid="stHeader"] {{
        display: none !important;
    }}
    div[data-testid="stDecoration"] {{
        display: none !important;
    }}
    #MainMenu {{
        visibility: hidden !important;
    }}
    footer {{
        visibility: hidden !important;
    }}
    [data-testid="stToolbar"] {{
        display: none !important;
    }}
    
    /* Masquage de la Sidebar native */
    [data-testid="stSidebar"] {{
        display: none !important;
    }}
    [data-testid="collapsedControl"] {{
        display: none !important;
    }}
    section.main {{
        margin-left: 0 !important;
        padding-left: 0 !important;
        width: 100% !important;
    }}
    
    /* Ajustement de la zone de contenu sous la navbar fixe */
    .main .block-container {{
        padding: 5.5rem 2.5rem 2.5rem 2.5rem !important;
        max-width: 1400px !important;
        margin: 0 auto !important;
    }}
    
    /* ── BARRE DE NAVIGATION (TOP NAVBAR) ── */
    .smp-top-navbar {{
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 70px;
        background-color: #FFFFFF;
        border-bottom: 1px solid rgba(0, 0, 0, 0.08);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 3rem;
        z-index: 999999;
        box-sizing: border-box;
    }}
    
    .smp-navbar-left {{
        display: flex;
        align-items: center;
        gap: 3rem;
        height: 100%;
    }}
    
    .smp-navbar-logo {{
        display: flex;
        align-items: center;
        height: 48px;
        flex-shrink: 0;
    }}
    
    .smp-navbar-logo img {{
        height: 48px;
        width: auto;
        object-fit: contain;
    }}
    
    .smp-navbar-fallback {{
        font-family: 'Onest', sans-serif;
        font-size: 1.4rem;
        font-weight: 700;
        color: {COLORS['accent']};
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }}
    
    .smp-navbar-menu {{
        display: flex;
        align-items: center;
        gap: 0.5rem;
        height: 100%;
    }}
    
    .smp-nav-link {{
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0 1.25rem;
        height: 70px;
        color: {COLORS['text_primary']} !important;
        text-decoration: none !important;
        font-family: 'Roboto', sans-serif;
        font-weight: 500;
        font-size: 0.95rem;
        border-bottom: 3.5px solid transparent;
        transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1);
        box-sizing: border-box;
    }}
    
    .smp-nav-link:hover {{
        color: {COLORS['accent']} !important;
        background-color: {COLORS['accent_light']};
        border-bottom-color: {COLORS['accent']};
    }}
    
    .smp-nav-link.active {{
        color: {COLORS['accent']} !important;
        font-weight: 700;
        border-bottom: 3.5px solid {COLORS['accent']};
        background-color: {COLORS['accent_light']};
    }}
    
    .smp-nav-icon {{
        font-size: 1.1rem;
        display: flex;
        align-items: center;
    }}
    
    .smp-nav-label {{
        letter-spacing: 0.01em;
    }}
    
    .smp-navbar-right {{
        display: flex;
        align-items: center;
    }}
    
    .smp-navbar-tag {{
        font-family: 'Onest', sans-serif;
        font-size: 0.72rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        background: {COLORS['accent_light']};
        color: {COLORS['accent']};
        padding: 0.35rem 0.85rem;
        border-radius: 20px;
        border: 1px solid {COLORS['border_glass']};
        box-shadow: 0 2px 6px rgba(139, 179, 70, 0.06);
    }}
    </style>
    
    <div class="smp-top-navbar">
        <div class="smp-navbar-left">
            <div class="smp-navbar-logo">
                {logo_html}
            </div>
         
        </div>
        <div class="smp-navbar-right">
               <div class="smp-navbar-menu">
                {links_html}
            </div>
        </div>
    </div>
    """
    navbar_html_clean = "\n".join(line.strip() for line in navbar_html.split("\n"))
    st.markdown(navbar_html_clean, unsafe_allow_html=True)
