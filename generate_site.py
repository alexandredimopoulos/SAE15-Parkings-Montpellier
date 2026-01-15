"""Génère index.html (dashboard) à partir de data/suivi_global.csv.

Objectif : un rendu proche du screenshot "Montpellier Live":
- Courbe comparatif Voiture vs Vélo (moyenne par heure)
- Bloc stabilité (plus stable / plus instable) basé sur l'écart-type sur les dernières 24h
- Carte des parkings/stations (positions depuis data/locations.json)
- Historique interactif (clic sur un point carte ou une barre)
- Barres classement (occupation actuelle)

Le script est robuste aux petites incohérences (doublons, valeurs capteur > total...).
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

CSV_PATH = "data/suivi_global.csv"
LOC_PATH = "data/locations.json"
OUT_HTML = "index.html"


def _force_div_id(plotly_html: str, wanted_id: str) -> str:
    """Forcer un id de DIV sur le premier conteneur Plotly.

    Selon la version de Plotly, `to_html(..., div_id=...)` n'existe pas.
    Ici, on remplace le 1er `id="..."` rencontré dans le HTML renvoyé.
    """
    return re.sub(r'<div id="[^"]+"', f'<div id="{wanted_id}"', plotly_html, count=1)


def norm_name(s: str) -> str:
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = re.sub(r"\s+", " ", s)
    return s


def load_locations() -> dict:
    if not os.path.exists(LOC_PATH):
        return {"Voiture": {}, "Velo": {}}
    with open(LOC_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_history() -> pd.DataFrame:
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(CSV_PATH)

    df = pd.read_csv(CSV_PATH, sep=";", on_bad_lines="skip")
    df.columns = [c.strip() for c in df.columns]

    # Support 2 formats:
    # A) Date, Heure, Type, Nom, Places_Libres, Places_Totales
    # B) timestamp, type, parking, places_libres, capacite_totale, lat, lon (ancien)
    cols = set(df.columns)

    if {"Date", "Heure", "Type", "Nom", "Places_Libres", "Places_Totales"}.issubset(cols):
        df = df.rename(
            columns={
                "Type": "type",
                "Nom": "name",
                "Places_Libres": "free",
                "Places_Totales": "total",
            }
        )
        # datetime locale (sans timezone) : YYYY-MM-DD + HH:MM
        df["dt"] = pd.to_datetime(df["Date"].astype(str) + " " + df["Heure"].astype(str), errors="coerce")
    elif {"timestamp", "type", "parking", "places_libres", "capacite_totale"}.issubset(cols):
        df = df.rename(
            columns={
                "parking": "name",
                "places_libres": "free",
                "capacite_totale": "total",
            }
        )
        df["dt"] = pd.to_datetime(df["timestamp"], unit="s", errors="coerce")
    else:
        raise ValueError(f"Colonnes CSV non reconnues: {df.columns.tolist()}")

    df["type"] = df["type"].astype(str).str.strip()
    df["name"] = df["name"].astype(str).str.strip()

    # numerique + nettoyage
    df["free"] = pd.to_numeric(df["free"], errors="coerce")
    df["total"] = pd.to_numeric(df["total"], errors="coerce")
    df = df.dropna(subset=["dt", "type", "name", "free", "total"])
    df = df[df["total"] > 0]

    # clamp capteurs
    df.loc[df["free"] > df["total"], "free"] = df.loc[df["free"] > df["total"], "total"]
    df.loc[df["free"] < 0, "free"] = 0

    df["percent_fill"] = (1 - (df["free"] / df["total"])) * 100.0
    df["percent_fill"] = df["percent_fill"].clip(0, 100)

    # arrondi à l'heure pour lisser proprement
    df["hour"] = df["dt"].dt.round("h")

    return df


def compute_stability(df: pd.DataFrame) -> tuple[str, str]:
    """Retourne (plus_stable, plus_instable) sur Voiture, sur les dernières 24h."""
    if df.empty:
        return ("—", "—")

    # dernière date
    last_dt = df["dt"].max()
    window_start = last_dt - timedelta(hours=24)

    d = df[(df["type"].str.lower() == "voiture") & (df["dt"] >= window_start)]
    if d.empty:
        return ("—", "—")

    # std par parking
    stats = d.groupby("name")["percent_fill"].agg(["std", "count"]).reset_index()
    stats = stats[stats["count"] >= 6]  # au moins ~6 points (sinon bruit)
    if stats.empty:
        return ("—", "—")

    stable = stats.sort_values(["std", "count"], ascending=[True, False]).iloc[0]["name"]
    unstable = stats.sort_values(["std", "count"], ascending=[False, False]).iloc[0]["name"]
    return (str(stable), str(unstable))


def build_site() -> None:
    df = load_history()

    # historique agrégé (si doublons)
    df_hist = df.groupby(["name", "type", "hour"], as_index=False)["percent_fill"].mean()
    df_hist["date_str"] = df_hist["hour"].dt.strftime("%Y-%m-%d %H:%M")

    # intermodalité : moyenne par type et heure
    df_inter = df_hist.groupby(["hour", "type"], as_index=False)["percent_fill"].mean()

    # pivot pour tracer 2 axes
    car = df_inter[df_inter["type"].str.lower() == "voiture"].set_index("hour")["percent_fill"]
    bike = df_inter[df_inter["type"].str.lower() == "velo"].set_index("hour")["percent_fill"]
    df_cmp = pd.merge(car, bike, left_index=True, right_index=True, how="outer", suffixes=("_c", "_b")).sort_index()

    html_inter = "<p style='color:#888'>Données insuffisantes…</p>"
    if not df_cmp.empty:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Scatter(
                x=df_cmp.index,
                y=df_cmp.get("percent_fill_c"),
                name="Voiture",
                line=dict(color="#007AFF", width=3, shape="linear"),
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=df_cmp.index,
                y=df_cmp.get("percent_fill_b"),
                name="Vélo",
                line=dict(color="#FF9500", width=3, shape="linear"),
            ),
            secondary_y=True,
        )
        fig.update_layout(
            margin=dict(l=0, r=0, t=30, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=1.1),
        )
        html_inter = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})

    # JSON historique (pour click)
    history: dict[str, dict] = {}
    for (name, t), sub in df_hist.groupby(["name", "type"]):
        s = sub.sort_values("hour")
        history[name] = {
            "dates": s["date_str"].tolist(),
            "values": [round(float(x), 1) for x in s["percent_fill"].tolist()],
            "type": t,
        }
    json_data = json.dumps(history, ensure_ascii=False)

    # snapshot actuel
    last_dt = df["dt"].max()
    date_maj = last_dt.strftime("%d/%m à %H:%M")

    df_last = df.sort_values("dt").groupby(["type", "name"], as_index=False).tail(1)
    df_last["lbl"] = df_last["percent_fill"].map(lambda x: f"{x:.0f}%")

    # stabilité
    stable, unstable = compute_stability(df)

    # positions
    loc = load_locations()
    df_last["name_norm"] = df_last["name"].map(norm_name)
    df_last["lat"] = None
    df_last["lon"] = None

    for idx, row in df_last.iterrows():
        t = "Voiture" if str(row["type"]).lower() == "voiture" else "Velo"
        entry = loc.get(t, {}).get(row["name_norm"])
        if entry:
            df_last.at[idx, "lat"] = entry.get("lat")
            df_last.at[idx, "lon"] = entry.get("lon")

    # carte
    df_map = df_last.dropna(subset=["lat", "lon"]).copy()

    html_map = "<div style='color:#888'>Pas de coordonnées (lance sync_locations.py)</div>"
    if not df_map.empty:
        fig_map = px.scatter_mapbox(
            df_map,
            lat="lat",
            lon="lon",
            color="type",
            custom_data=["name", "percent_fill"],
            zoom=12,
            height=450,
            color_discrete_map={"Voiture": "#007AFF", "Velo": "#FF9500", "Vélo": "#FF9500"},
        )
        fig_map.update_layout(
            mapbox_style="carto-positron",
            mapbox_center={"lat": 43.608, "lon": 3.877},
            margin=dict(l=0, r=0, t=0, b=0),
            legend=dict(y=0.95, x=0.05),
        )
        html_map = _force_div_id(
            fig_map.to_html(
                full_html=False,
                include_plotlyjs="cdn",
                config={"displayModeBar": False},
            ),
            "map-div",
        )

    def make_bar(sub: pd.DataFrame, color: str, did: str) -> str:
        if sub.empty:
            return ""
        fig = px.bar(
            sub.sort_values("percent_fill", ascending=False),
            x="name",
            y="percent_fill",
            text="lbl",
            color_discrete_sequence=[color],
            height=320,
        )
        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(visible=False, range=[0, 110]),
            xaxis=dict(title=None),
        )
        return _force_div_id(
            fig.to_html(
                full_html=False,
                include_plotlyjs="cdn",
                config={"displayModeBar": False},
            ),
            did,
        )

    cars = df_last[df_last["type"].str.lower() == "voiture"].copy()
    bikes = df_last[df_last["type"].str.lower().isin(["velo", "vélo"])].copy()

    html_cars = make_bar(cars, "#007AFF", "cars-div")
    html_bikes = make_bar(bikes, "#FF9500", "bikes-div")

    html = f"""<!DOCTYPE html>
