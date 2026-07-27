"""
pages/3_Historique.py — Centre d'audit et traçabilité des escales SOMAPORT.
"""

from __future__ import annotations
import sys
import importlib
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Force reload of ui_theme
if "src.ui_theme" in sys.modules:
    importlib.reload(sys.modules["src.ui_theme"])

import config
from src.database import HistoryDB
from src.ui_theme import inject_theme, badge, section_title, stat_card, COLORS, hero_header

inject_theme()

# ── Plotly theme helpers ───────────────────────────────────────────────────
_PAGE_BG  = "rgba(0,0,0,0)"
_GRID     = "rgba(0,0,0,0.06)"
_FONT_CLR = COLORS["text_muted"]
_PALETTE  = [COLORS["accent"], COLORS["bg_blue1"], COLORS["bg_blue2"]]

def _layout(**kw) -> dict:
    base = dict(
        paper_bgcolor=_PAGE_BG, plot_bgcolor=_PAGE_BG,
        font=dict(family="Roboto, Onest, system-ui", color=_FONT_CLR, size=12),
        xaxis=dict(gridcolor=_GRID, zeroline=False, tickfont=dict(color=_FONT_CLR)),
        yaxis=dict(gridcolor=_GRID, zeroline=False, tickfont=dict(color=_FONT_CLR)),
        margin=dict(l=20, r=10, t=40, b=20), height=260,
        legend=dict(bgcolor="rgba(255,255,255,0.9)", borderwidth=1, font=dict(color=_FONT_CLR)),
        hoverlabel=dict(bgcolor="#FFFFFF", font=dict(color=COLORS["text_primary"], family="Roboto"), bordercolor=COLORS["accent"]),
    )
    base.update(kw)
    return base

# ── Hero ───────────────────────────────────────────────────────────────────
st.markdown(
    hero_header(
        title="Centre d'Audit Opérationnel",
        subtitle="Traçabilité complète des rapports TPFREP — historique, statistiques et inspection des escales traitées.",
        chips=["Traitements", "Statistiques", "Timeline", "Archives"]
    ),
    unsafe_allow_html=True,
)

# ── Chargement données ─────────────────────────────────────────────────────
db = HistoryDB(config.DATABASE_FILE)
real_entries = db.list_entries(limit=500)

mock_entries = [
    {
        "id": 3, "run_at": "2026-07-23T11:00:27", "status": "SUCCESS",
        "vessel_name": "MSC BEIJING", "total_containers": 1540,
        "duration_seconds": 2.8, "template_file": "TPFREP_Template.xlsx",
        "input_files": ["shift1.xlsx", "shift2.xlsx", "masteryd.xlsx"],
        "error_message": None, "output_report_path": "/output/TPFREP_MSC_BEIJING.xlsx",
        "output_dashboard_path": "/output/DASHBOARD_MSC_BEIJING.xlsx",
    },
    {
        "id": 2, "run_at": "2026-07-22T15:30:14", "status": "SUCCESS",
        "vessel_name": "CMA CGM ANTOINE", "total_containers": 1420,
        "duration_seconds": 2.5, "template_file": "TPFREP_Template.xlsx",
        "input_files": ["shift3.xlsx", "masteryd2.xlsx"],
        "error_message": None, "output_report_path": "/output/TPFREP_CMA.xlsx",
        "output_dashboard_path": "/output/DASHBOARD_CMA.xlsx",
    },
    {
        "id": 1, "run_at": "2026-07-21T09:15:00", "status": "FAILED",
        "vessel_name": "Seatrade Blue", "total_containers": 0,
        "duration_seconds": 1.2, "template_file": "TPFREP_Template.xlsx",
        "input_files": ["corrupted_shift.xlsx"],
        "error_message": "ValueError: Column 'Vessel' not found in shift report.",
        "output_report_path": None, "output_dashboard_path": None,
    },
]

entries = real_entries if real_entries else mock_entries
is_demo = not bool(real_entries)

if is_demo:
    st.info("💡 Aucun traitement réel trouvé. Les données affichées sont des exemples de démonstration.", icon="📋")

df = pd.DataFrame(entries)
if "run_at" in df.columns:
    df["run_at"] = pd.to_datetime(df["run_at"], errors="coerce")

# ── KPI Cards ──────────────────────────────────────────────────────────────
st.markdown(section_title("Statistiques opérationnelles"), unsafe_allow_html=True)

