"""
src/ui_theme.py — Design System SOMAPORT pour TerminalAutomation.

Palette officielle SOMAPORT :
  • Fond app        : #FAF9F6 (Off-white / Coquille d'œuf)
  • Fond carte      : Translucide avec effet Glassmorphism
  • Sidebar dark    : #001523 (bg-dark-blue)
  • Accent          : #00607A (blue-medium-light / vert logo)
  • Accent dark     : #011E35
  • Texte titre     : #333333 (primary)
  • Texte courant   : #5A5A5A (text)
  • Succès          : #1B6B3A
  • Erreur          : #B91C1C
  • Avertissement   : #92400E

Typographie :
  • Titres (H1-H6) : Onest (Google Fonts)
  • Corps / labels  : Roboto 300/400 (Google Fonts)
"""

import streamlit as st

COLORS = {
    "bg_app":        "#FFFFFF",
    "bg_glass":      "rgba(255, 255, 255, 0.65)",
    "bg_dark":       "#001523",
    "bg_blue1":      "#0B455C",
    "bg_blue2":      "#011E35",
    "accent":        "#8BB346",
    "accent_light":  "rgba(139, 179, 70, 0.1)",
    "accent_dark":   "#011E35",
    "text_primary":  "#2D3748",
    "text_muted":    "#64748B",
    "text_on_dark":  "#F8FAFC",
    "success":       "#059669",
    "success_bg":    "rgba(5, 150, 105, 0.1)",
    "warning":       "#D97706",
    "warning_bg":    "rgba(217, 119, 6, 0.1)",
    "error":         "#DC2626",
    "error_bg":      "rgba(220, 38, 38, 0.1)",
    "border_light":  "rgba(255, 255, 255, 0.6)",
    "border_glass":  "rgba(139, 179, 70, 0.15)",
}

