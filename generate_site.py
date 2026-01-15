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
    html = f"""<!DOCTYPE html><html><head><title>Erreur</title></head>
    <body style="font-family:sans-serif;text-align:center;padding:50px;">
    <h1>⚠️ Oups !</h1><p>{message}</p></body></html>"""
    with open(FICHIER_HTML, "w", encoding="utf-8") as f:
        f.write(html)

def generer_html():
    if not os.path.exists(FICHIER_CSV):
        creer_page_erreur("Pas de fichier CSV trouvé.")
        return

    try:
        df = pd.read_csv(FICHIER_CSV, delimiter=";", on_bad_lines='skip')
        df.columns = df.columns.str.strip()
    except Exception as e:
        creer_page_erreur(f"Le fichier CSV est illisible : {e}")
        return

    required = ['timestamp', 'type', 'places_libres', 'capacite_totale', 'parking']
    if not all(col in df.columns for col in required):
        creer_page_erreur("Colonnes manquantes dans le CSV.")
        return

    # --- TRAITEMENT ---
    df['date'] = pd.to_datetime(df['timestamp'], unit='s') + pd.Timedelta(hours=1)
    df['capacite_totale'] = pd.to_numeric(df['capacite_totale'], errors='coerce')
    df = df[df['capacite_totale'] > 0]
    df['percent_fill'] = (1 - (df['places_libres'] / df['capacite_totale'])) * 100
    
    # --- 1. COMPRESSION HISTORIQUE ---
    df['heure_round'] = df['date'].dt.floor('30min')
    df_history = df.groupby(['parking', 'type', 'heure_round'])['percent_fill'].mean().reset_index()
    df_history['date_str'] = df_history['heure_round'].dt.strftime('%Y-%m-%d %H:%M')

    # --- 2. INTERMODALITÉ ---
    df['heure_pile'] = df['date'].dt.floor('h')
    df_inter = df.groupby(['heure_pile', 'type'])['percent_fill'].mean().reset_index()
    df_cars = df_inter[df_inter['type'] == 'Voiture'].set_index('heure_pile')['percent_fill']
    df_bikes = df_inter[df_inter['type'] == 'Velo'].set_index('heure_pile')['percent_fill']
    df_compare = pd.merge(df_cars, df_bikes, left_index=True, right_index=True, suffixes=('_car', '_bike'))
    
    if not df_compare.empty:
        fig_inter = make_subplots(specs=[[{"secondary_y": True}]])
        fig_inter.add_trace(go.Scatter(x=df_compare.index, y=df_compare['percent_fill_car'], name="Voiture", line=dict(color='#007AFF', width=3)), secondary_y=False)
        fig_inter.add_trace(go.Scatter(x=df_compare.index, y=df_compare['percent_fill_bike'], name="Vélo", line=dict(color='#FF9500', width=3)), secondary_y=True)
        fig_inter.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", y=1.1))
        fig_inter.update_yaxes(showgrid=True, gridcolor='#eee', secondary_y=False)
        fig_inter.update_yaxes(showgrid=False, secondary_y=True)
        html_inter = fig_inter.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False})
    else:
        html_inter = "<p>Données insuffisantes</p>"

    # --- 3. JSON LÉGER ---
    history_dict = {}
    for parking_name in df_history['parking'].unique():
        data_p = df_history[df_history['parking'] == parking_name].sort_values('heure_round')
        vals = [round(x, 1) for x in data_p['percent_fill'].tolist()]
        history_dict[parking_name] = {
            "dates": data_p['date_str'].tolist(),
            "values": vals,
            "type": data_p['type'].iloc[0]
        }
    json_history = json.dumps(history_dict)

    # --- 4. ETAT ACTUEL (CORRECTION CRUCIALE ICI) ---
    # Au lieu de filtrer par temps, on prend simplement la dernière ligne de CHAQUE parking
    df_last = df.sort_values('timestamp').groupby('parking').tail(1)
    
    # Date affichée : la plus récente trouvée
    last_ts_global = df['timestamp'].max()
    date_maj = (datetime.fromtimestamp(last_ts_global) + timedelta(hours=1)).strftime('%d/%m à %H:%M')
    
    df_last['label_text'] = df_last.apply(lambda x: f"{x['percent_fill']:.0f}%", axis=1)

    COLOR_MAP = {'Voiture': '#007AFF', 'Velo': '#FF9500'}

    # Carte
    df_map = df_last.dropna(subset=['lat', 'lon'])
    fig_map = px.scatter_mapbox(
        df_map, lat="lat", lon="lon", color="type",
        custom_data=['parking', 'percent_fill'],
        color_discrete_map=COLOR_MAP, zoom=12, height=450
    )
    fig_map.update_traces(marker=dict(size=12, opacity=0.9), hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]:.0f}%<extra></extra>")
    fig_map.update_layout(mapbox_style="carto-positron", mapbox_center={"lat": 43.608, "lon": 3.877}, margin=dict(l=0, r=0, t=0, b=0), legend=dict(yanchor="top", y=0.95, xanchor="left", x=0.05))
    html_map = fig_map.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False, 'responsive': True}, div_id='map-div')

    # Graphique ligne vide
    html_line = "<div id='line-div' style='text-align:center; padding:40px; color:#888'>Cliquez sur un parking pour voir l'historique</div>"
    
    # Barres
    def create_bar(data, color, div_id):
        if data.empty: return "<p style='text-align:center; color:#888'>Aucune donnée récente</p>"
        data = data.sort_values('percent_fill', ascending=False)
        fig = px.bar(data, x='parking', y='percent_fill', text='label_text', color_discrete_sequence=[color])
        fig.update_traces(textposition='outside', cliponaxis=False)
        fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=0, b=0), yaxis=dict(visible=False, range=[0, 120]), xaxis=dict(title=None, tickangle=-45))
        return fig.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False, 'responsive': True}, div_id=div_id)

    html_cars = create_bar(df_last[df_last['type'] == 'Voiture'], '#007AFF', 'cars-div')
    
    df_bikes = df_last[df_last['type'] == 'Velo'].copy()
    if not df_bikes.empty: 
        df_bikes['parking'] = df_bikes['parking'].apply(lambda x: x[:12] + '..' if len(x) > 12 else x)
    html_bikes = create_bar(df_bikes, '#FF9500', 'bikes-div')

    # Stabilité
    if not df_history.empty:
        stab = df_history.groupby('parking')['percent_fill'].std().sort_values()
        html_stable = f"""<div style="display:flex; justify-content:space-around; text-align:center;">
            <div><small>Le + Stable</small><br><strong style="color:#34C759; font-size:18px">{stab.index[0]}</strong></div>
            <div><small>Le + Instable</small><br><strong style="color:#FF3B30; font-size:18px">{stab.index[-1]}</strong></div>
        </div>"""
    else:
        html_stable = ""

    # HTML FINAL
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Suivi Parkings Montpellier (v7)</title>
        <style>
            :root {{ --bg: #F0F2F5; --card: #FFFFFF; --text: #1C1E21; }}
            body {{ font-family: -apple-system, system-ui, sans-serif; background: var(--bg); color: var(--text); margin:0; padding:10px; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            h1 {{ text-align: center; margin: 20px 0; font-size: 1.5rem; }}
            .card {{ background: var(--card); border-radius: 16px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }}
            h3 {{ margin-top: 0; font-size: 1.1rem; color: #65676B; }}
            .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
            @media(max-width: 768px){{ .grid {{ grid-template-columns: 1fr; }} }}
            .btn-fs {{ float:right; background:none; border:1px solid #ddd; padding:4px 8px; border-radius:6px; cursor:pointer; }}
            #map-wrap.fullscreen {{ position:fixed; top:0; left:0; width:100%; height:100%; z-index:999; background:white; padding:10px; }}
            #map-wrap.fullscreen #map-div {{ height: 90vh !important; }}
            footer {{ text-align: center; color: #888; font-size: 0.8rem; margin-top: 30px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🅿️ Montpellier Live <span style="background:#E4E6EB; padding:4px 8px; border-radius:12px; font-size:0.8rem">{date_maj}</span></h1>
            
            <div class="grid">
                <div class="card"><h3>🚲 vs 🚗</h3>{html_inter}</div>
                <div class="card"><h3>📊 Stabilité</h3>{html_stable}</div>
            </div>

            <div class="card">
                <div id="map-wrap">
                    <button class="btn-fs" onclick="toggleFS()">⛶</button>
                    <h3>🗺️ Carte</h3>
                    {html_map}
                </div>
            </div>

            <div class="card"><h3>📈 Historique</h3>{html_line}</div>

            <div class="grid">
                <div class="card"><h3>🚗 Voitures</h3>{html_cars}</div>
                <div class="card"><h3>🚲 Vélos</h3>{html_bikes}</div>
            </div>

            <footer>SAE15 - Version 7.0 (Correctif Temps Réel)</footer>
        </div>

        <script>
            var data = {json_history};
            
            function toggleFS() {{
                var el = document.getElementById('map-wrap');
                if(!document.fullscreenElement) {{ el.requestFullscreen(); el.classList.add('fullscreen'); }}
                else {{ document.exitFullscreen(); el.classList.remove('fullscreen'); }}
            }}

            function updateChart(name) {{
                var div = document.getElementById('line-div');
                if(!data[name]) return;
                var d = data[name];
                var color = (d.type === 'Voiture') ? '#007AFF' : '#FF9500';
                
                var trace = {{ x: d.dates, y: d.values, type: 'scatter', mode: 'lines', line: {{color: color, width: 3}}, fill: 'tozeroy' }};
                var layout = {{ title: 'Historique : ' + name, margin: {{l:30, r:10, t:40, b:30}}, height: 300 }};
                
                Plotly.newPlot(div, [trace], layout, {{displayModeBar: false, responsive: true}});
            }}

            window.onload = function() {{
                var map = document.getElementById('map-div');
                var cars = document.getElementById('cars-div');
                var bikes = document.getElementById('bikes-div');
                
                function handleClick(d) {{
                    var pt = d.points[0];
                    var name = pt.customdata ? pt.customdata[0] : pt.x;
                    if(!data[name]) {{
                        var search = name.replace('..', '');
                        for(var k in data) {{ if(k.startsWith(search)) {{ name = k; break; }} }}
                    }}
                    updateChart(name);
                    document.getElementById('line-div').scrollIntoView({{behavior: 'smooth', block: 'center'}});
                }}

                if(map) map.on('plotly_click', handleClick);
                if(cars) cars.on('plotly_click', handleClick);
                if(bikes) bikes.on('plotly_click', handleClick);
            }};
        </script>
    </body>
    </html>
    """

    with open(FICHIER_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    print("Site v7 généré (Correctif Last Value) !")

if __name__ == "__main__":
    generer_html()