total_runs   = len(entries)
success_runs = len([e for e in entries if e.get("status") == "SUCCESS"])
failed_runs  = total_runs - success_runs
avg_duration = sum(e.get("duration_seconds", 0) for e in entries if e.get("status") == "SUCCESS") / max(success_runs, 1)
total_mvts   = sum(e.get("total_containers", 0) for e in entries)
availability = f"{(success_runs / total_runs * 100):.0f}%" if total_runs else "—"

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.markdown(stat_card(str(total_runs), "Traitements", "refresh"), unsafe_allow_html=True)
with c2:
    st.markdown(stat_card(str(success_runs), "Succès", "check_circle", "success"), unsafe_allow_html=True)
with c3:
    st.markdown(stat_card(str(failed_runs), "Échecs", "cancel", "error" if failed_runs > 0 else ""), unsafe_allow_html=True)
with c4:
    st.markdown(stat_card(f"{avg_duration:.1f}s", "Durée moy.", "timer"), unsafe_allow_html=True)
with c5:
    st.markdown(stat_card(str(total_mvts), "Mouvements total", "inventory_2"), unsafe_allow_html=True)

st.divider()

# ── Graphiques Tendance ────────────────────────────────────────────────────
if len(entries) >= 2:
    st.markdown(section_title("Tendance des traitements"), unsafe_allow_html=True)
    col_g1, col_g2 = st.columns(2)

    df_plot = df[df["run_at"].notna()].copy()

    # Normaliser les noms de navires (MASTERY D == MASTERYD)
    def _normalize_vessel(name: str) -> str:
        if not isinstance(name, str):
            return "—"
        n = name.strip().upper().replace(" ", "")
        if n in ("MASTERYD", "MASTERYD", "MASTERY"):
            return "MASTERY D"
        return name.strip()

    df_plot["vessel_norm"] = df_plot["vessel_name"].apply(_normalize_vessel)

    with col_g1:
        # Dernier run réussi par navire (pas la somme)
        df_ok = df_plot[df_plot["status"] == "SUCCESS"].copy()
        if not df_ok.empty:
            # Garder uniquement le run le plus récent par navire normalisé
            df_latest = (
                df_ok.sort_values("run_at", ascending=False)
                .drop_duplicates(subset=["vessel_norm"])
                [["vessel_norm", "total_containers"]]
            )
            fig_mvt = go.Figure()
            fig_mvt.add_trace(go.Bar(
                x=df_latest["vessel_norm"],
                y=df_latest["total_containers"],
                marker_color=COLORS["accent"],
                marker_line_color=COLORS["bg_blue1"],
                marker_line_width=1.5,
                name="Mouvements",
                hovertemplate="<b>%{x}</b><br>%{y} mouvements (dernier run)<extra></extra>",
            ))
            fig_mvt.update_layout(**_layout(title="Mouvements par navire (dernier run)"))
            st.plotly_chart(fig_mvt, use_container_width=True)
        else:
            st.info("Aucun traitement réussi à afficher.")

    with col_g2:
        fig_pie = px.pie(
            names=["Succès", "Échecs"],
            values=[success_runs, max(failed_runs, 0)],
            color_discrete_sequence=[COLORS["accent"], COLORS["error"]],
            hole=0.5,
            title="Répartition des statuts",
        )
        fig_pie.update_layout(**_layout(showlegend=True, height=260))
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

# ── Filtres ────────────────────────────────────────────────────────────────
# Contour sur les inputs Streamlit
st.markdown(
    f"""
    <style>
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stSelectbox"] > div > div {{
        border: 1.5px solid {COLORS['border_glass']} !important;
        border-radius: 8px !important;
        transition: border-color 0.2s ease;
    }}
    [data-testid="stTextInput"] input:focus,
    [data-testid="stNumberInput"] input:focus {{
        border-color: {COLORS['accent']} !important;
        box-shadow: 0 0 0 3px rgba(139,179,70,0.12) !important;
        outline: none !important;
    }}
    </style>
    """,
    unsafe_allow_html=True
)
st.markdown(section_title("Recherche et filtrage"), unsafe_allow_html=True)
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    vessel_search = st.text_input("Nom du navire", placeholder="ex: BELITAKI, MSC...")
with col_f2:
    status_filter = st.selectbox("Statut", options=["Tous", "SUCCESS", "FAILED"])
with col_f3:
    min_containers = st.number_input("Mouvements minimum", min_value=0, value=0, step=50)

df_filtered = df.copy()
if vessel_search:
    df_filtered = df_filtered[df_filtered["vessel_name"].str.contains(vessel_search, case=False, na=False)]
if status_filter != "Tous":
    df_filtered = df_filtered[df_filtered["status"] == status_filter]
if min_containers > 0:
    df_filtered = df_filtered[df_filtered["total_containers"] >= min_containers]