def inject_theme() -> None:
    """Injecte le Design System SOMAPORT Glassmorphism dans Streamlit."""
    
    css = f"""
<!-- Ajout de Google Material Symbols pour les icônes pro -->
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,300,0,0" rel="stylesheet" />
<link href="https://fonts.googleapis.com/css2?family=Onest:wght@300;400;500;600;700&family=Roboto:wght@300;400;500&display=swap" rel="stylesheet">
<style>
    /* --- VARIABLES GLOBALES --- */
    :root {{
        --font-title: 'Onest', system-ui, sans-serif;
        --font-body: 'Roboto', system-ui, sans-serif;
        --color-accent: {COLORS['accent']};
        --color-bg-app: {COLORS['bg_app']};
        --color-bg-glass: {COLORS['bg_glass']};
        --color-bg-dark: {COLORS['bg_dark']};
        --color-text: {COLORS['text_primary']};
        --color-muted: {COLORS['text_muted']};
        --shadow-soft: 0 4px 20px rgba(0, 0, 0, 0.03), 0 1px 3px rgba(0, 0, 0, 0.02);
        --shadow-hover: 0 10px 30px rgba(0, 96, 122, 0.08), 0 4px 10px rgba(0, 0, 0, 0.04);
        --radius-lg: 16px;
        --radius-md: 8px;
        --transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    }}

    /* --- CLASSE ICONE PRO --- */
    .mat-icon {{
        font-family: 'Material Symbols Rounded';
        font-weight: normal;
        font-style: normal;
        line-height: 1;
        letter-spacing: normal;
        text-transform: none;
        display: inline-block;
        white-space: nowrap;
        word-wrap: normal;
        direction: ltr;
        -webkit-font-feature-settings: 'liga';
        -webkit-font-smoothing: antialiased;
    }}

    /* --- FOND & MASQUAGE NATIVE --- */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
        background-color: var(--color-bg-app) !important;
        background-image: 
            radial-gradient(at 0% 0%, rgba(0, 96, 122, 0.03) 0px, transparent 50%),
            radial-gradient(at 100% 100%, rgba(0, 96, 122, 0.03) 0px, transparent 50%);
        background-attachment: fixed;
    }}
    #MainMenu, footer {{visibility: hidden;}}
    .block-container {{ padding-top: 2rem !important; max-width: 1400px; }}

    /* --- TYPOGRAPHIE --- */
    h1, h2, h3, h4, h5, h6, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {{
        font-family: var(--font-title) !important;
        color: var(--color-text) !important;
        letter-spacing: -0.02em;
    }}
    p, span, div, label {{
        font-family: var(--font-body);
        color: var(--color-text);
    }}

    /* --- OVERRIDES NATIVE STREAMLIT --- */
    .stButton > button,
    [data-testid="stDownloadButton"] > button {{
        background: linear-gradient(135deg, {COLORS['accent']}, {COLORS['bg_blue1']}) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: var(--radius-md) !important;
        padding: 0.6rem 1.5rem !important;
        font-family: var(--font-title) !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px !important;
        box-shadow: 0 4px 12px rgba(139, 179, 70, 0.25) !important;
        transition: var(--transition) !important;
        width: 100% !important;
    }}
    .stButton > button *,
    [data-testid="stDownloadButton"] > button * {{
        color: #FFFFFF !important;
        fill: #FFFFFF !important;
    }}
    .stButton > button:hover,
    [data-testid="stDownloadButton"] > button:hover {{
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 20px rgba(139, 179, 70, 0.4) !important;
        background: linear-gradient(135deg, {COLORS['bg_blue1']}, {COLORS['accent']}) !important;
    }}
    
    [data-testid="stFileUploadDropzone"] {{
        background: var(--color-bg-glass) !important;
        border: 1px dashed {COLORS['border_glass']} !important;
        border-radius: var(--radius-lg) !important;
        backdrop-filter: blur(12px);
        transition: var(--transition);
    }}
    [data-testid="stFileUploadDropzone"]:hover {{
        background: rgba(255, 255, 255, 0.9) !important;
        border-color: var(--color-accent) !important;
    }}

    [data-testid="stSidebar"] {{
        background-color: var(--color-bg-dark) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }}
    [data-testid="stSidebar"] * {{
        color: {COLORS['text_on_dark']} !important;
    }}

    /* --- GLASSMORPHISM CARDS --- */
    .ta-card {{
        background: var(--color-bg-glass);
        backdrop-filter: blur(20px) saturate(160%);
        -webkit-backdrop-filter: blur(20px) saturate(160%);
        border: 1px solid {COLORS['border_light']};
        border-radius: var(--radius-lg);
        box-shadow: var(--shadow-soft);
        transition: var(--transition);
        position: relative;
        overflow: hidden;
    }}
    .ta-card::before {{
        content: "";
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 1px;
        background: linear-gradient(90deg, rgba(255,255,255,0.8), rgba(255,255,255,0.2));
    }}
    .ta-animate:hover {{
        transform: translateY(-4px);
        box-shadow: var(--shadow-hover);
        border: 1px solid {COLORS['border_glass']};
    }}

    /* --- KPIS & STATS --- */
    .ta-stat {{
        padding: 16px 18px;
        text-align: left;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 110px;
        height: 110px;
        box-sizing: border-box;
    }}
    .ta-stat-header {{
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
        color: var(--color-muted);
        font-family: var(--font-title);
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-size: 0.72rem;
    }}
    .ta-stat-icon {{
        font-size: 1.1rem;
        color: var(--color-accent);
        display: flex;
        align-items: center;
    }}
    .ta-stat-value {{
        font-size: 1.65rem;
        font-weight: 600;
        color: var(--color-text);
        margin: 0;
        font-family: var(--font-title);
        line-height: 1.1;
    }}
    .ta-stat-value.success {{ color: {COLORS['success']}; font-weight: 600; }}
    .ta-stat-value.error {{ color: {COLORS['error']}; font-weight: 600; }}

    /* --- TITRES DE SECTION --- */
    .ta-section-title {{
        font-family: var(--font-title);
        font-size: 1.2rem;
        font-weight: 500;
        color: var(--color-text);
        margin: 2.5rem 0 1.5rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid {COLORS['border_glass']};
    }}

    /* --- BADGES ET CHIPS --- */
    .ta-badge {{
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        font-family: var(--font-title);
        text-transform: uppercase;
    }}
    .ta-badge-success {{ background: {COLORS['success_bg']}; color: {COLORS['success']}; }}
    .ta-badge-warning {{ background: {COLORS['warning_bg']}; color: {COLORS['warning']}; }}
    .ta-badge-error {{ background: {COLORS['error_bg']}; color: {COLORS['error']}; }}
    .ta-badge-info {{ background: {COLORS['accent_light']}; color: {COLORS['accent']}; }}
    
    .ta-chip {{
        background: transparent;
        border: 1px solid {COLORS['border_glass']};
        color: var(--color-muted);
        padding: 4px 16px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 500;
        letter-spacing: 0.02em;
    }}

    /* --- PIPELINE VISUALISATION --- */
    .pipeline-step {{
        display: flex;
        flex-direction: column;
        align-items: center;
        color: var(--color-text);
    }}
    .pipeline-icon {{
        font-size: 1.6rem;
        margin-bottom: 0.5rem;
        background: transparent;
        border: 1px solid {COLORS['border_glass']};
        color: var(--color-accent);
        width: 56px;
        height: 56px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        transition: var(--transition);
    }}
    .pipeline-step:hover .pipeline-icon {{
        transform: scale(1.1);
        background: var(--color-accent);
        color: white;
        border-color: var(--color-accent);
        box-shadow: 0 4px 12px rgba(0,96,122,0.2);
    }}
    .pipeline-title {{
        font-weight: 500;
        font-size: 0.85rem;
        color: var(--color-muted);
    }}
    .pipeline-arrow {{
        color: {COLORS['border_glass']};
        font-size: 1.5rem;
        display: flex;
        align-items: center;
    }}
</style>
"""
    st.markdown(css, unsafe_allow_html=True)


def badge(status: str, text: str) -> str:
    """Retourne une pastille de statut textuelle stricte."""
    return f'<span class="ta-badge ta-badge-{status}">{text}</span>'