<html lang=\"fr\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Montpellier Live</title>
  <style>
    body {{ font-family:-apple-system, system-ui, Segoe UI, Roboto, sans-serif; background:#F2F2F7; margin:0; padding:20px; color:#1C1C1E; }}
    .top {{ display:flex; justify-content:center; align-items:center; gap:10px; margin-bottom:12px; }}
    .pill {{ background:white; border-radius:999px; padding:6px 12px; box-shadow:0 2px 10px rgba(0,0,0,0.05); font-size:13px; }}
    .box {{ background:white; border-radius:16px; padding:20px; margin-bottom:20px; box-shadow:0 2px 10px rgba(0,0,0,0.05); }}
    .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
    @media(max-width:900px) {{ .grid {{ grid-template-columns:1fr; }} }}
    h1 {{ margin:6px 0 0 0; text-align:center; }}
    h3 {{ margin:0 0 10px 0; }}
    .stability {{ display:flex; justify-content:space-between; gap:16px; }}
    .stability .item {{ flex:1; text-align:center; padding:10px 12px; border-radius:12px; background:#F7F7FB; }}
    .ok {{ color:#1f9d55; font-weight:700; }}
    .bad {{ color:#d64545; font-weight:700; }}
  </style>
</head>
<body>
  <div class=\"top\">
    <div class=\"pill\">🅿️ Montpellier Live</div>
    <div class=\"pill\">MAJ: {date_maj}</div>
  </div>

  <div class=\"grid\">
    <div class=\"box\">
      <h3>🚲 vs 🚗</h3>
      {html_inter}
    </div>
    <div class=\"box\">
      <h3>📊 Stabilité (24h)</h3>
      <div class=\"stability\">
        <div class=\"item\">Le + stable<br><span class=\"ok\">{stable}</span></div>
        <div class=\"item\">Le + instable<br><span class=\"bad\">{unstable}</span></div>
      </div>
    </div>
  </div>

  <div class=\"box\">
    <h3>🗺️ Carte</h3>
    {html_map}
  </div>

  <div class=\"box\">
    <h3>📈 Historique</h3>
    <div id=\"line-div\" style=\"height:320px;text-align:center;line-height:320px;color:#888\">Cliquez sur un parking/station</div>
  </div>

  <div class=\"grid\">
    <div class=\"box\"><h3>🚗 Voitures</h3>{html_cars}</div>
    <div class=\"box\"><h3>🚲 Vélos</h3>{html_bikes}</div>
  </div>

  <script>
    var historyData = {json_data};

    function pickColor(t) {{
      t = (t || '').toLowerCase();
      if (t.includes('voiture')) return '#007AFF';
      return '#FF9500';
    }}

    function updateHistory(name) {{
      var d = historyData[name];
      if (!d) return;
      Plotly.newPlot(
        'line-div',
        [{{ x: d.dates, y: d.values, type: 'scatter', line: {{ color: pickColor(d.type), width: 3 }} }}],
        {{ title: name, margin: {{ l: 35, r: 10, t: 40, b: 30 }} }},
        {{ displayModeBar: false, responsive: true }}
      );
    }}

    window.onload = function() {{
      try {{
        var map = document.getElementById('map-div');
        if (map) map.on('plotly_click', function(e) {{ updateHistory(e.points[0].customdata[0]); }});
      }} catch (e) {{}}

      try {{
        var cars = document.getElementById('cars-div');
        if (cars) cars.on('plotly_click', function(e) {{ updateHistory(e.points[0].x); }});
      }} catch (e) {{}}

      try {{
        var bikes = document.getElementById('bikes-div');
        if (bikes) bikes.on('plotly_click', function(e) {{ updateHistory(e.points[0].x); }});
      }} catch (e) {{}}
    }};
  </script>
</body>
</html>"""

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK: site généré -> {OUT_HTML}")


if __name__ == "__main__":
    build_site()