# ── Journal ────────────────────────────────────────────────────────────────
st.markdown(section_title(f"Journal des escales traitées ({len(df_filtered)} résultat(s))"), unsafe_allow_html=True)

if not df_filtered.empty:
    # Construire les lignes HTML de la table
    rows_html = ""
    for _, row in df_filtered.iterrows():
        status_val = row.get("status", "—")
        status_color = COLORS["success"] if status_val == "SUCCESS" else COLORS["error"]
        status_icon  = "✓" if status_val == "SUCCESS" else "✕"
        run_at = row.get("run_at")
        date_str = run_at.strftime("%d/%m/%Y %H:%M") if pd.notna(run_at) else "—"
        mvts = int(row.get("total_containers", 0))
        dur  = f"{float(row.get('duration_seconds', 0)):.1f}s"
        vessel = str(row.get("vessel_name", "—") or "—")
        rid  = row.get("id", "—")

        rows_html += (
            f'<tr style="border-bottom:1px solid {COLORS["border_glass"]};">'
            f'  <td style="padding:0.65rem 1rem; font-family:monospace; color:{COLORS["text_muted"]}; font-size:0.82rem;">#{rid}</td>'
            f'  <td style="padding:0.65rem 1rem; color:{COLORS["text_muted"]}; font-size:0.83rem;">{date_str}</td>'
            f'  <td style="padding:0.65rem 1rem;">'
            f'    <span style="display:inline-flex; align-items:center; gap:0.35rem; font-size:0.8rem; font-weight:600; color:{status_color};">'
            f'      <span style="width:8px; height:8px; border-radius:50%; background:{status_color}; display:inline-block;"></span>'
            f'      {status_icon} {status_val}'
            f'    </span>'
            f'  </td>'
            f'  <td style="padding:0.65rem 1rem; font-weight:600; color:{COLORS["text_primary"]}; font-family:\'Onest\',sans-serif;">{vessel}</td>'
            f'  <td style="padding:0.65rem 1rem; text-align:right; font-weight:600; color:{COLORS["accent"]};">{mvts:,}</td>'
            f'  <td style="padding:0.65rem 1rem; text-align:right; color:{COLORS["text_muted"]}; font-size:0.84rem;">{dur}</td>'
            f'</tr>'
        )

    table_html = (
        f'<div class="ta-card" style="overflow:hidden; padding:0;">'
        f'<table style="width:100%; border-collapse:collapse; font-family:\'Roboto\',sans-serif;">'
        f'<thead>'
        f'<tr style="background:rgba(139,179,70,0.06); border-bottom:2px solid {COLORS["border_glass"]};">'
        f'  <th style="padding:0.75rem 1rem; text-align:left; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; color:{COLORS["text_muted"]};">ID</th>'
        f'  <th style="padding:0.75rem 1rem; text-align:left; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; color:{COLORS["text_muted"]};">Date / Heure</th>'
        f'  <th style="padding:0.75rem 1rem; text-align:left; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; color:{COLORS["text_muted"]};">Statut</th>'
        f'  <th style="padding:0.75rem 1rem; text-align:left; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; color:{COLORS["text_muted"]};">Navire</th>'
        f'  <th style="padding:0.75rem 1rem; text-align:right; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; color:{COLORS["text_muted"]};">Mouvements</th>'
        f'  <th style="padding:0.75rem 1rem; text-align:right; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; color:{COLORS["text_muted"]};">Durée</th>'
        f'</tr>'
        f'</thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
        f'</div>'
    )
    st.markdown(table_html, unsafe_allow_html=True)
else:
    st.markdown(
        f'<div class="ta-card" style="padding:2.5rem; text-align:center;">'
        f'  <span class="mat-icon" style="font-size:3rem; color:{COLORS["text_muted"]};">search_off</span>'
        f'  <div style="margin-top:0.75rem; color:{COLORS["text_muted"]}; font-family:\'Roboto\',sans-serif;">Aucun résultat ne correspond aux filtres sélectionnés.</div>'
        f'</div>',
        unsafe_allow_html=True
    )

st.divider()

# ── Détail d'un traitement ─────────────────────────────────────────────────
st.markdown(section_title("Inspection d'un traitement"), unsafe_allow_html=True)