def stat_card(value: str, label: str, icon: str = "", color: str = "") -> str:
    """Retourne une carte KPI SOMAPORT au format Glassmorphism avec Material Symbols."""
    color_class = f" {color}" if color else ""
    
    # Remplacement par l'icône Material
    icon_html = ""
    if icon:
        icon_html = f'<div class="ta-stat-icon{color_class}"><span class="mat-icon">{icon}</span></div>'
        
    return (
        f'<div class="ta-card ta-stat ta-animate">'
        f'  <div class="ta-stat-header">'
        f'    {icon_html}'
        f'    <div class="ta-stat-label">{label}</div>'
        f'  </div>'
        f'  <div class="ta-stat-value{color_class}">{value}</div>'
        f'</div>'
    )


def section_title(text: str) -> str:
    """Retourne un titre de section souligné."""
    return f'<div class="ta-section-title">{text}</div>'


def chip(text: str) -> str:
    """Retourne un chip d'information minimaliste."""
    return f'<span class="ta-chip">{text}</span>'


def hero_header(title: str, subtitle: str, chips: list | None = None) -> str:
    """Retourne un en-tête Hero SOMAPORT épuré."""
    chips_html = ""
    if chips:
        chip_items = " ".join(f'<span class="ta-chip">{c}</span>' for c in chips)
        chips_html = (
            f'<div style="display:flex;gap:0.75rem;flex-wrap:wrap;margin-top:1.5rem;">'
            f'{chip_items}</div>'
        )
    return f"""
<div class="ta-animate" style="margin-bottom:3rem; padding: 2rem; background: var(--color-bg-glass); backdrop-filter: blur(20px); border-radius: 16px; border: 1px solid {COLORS['border_light']}; box-shadow: var(--shadow-soft);">
    <h1 style="margin:0 0 0.5rem 0; font-size: 2.2rem; font-weight: 600;">{title}</h1>
    <p style="margin:0;font-size:1.05rem;font-weight:300;color:{COLORS['text_muted']};
              line-height:1.6;max-width:800px;">{subtitle}</p>
    {chips_html}
</div>
"""


def kpi_row(stats: list) -> str:
    """Retourne une rangée de cartes KPI structurée."""
    cards = "".join(
        stat_card(
            value=s.get("value", ""),
            label=s.get("label", ""),
            icon=s.get("icon", ""),
            color=s.get("color", ""),
        )
        for s in stats
    )
    return (
        f'<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));'
        f'gap:1.5rem; margin-bottom: 2rem;">{cards}</div>'
    )

def badge(status: str, text: str) -> str:
    """Retourne une pastille de statut textuelle stricte."""
    return f'<span class="ta-badge ta-badge-{status}">{text}</span>'


def stat_card(value: str, label: str, icon: str = "", color: str = "") -> str:
    """Retourne une carte KPI SOMAPORT au format Glassmorphism."""
    color_class = f" {color}" if color else ""
    return (
        f'<div class="ta-card ta-stat ta-animate">'
        f'  <div class="ta-stat-header">'
        f'    <div class="ta-stat-label">{label}</div>'
        f'  </div>'
        f'  <div class="ta-stat-value{color_class}">{value}</div>'
        f'</div>'
    )


def section_title(text: str) -> str:
    """Retourne un titre de section souligné."""
    return f'<div class="ta-section-title">{text}</div>'


def chip(text: str) -> str:
    """Retourne un chip d'information minimaliste."""
    return f'<span class="ta-chip">{text}</span>'


def hero_header(title: str, subtitle: str, chips: list | None = None) -> str:
    """Retourne un en-tête Hero SOMAPORT épuré."""
    chips_html = ""
    if chips:
        chip_items = " ".join(f'<span class="ta-chip">{c}</span>' for c in chips)
        chips_html = (
            f'<div style="display:flex;gap:0.75rem;flex-wrap:wrap;margin-top:1.5rem;">'
            f'{chip_items}</div>'
        )
    return f"""
<div class="ta-animate" style="margin-bottom:3rem; padding: 2rem; background: var(--color-bg-glass); backdrop-filter: blur(20px); border-radius: 16px; border: 1px solid {COLORS['border_light']}; box-shadow: var(--shadow-soft);">
    <h1 style="margin:0 0 0.5rem 0; font-size: 2.2rem; font-weight: 600;">{title}</h1>
    <p style="margin:0;font-size:1.05rem;font-weight:300;color:{COLORS['text_muted']};
              line-height:1.6;max-width:800px;">{subtitle}</p>
    {chips_html}
</div>
"""


def kpi_row(stats: list) -> str:
    """Retourne une rangée de cartes KPI structurée."""
    cards = "".join(
        stat_card(
            value=s.get("value", ""),
            label=s.get("label", ""),
            icon=s.get("icon", ""),
            color=s.get("color", ""),
        )
        for s in stats
    )
    return (
        f'<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));'
        f'gap:1.5rem; margin-bottom: 2rem;">{cards}</div>'
    )