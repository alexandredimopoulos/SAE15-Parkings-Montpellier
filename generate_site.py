import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import json
from datetime import datetime, timedelta

FICHIER_CSV = "data/suivi_global.csv"
FICHIER_HTML = "index.html"

def creer_page_erreur(message):
    html = f"""<!DOCTYPE html><html><head><title>Maintenance</title></head>
    <body style="font-family:sans-serif;text-align:center;padding:50px;">
    <h1>⚠️ Maintenance</h1><p>{message}</p></body></html>"""
    with open(FICHIER_HTML, "w", encoding="utf-8") as f:
        f.write(html)

def generer_html():
    if not os.path.exists(FICHIER_CSV):
        creer_page_erreur("Attente des données...")
        return

    try:
        # On lit le CSV (même s'il est gros, Python le gère bien)
        df = pd.read_csv(FICHIER_CSV, delimiter=";", on_bad_lines='skip')
        df.columns = df.columns.str.strip()
    except Exception as e:
        creer_page_erreur(f"Erreur CSV : {e}")
        return

    required = ['timestamp', 'type', 'places_libres', 'capacite_totale', 'parking']
    if not all(col in df.columns for col in required):
        creer_page_erreur("Données incomplètes.")
        return

    # --- 1. PRÉPARATION & NETTOYAGE ---
    df['date'] = pd.to_datetime(df['timestamp'], unit='s') + pd.Timedelta(hours=1)
    df['capacite_totale'] = pd.to_numeric(df['capacite_totale'], errors='coerce')
    df = df[df['capacite_totale'] > 0]
    df['percent_fill'] = (1 - (df['places_libres'] / df['capacite_totale'])) * 100
    
    # --- OPTIMISATION MAJEURE : RÉDUCTION DES DONNÉES ---
    # On crée une colonne "Heure" pour regrouper
    df['heure_round'] = df['date'].dt.floor('30T') # On garde 1 point toutes les 30 min
    
    # On fait la moyenne par parking et par tranche de 30 min
    # Cela réduit drastiquement le nombre de lignes pour le graphique
    df_history = df.groupby(['parking', 'type', 'heure_round'])['percent_fill'].mean().reset_index()
    df_history['date_str'] = df_history['heure_round'].dt.strftime('%Y-%m-%d %H:%M')

    # --- 2. LOGIQUE INTERMODALITÉ ---
    # Pour le graphique comparatif global, on moyenne encore plus large (1h)
    df['heure_pile'] = df['date'].dt.floor('H')
    df_inter = df.groupby(['heure_pile', 'type'])['percent_fill'].mean().reset_index()
    
    df_cars_agg = df_inter[df_inter['type'] == 'Voiture'].set_index('heure_pile')['percent_fill']
    df_bikes_agg = df_inter[df_inter['type'] == 'Velo'].set_index('heure_pile')['percent_fill']
    df_compare = pd.merge(df_cars_agg, df_bikes_agg, left_index=True, right_index=True, suffixes=('_car', '_bike'))
    
    # Graphique Intermodalité
    if not df_compare.empty and len(df_compare) > 2:
        fig_inter = make_subplots(specs=[[{"secondary_y": True}]])
        fig_inter.add_trace(go.Scatter(x=df_compare.index, y=df_compare['percent_fill_car'], name="Voiture", line=dict(color='#007AFF', width=3)), secondary_y=False)
        fig_inter.add_trace(go.Scatter(x=df_compare.index, y=df_compare['percent_fill_bike'], name="Vélo", line=dict(color='#FF9500', width=3)), secondary_y=True)
        fig_inter.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.1))
        fig_inter.update_yaxes(showgrid=True, gridcolor='#eee', secondary_y=False)
        fig_inter.update_yaxes(showgrid=False, secondary_y=True)
        html_inter = fig_inter.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False})
    else:
        html_inter = "<p style='text-align:center; color:#888'>Données en cours de synchronisation...</p>"

    # --- 3. INDICATEURS DE STABILITÉ ---
    # On calcule l'écart-type sur les données réduites (plus rapide)
    stability = df_history.groupby('parking')['percent_fill'].std().sort_values()
    if not stability.empty:
        html_stable = f"""
        <div style="display:flex; justify-content:space-around; text-align:center; margin-top:10px;">
            <div><div style="font-size:12px; color:#8E8E93;">Le plus Stable ✅</div><div style="font-size:18px; font-weight:bold; color:#34C759;">{stability.index[0]}</div></div>
            <div><div style="font-size:12px; color:#8E8E93;">Le plus Instable ⚠️</div><div style="font-size:18px; font-weight:bold; color:#FF3B30;">{stability.index[-1]}</div></div>
        </div>"""
    else:
        html_stable = "<p>Calcul...</p>"

    # --- 4. EXPORT JSON LÉGER POUR LE JS ---
    history_dict = {}
    # On utilise df_history (la version légère) au lieu de df
    for parking_name in df_history['parking'].unique():
        data_p = df_history[df_history['parking'] == parking_name].sort_values('heure_round')
        # On arrondit les valeurs à 1 décimale pour gagner encore de la place
        values_rounded = [round(v, 1) for v in data_p['percent_fill'].tolist()]
        history_dict[parking_name] = {
            "dates": data_p['date_str'].tolist(),
            "values": values_rounded,
            "type": data_p['type'].iloc[0]
        }
    
    # C'est ici que ça change tout : le JSON sera petit !
    json_history = json.dumps(history_dict)

    # --- 5. ÉTAT ACTUEL (Barres & Carte) ---
    last_ts = df['timestamp'].max()
    df_last = df[df['timestamp'] == last_ts].copy()
    date_maj = (datetime.fromtimestamp(last_ts) + timedelta(hours=1)).strftime('%H:%M')
    df_last['label_text'] = df_last.apply(lambda x: f"{x['percent_fill']:.0f}%", axis=1)

    COLOR_MAP = {'Voiture': '#007AFF', 'Velo': '#FF9500'}

    # Carte
    df_map = df_last.dropna(subset=['lat', 'lon'])
    fig_map = px.scatter_mapbox(
        df_map, lat="lat", lon="lon", color="type",
        custom_data=['parking', 'percent_fill'],
        color_discrete_map=COLOR_MAP, zoom=12, height=450
    )
    fig_map.update_traces(marker=dict(size=15, opacity=0.9), hovertemplate="<b>%{customdata[0]}</b><br>Remplissage: %{customdata[1]:.0f}%<extra></extra>")
    fig_map.update_layout(mapbox_style="carto-positron", mapbox_center={"lat": 43.608, "lon": 3.877}, margin=dict(l=0, r=0, t=0, b=0), legend=dict(yanchor="top", y=0.95, xanchor="left", x=0.05))
    html_map = fig_map.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False, 'responsive': True}, div_id='map-div')

    # Graphique ligne vide par défaut (sera rempli par le JS)
    default_text = "<div style='text-align:center; padding:50px; color:#888;'>Cliquez sur un parking ou une station pour voir l'historique</div>"
    html_line = f"<div id='line-div'>{default_text}</div>"

    # Si on a des données, on pré-affiche le premier graph
    if not df_history.empty:
        default_parking = df_history['parking'].iloc[0]
        data_def = df_history[df_history['parking'] == default_parking]
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(x=data_def['heure_round'], y=data_def['percent_fill'], mode='lines', name=default_parking, line=dict(color='#007AFF', width=3), fill='tozeroy', fillcolor='rgba(0, 122, 255, 0.1)'))
        fig_line.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=30, b=0), title=dict(text=f"Évolution : <b>{default_parking}</b>"), yaxis=dict(range=[0, 105], showgrid=True, gridcolor='#eee'))
        html_line = fig_line.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False, 'responsive': True}, div_id='line-div')

    # Barres
    def create_bar_chart(data, color, div_id):
        if data.empty: return "<p>Pas de données</p>"
        data = data.sort_values('percent_fill', ascending=False)
        fig = px.bar(data, x='parking', y='percent_fill', text='label_text', color_discrete_sequence=[color], custom_data=['places_libres', 'capacite_totale'])
        fig.update_traces(textposition='outside', textfont_weight='bold', marker_cornerradius=5, cliponaxis=False, hovertemplate="<b>%{x}</b><br>%{customdata[0]} places dispo<br>%{y:.0f}% rempli<extra></extra>")
        fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=0, b=0), yaxis=dict(visible=False, range=[0, 125]), xaxis=dict(title=None, tickangle=-45))
        return fig.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False, 'responsive': True}, div_id=div_id)

    html_cars = create_bar_chart(df_last[df_last['type'] == 'Voiture'], COLOR_MAP['Voiture'], 'cars-div')
    df_bikes = df_last[df_last['type'] == 'Velo'].copy()
    if not df_bikes.empty: df_bikes['parking'] = df_bikes['parking'].apply(lambda x: x[:15] + '..' if len(x) > 15 else x)
    html_bikes = create_bar_chart(df_bikes, COLOR_MAP['Velo'], 'bikes-div')

    # --- HTML FINAL ---
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Suivi Parkings Montpellier</title>
        <style>
            :root {{ --bg-color: #F2F2F7; --card-bg: #FFFFFF; --text-primary: #1C1C1E; --text-secondary: #8E8E93; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: var(--bg-color); color: var(--text-primary); margin: 0; padding: 0; -webkit-font-smoothing: antialiased; }}
            header {{ position: sticky; top: 0; background: rgba(255,255,255,0.85); backdrop-filter: saturate(180%) blur(20px); border-bottom: 1px solid rgba(0,0,0,0.1); padding: 15px 20px; z-index: 999; display: flex; justify-content: center; align-items: center; position: relative; }}
            h1 {{ font-size: 20px; font-weight: 700; margin: 0; text-align: center; }}
            .pill {{ background: #E5E5EA; color: var(--text-secondary); padding: 6px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; position: absolute; right: 20px; }}
            @media (max-width: 600px) {{ header {{ justify-content: space-between; }} .pill {{ position: static; }} h1 {{ font-size: 16px; }} }}
            .container {{ max-width: 95%; margin: 0 auto; padding: 20px; }}
            .card {{ background: var(--card-bg); border-radius: 22px; padding: 24px; margin-bottom: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.04); overflow: hidden; }}
            .card-header {{ display: flex; align-items: center; margin-bottom: 20px; justify-content: space-between; }}
            .header-left {{ display: flex; align-items: center; }}
            .icon {{ font-size: 24px; margin-right: 12px; }}
            .card-title {{ font-size: 19px; font-weight: 700; margin: 0; }}
            .card-subtitle {{ font-size: 14px; color: var(--text-secondary); margin-top: 2px; }}
            footer {{ text-align: center; color: var(--text-secondary); font-size: 12px; padding: 40px; }}
            .instruction {{ text-align:center; color: #007AFF; font-size:14px; margin-bottom:10px; font-weight:500; }}
            .fs-btn {{ background: none; border: 1px solid #E5E5EA; border-radius: 8px; padding: 5px 10px; cursor: pointer; color: #007AFF; font-weight: 600; font-size: 13px; transition: background 0.2s; }}
            .fs-btn:hover {{ background: #f0f0f5; }}
            #map-container-wrapper.is-fullscreen {{ background: white; padding: 20px; display: flex; flex-direction: column; justify-content: center; position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 9999; }}
            #map-container-wrapper.is-fullscreen #map-div {{ height: 90vh !important; }}
            .stats-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px; }}
            @media (max-width: 768px) {{ .stats-grid {{ grid-template-columns: 1fr; }} }}
        </style>
    </head>
    <body>
        <header><h1>🅿️ Suivi des Parkings de Montpellier en direct 🚲</h1><div class="pill">Maj : {date_maj}</div></header>
        <div class="container">
            <div class="stats-grid">
                <div class="card"><div class="card-header"><div class="header-left"><span class="icon">🧠</span><div><h2 class="card-title">Intermodalité</h2><div class="card-subtitle">Voiture vs Vélo (7 jours)</div></div></div></div>{html_inter}</div>
                <div class="card"><div class="card-header"><div class="header-left"><span class="icon">📊</span><div><h2 class="card-title">Stabilité</h2><div class="card-subtitle">Top & Flop</div></div></div></div>{html_stable}</div>
            </div>
            <div class="card" style="padding:0;"><div id="map-container-wrapper"><div style="padding: 20px 20px 10px 20px; display:flex; justify-content:space-between; align-items:center;"><div><h2 class="card-title">Carte</h2><div class="card-subtitle">Localisation</div></div><button class="fs-btn" onclick="toggleFullScreen()">⛶ Plein écran</button></div><p class="instruction">👆 Cliquez sur un point pour voir son historique</p>{html_map}</div></div>
            <div class="card"><div class="card-header"><div class="header-left"><span class="icon">📈</span><div><h2 class="card-title">Analyse Temporelle</h2><div class="card-subtitle">Historique détaillé</div></div></div></div>{html_line}</div>
            <div class="stats-grid">
                <div class="card"><div class="card-header"><div class="header-left"><span class="icon">🚗</span><div><h2 class="card-title">Voitures</h2><div class="card-subtitle">État actuel</div></div></div></div>{html_cars}</div>
                <div class="card"><div class="card-header"><div class="header-left"><span class="icon">🚲</span><div><h2 class="card-title">Vélos</h2><div class="card-subtitle">État actuel</div></div></div></div>{html_bikes}</div>
            </div>
            <footer>SAE15 • Données OpenData Montpellier</footer>
        </div>
        <script>
            var historicalData = {json_history};
            function toggleFullScreen() {{ var elem = document.getElementById('map-container-wrapper'); if (!document.fullscreenElement) {{ elem.requestFullscreen().catch(err => {{ alert(`Erreur : ${{err.message}}`); }}); elem.classList.add("is-fullscreen"); }} else {{ document.exitFullscreen(); elem.classList.remove("is-fullscreen"); }} }}
            function updateLineChart(parkingName) {{
                var lineDiv = document.getElementById('line-div');
                if (historicalData[parkingName]) {{
                    var newData = historicalData[parkingName];
                    var newColor = (newData.type === 'Voiture') ? '#007AFF' : '#FF9500';
                    var update = {{ x: [newData.dates], y: [newData.values], name: [parkingName], 'line.color': [newColor] }};
                    var layoutUpdate = {{ 'title.text': 'Évolution : <b>' + parkingName + '</b>' }};
                    Plotly.update(lineDiv, update, layoutUpdate);
                    lineDiv.scrollIntoView({{behavior: "smooth", block: "center"}});
                }}
            }}
            window.onload = function() {{
                var mapDiv = document.getElementById('map-div'); var carsDiv = document.getElementById('cars-div'); var bikesDiv = document.getElementById('bikes-div');
                if(mapDiv) {{ mapDiv.on('plotly_click', function(data){{ updateLineChart(data.points[0].customdata[0]); }}); }}
                if(carsDiv) {{ carsDiv.on('plotly_click', function(data){{ updateLineChart(data.points[0].x); }}); }}
                if(bikesDiv) {{ bikesDiv.on('plotly_click', function(data){{ var parkingName = data.points[0].x; if (!historicalData[parkingName]) {{ var cleanName = parkingName.replace('..', ''); for (var key in historicalData) {{ if (key.startsWith(cleanName)) {{ parkingName = key; break; }} }} }} updateLineChart(parkingName); }}); }}
            }};
        </script>
    </body></html>"""

    with open(FICHIER_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    print("Site généré avec optimisation JSON (Taille réduite) !")

if __name__ == "__main__":
    generer_html()