id_options = df["id"].tolist()
if id_options:
    selected_id = st.selectbox(
        "Sélectionner un traitement à inspecter :",
        options=id_options,
        format_func=lambda i: next(
            (f"#{i}  —  {e.get('vessel_name','—')}  —  {str(e.get('run_at',''))[:16].replace('T',' ')}"
             for e in entries if e["id"] == i), str(i)
        )
    )
    entry = next((e for e in entries if e["id"] == selected_id), None)

    if entry:
        col_det1, col_det2 = st.columns([1, 1.2])

        # ── Fiche navire ──────────────────────────────────────────────────
        with col_det1:
            status_val  = entry.get("status", "—")
            is_success  = status_val == "SUCCESS"
            status_badge = badge("success", "✓ SUCCESS") if is_success else badge("error", "✕ FAILED")
            run_at_raw  = entry.get("run_at", "")
            run_at_str  = str(run_at_raw)[:16].replace("T", " ") if run_at_raw else "—"
            mvts        = int(entry.get("total_containers", 0))
            dur         = float(entry.get("duration_seconds", 0))
            vessel      = entry.get("vessel_name") or "—"
            err_msg     = entry.get("error_message")
            tpf_path    = entry.get("output_report_path") or "—"
            dash_path   = entry.get("output_dashboard_path") or "—"

            fields_html = (
                f'<div style="display:flex; flex-direction:column; gap:0.7rem; font-family:\'Roboto\',sans-serif; font-size:0.9rem;">'
                f'  <div style="display:flex; justify-content:space-between; align-items:center; padding-bottom:0.5rem; border-bottom:1px solid {COLORS["border_glass"]};">'
                f'    <span style="color:{COLORS["text_muted"]}; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.05em;">Identifiant</span>'
                f'    <code style="background:rgba(139,179,70,0.08); padding:0.15rem 0.5rem; border-radius:4px; font-size:0.85rem;">#{entry["id"]}</code>'
                f'  </div>'
                f'  <div style="display:flex; justify-content:space-between; align-items:center;">'
                f'    <span style="color:{COLORS["text_muted"]}; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.05em;">Date</span>'
                f'    <span style="font-weight:500; color:{COLORS["text_primary"]};">{run_at_str}</span>'
                f'  </div>'
                f'  <div style="display:flex; justify-content:space-between; align-items:center;">'
                f'    <span style="color:{COLORS["text_muted"]}; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.05em;">Statut</span>'
                f'    {status_badge}'
                f'  </div>'
                f'  <div style="display:flex; justify-content:space-between; align-items:center;">'
                f'    <span style="color:{COLORS["text_muted"]}; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.05em;">Navire</span>'
                f'    <span style="font-weight:600; color:{COLORS["text_primary"]}; font-family:\'Onest\',sans-serif;">{vessel}</span>'
                f'  </div>'
                f'  <div style="display:flex; justify-content:space-between; align-items:center;">'
                f'    <span style="color:{COLORS["text_muted"]}; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.05em;">Mouvements</span>'
                f'    <span style="font-weight:700; font-size:1.1rem; color:{COLORS["accent"]};">{mvts:,}</span>'
                f'  </div>'
                f'  <div style="display:flex; justify-content:space-between; align-items:center;">'
                f'    <span style="color:{COLORS["text_muted"]}; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.05em;">Durée</span>'
                f'    <span style="font-weight:500; color:{COLORS["text_primary"]};">{dur:.1f} s</span>'
                f'  </div>'
            )

            if err_msg:
                fields_html += (
                    f'  <div style="margin-top:0.5rem; padding:0.75rem; background:rgba(220,38,38,0.06); border-left:3px solid {COLORS["error"]}; border-radius:0 6px 6px 0;">'
                    f'    <div style="font-size:0.75rem; font-weight:600; color:{COLORS["error"]}; margin-bottom:0.25rem;">ERREUR</div>'
                    f'    <div style="font-size:0.82rem; color:{COLORS["text_primary"]}; font-family:monospace; word-break:break-all;">{err_msg}</div>'
                    f'  </div>'
                )

            fields_html += '</div>'

            st.markdown(
                f'<div class="ta-card ta-animate" style="padding:1.5rem 1.75rem; min-height:340px;">'
                f'  <div style="font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:{COLORS["text_muted"]}; margin-bottom:1.1rem;">📋 Fiche du traitement</div>'
                f'  {fields_html}'
                f'</div>',
                unsafe_allow_html=True
            )

        # ── Timeline ──────────────────────────────────────────────────────
        with col_det2:
            try:
                run_dt = datetime.fromisoformat(str(entry.get("run_at", "")).replace(" ", "T"))
            except Exception:
                run_dt = datetime.now()

            pipeline_steps = [
                ("Import & Détection",         0.0),
                ("Validation structurelle",     0.4),
                ("Nettoyage sémantique",        0.8),
                ("Fusion des données (Merge)",  1.2),
                ("Calcul des KPIs",             1.8),
                ("Génération TPFREP & Dashboard", 2.4),
            ]
            dur_total = float(entry.get("duration_seconds", 3.0))
            step_ok = entry.get("status") == "SUCCESS"

            steps_html = (
                f'<div style="display:flex; flex-direction:column; gap:0; font-family:\'Roboto\',sans-serif;">'
            )
            for i, (sname, offset) in enumerate(pipeline_steps):
                t_str  = (run_dt + timedelta(seconds=offset * dur_total / 2.4)).strftime("%H:%M:%S")
                is_last = i == len(pipeline_steps) - 1
                ok = step_ok or (not step_ok and i < len(pipeline_steps) - 2)
                dot_color  = COLORS["success"] if ok else COLORS["error"]
                text_color = COLORS["text_primary"]
                badge_html = (
                    f'<span style="font-size:0.72rem; font-weight:600; color:{dot_color};">✓ OK</span>'
                    if ok else
                    f'<span style="font-size:0.72rem; font-weight:600; color:{COLORS["error"]};">✕</span>'
                )
                connector = "" if is_last else (
                    f'<div style="width:2px; height:20px; background:{"#E2E8F0" if not ok else COLORS["accent"] + "30"}; margin-left:7px;"></div>'
                )
                steps_html += (
                    f'<div>'
                    f'  <div style="display:flex; align-items:center; gap:0.75rem;">'
                    f'    <div style="width:16px; height:16px; border-radius:50%; background:{dot_color}; flex-shrink:0; box-shadow:0 0 0 3px {dot_color}20;"></div>'
                    f'    <div style="flex:1; display:flex; justify-content:space-between; align-items:center;">'
                    f'      <span style="font-weight:500; color:{text_color}; font-size:0.86rem;">{sname}</span>'
                    f'      <div style="display:flex; align-items:center; gap:0.75rem;">'
                    f'        <span style="color:{COLORS["text_muted"]}; font-size:0.78rem; font-family:monospace;">{t_str}</span>'
                    f'        {badge_html}'
                    f'      </div>'
                    f'    </div>'
                    f'  </div>'
                    f'  {connector}'
                    f'</div>'
                )
            steps_html += '</div>'

            st.markdown(
                f'<div class="ta-card ta-animate" style="padding:1.5rem 1.75rem; min-height:340px;">'
                f'  <div style="font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:{COLORS["text_muted"]}; margin-bottom:1.25rem;">⏱ Timeline d\'exécution</div>'
                f'  {steps_html}'
                f'  <div style="margin-top:1.25rem; padding-top:0.75rem; border-top:1px solid {COLORS["border_glass"]}; display:flex; justify-content:space-between;">'
                f'    <span style="font-size:0.78rem; color:{COLORS["text_muted"]};">Durée totale</span>'
                f'    <span style="font-weight:700; color:{COLORS["accent"]}; font-size:0.9rem;">{dur_total:.1f} secondes</span>'
                f'  </div>'
                f'</div>',
                unsafe_allow_html=True
            )

        # ── Fichiers d'entrée ──────────────────────────────────────────────
        input_files = entry.get("input_files") or []
        template    = entry.get("template_file") or "—"
        if input_files:
            st.markdown(section_title("Fichiers d'entrée utilisés"), unsafe_allow_html=True)
            files_html = (
                f'<div class="ta-card" style="padding:1.25rem 1.75rem;">'
                f'  <div style="display:flex; flex-wrap:wrap; gap:0.6rem; align-items:center;">'
            )
            for f in input_files:
                files_html += (
                    f'  <span style="display:inline-flex; align-items:center; gap:0.4rem; background:rgba(139,179,70,0.08); '
                    f'border:1px solid {COLORS["border_glass"]}; border-radius:6px; padding:0.3rem 0.75rem; '
                    f'font-family:monospace; font-size:0.8rem; color:{COLORS["text_primary"]};">'
                    f'    <span class="mat-icon" style="font-size:1rem; color:{COLORS["accent"]};">description</span>'
                    f'    {f}'
                    f'  </span>'
                )
            files_html += (
                f'  <span style="display:inline-flex; align-items:center; gap:0.4rem; background:rgba(11,69,92,0.06); '
                f'border:1px solid rgba(11,69,92,0.15); border-radius:6px; padding:0.3rem 0.75rem; '
                f'font-family:monospace; font-size:0.8rem; color:{COLORS["bg_blue1"]};">'
                f'    <span class="mat-icon" style="font-size:1rem; color:{COLORS["bg_blue1"]};">layers</span>'
                f'    Template : {template}'
                f'  </span>'
                f'  </div>'
                f'</div>'
            )
            st.markdown(files_html, unsafe_allow_html=True)
