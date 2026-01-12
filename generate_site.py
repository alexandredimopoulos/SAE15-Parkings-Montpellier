import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
        df = pd.read_csv(FICHIER_CSV, delimiter=";")
        df.columns = df.columns.str.strip()
    except Exception as e:
        creer_page_erreur(f"Erreur CSV : {e}")
        return

    required = ['timestamp', 'type', 'places_libres', 'capacite_totale', 'parking']
    if not all(col in df.columns for col in required):
        creer_page_erreur("Données incomplètes.")
        return

    # --- 1. PRÉPARATION DES DONNÉES ---
    df['date'] = pd.to_datetime(df['timestamp'], unit='s') + pd.Timedelta(hours=1)
    
    # Nettoyage
    df['capacite_totale'] = pd.to_numeric(df['capacite_totale'], errors='coerce')
    df = df[df['capacite_totale'] > 0]
    df['percent_fill'] = (1 - (df['places_libres'] / df['capacite_totale'])) * 100
    
    # Formatage date pour JS
    df['date_str'] = df['date'].dt.strftime('%Y-%m-%d %H:%M:%S')

    # --- 2. DICTIONNAIRE D'HISTORIQUE ---
    start_date = df['date'].max() - timedelta(hours=48)
    df_history = df[df['date'] >= start_date].copy()
    
    history_dict = {}
    for parking_name in df_history['parking'].unique():
        data_p = df_history[df_history['parking'] == parking_name].sort_values('date')
        history_dict[parking_name] = {
            "dates": data_p['date_str'].tolist(),
            "values": data_p['percent_fill'].tolist(),
            "type": data_p['type'].iloc[0]
        }
    
    json_history = json.dumps(history_dict)

    # --- 3. DERNIER ÉTAT ---
    last_ts = df['timestamp'].max()
    df_last = df[df['timestamp'] == last_ts].copy()
    
    # CORRECTION HEURE (+1h demandée)
    date_maj = (datetime.fromtimestamp(last_ts) + timedelta(hours=1)).strftime('%H:%M')
    
    # MODIFICATION ETIQUETTE : Uniquement le pourcentage
    df_last['label_text'] = df_last.apply(lambda x: f"{x['percent_fill']:.0f}%", axis=1)

    # --- 4. CONFIGURATION GRAPHIQUES ---
    layout_config = {
        'plot_bgcolor': 'rgba(0,0,0,0)', 'paper_bgcolor': 'rgba(0,0,0,0)',
        'font': {'family': '-apple-system, Roboto, sans-serif'}, 'margin': dict(l=0, r=0, t=0, b=0)
    }
    COLOR_MAP = {'Voiture': '#007AFF', 'Velo': '#FF9500'}

    # --- A. CARTE ---
    df_map = df_last.dropna(subset=['lat', 'lon'])
    fig_map = px.scatter_mapbox(
        df_map, lat="lat", lon="lon", color="type",
        custom_data=['parking', 'percent_fill'],
        color_discrete_map=COLOR_MAP, zoom=12, height=400
    )
    fig_map.update_traces(
        marker=dict(size=15, opacity=0.9),
        hovertemplate="<b>%{customdata[0]}</b><br>Remplissage: %{customdata[1]:.0f}%<extra></extra>"
    )
    fig_map.update_layout(
        mapbox_style="carto-positron", 
        mapbox_center={"lat": 43.608, "lon": 3.877},
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(yanchor="top", y=0.95, xanchor="left", x=0.05),
        clickmode='event+select'
    )
    html_map = fig_map.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False}, div_id='map-div')

    # --- B. GRAPHIQUE ÉVOLUTION ---
    default_parking = df_last['parking'].iloc[0] if not df_last.empty else "Inconnu"
    default_data = df_history[df_history['parking'] == default_parking]
    
    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=default_data['date'], y=default_data['percent_fill'],
        mode='lines', name=default_parking,
        line=dict(color='#007AFF', width=3),
        fill='tozeroy', fillcolor='rgba(0, 122, 255, 0.1)'
    ))
    fig_line.update_layout(**layout_config)
    
    # TITRE EN GRAS ICI
    fig_line.update_layout(
        title=dict(text=f"Évolution : <b>{default_parking}</b>", x=0.05, y=0.95),
        hovermode="x unified",
        yaxis=dict(range=[0, 105], showgrid=True, gridcolor='#eee'),
        xaxis=dict(showgrid=False)
    )
    html_line = fig_line.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False}, div_id='line-div')

    # --- C. BARRES ---
    def create_bar_chart(data, color):
        if data.empty: return "<p>Pas de données</p>"
        data = data.sort_values('percent_fill', ascending=False)
        fig = px.bar(data, x='parking', y='percent_fill', text='label_text', color_discrete_sequence=[color])
        fig.update_traces(textposition='outside', textfont_weight='bold', marker_cornerradius=5, cliponaxis=False)
        fig.update_layout(**layout_config)
        # On réduit un peu la marge haute car le texte est plus court
        fig.update_yaxes(visible=False, range=[0, 125])
        fig.update_xaxes(title=None, tickangle=-45)
        return fig.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False})

    html_cars = create_bar_chart(df_last[df_last['type'] == 'Voiture'], COLOR_MAP['Voiture'])
    
    df_bikes = df_last[df_last['type'] == 'Velo'].copy()
    if not df_bikes.empty:
        df_bikes['parking'] = df_bikes['parking'].apply(lambda x: x[:15] + '..' if len(x) > 15 else x)
    html_bikes = create_bar_chart(df_bikes, COLOR_MAP['Velo'])

    # --- JAVASCRIPT ---
    js_script = f"""
    <script>
        var historicalData = {json_history};
        
        window.onload = function() {{
            var mapDiv = document.getElementById('map-div');
            var lineDiv = document.getElementById('line-div');
            
            mapDiv.on('plotly_click', function(data){{
                var point = data.points[0];
                var parkingName = point.customdata[0];
                
                if (historicalData[parkingName]) {{
                    var newData = historicalData[parkingName];
                    var newColor = (newData.type === 'Voiture') ? '#007AFF' : '#FF9500';
                    var fillColor = (newData.type === 'Voiture') ? 'rgba(0, 122, 255, 0.1)' : 'rgba(255, 149, 0, 0.1)';

                    var update = {{
                        x: [newData.dates],
                        y: [newData.values],
                        name: [parkingName],
                        'line.color': [newColor],
                        'fillcolor': [fillColor]
                    }};
                    
                    // MISE A JOUR DU TITRE EN GRAS
                    var layoutUpdate = {{
                        'title.text': 'Évolution : <b>' + parkingName + '</b>'
                    }};

                    Plotly.update(lineDiv, update, layoutUpdate);
                    lineDiv.scrollIntoView({{behavior: "smooth", block: "center"}});
                }}
            }});
        }};
    </script>
    """

    # --- HTML FINAL ---
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Montpellier Live</title>
        <style>
            :root {{ --bg-color: #F2F2F7; --card-bg: #FFFFFF; --text-primary: #1C1C1E; --text-secondary: #8E8E93; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: var(--bg-color); color: var(--text-primary); margin: 0; padding: 0; -webkit-font-smoothing: antialiased; }}
            header {{ position: sticky; top: 0; background: rgba(255,255,255,0.85); backdrop-filter: saturate(180%) blur(20px); -webkit-backdrop-filter: saturate(180%) blur(20px); border-bottom: 1px solid rgba(0,0,0,0.1); padding: 15px 20px; z-index: 999; display: flex; justify-content: space-between; align-items: center; }}
            h1 {{ font-size: 20px; font-weight: 700; margin: 0; }}
            .pill {{ background: #E5E5EA; color: var(--text-secondary); padding: 6px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; }}
            
            /* MODIFICATION LARGEUR SITE ICI */
            .container {{ max-width: 1100px; margin: 0 auto; padding: 20px; }}
            
            .card {{ background: var(--card-bg); border-radius: 22px; padding: 24px; margin-bottom: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.04); overflow: hidden; }}
            .card-header {{ display: flex; align-items: center; margin-bottom: 20px; }}
            .icon {{ font-size: 24px; margin-right: 12px; }}
            .card-title {{ font-size: 19px; font-weight: 700; margin: 0; }}
            .card-subtitle {{ font-size: 14px; color: var(--text-secondary); margin-top: 2px; }}
            footer {{ text-align: center; color: var(--text-secondary); font-size: 12px; padding: 40px; }}
            .instruction {{ text-align:center; color: #007AFF; font-size:14px; margin-bottom:10px; font-weight:500; }}
        </style>
    </head>
    <body>
        <header>
            <h1>Montpellier Live</h1>
            <div class="pill">Maj : {date_maj}</div>
        </header>

        <div class="container">
            
            <div class="card" style="padding:0;">
                <div style="padding: 20px 20px 10px 20px;">
                    <h2 class="card-title">Carte Interactive</h2>
                    <div class="card-subtitle">Localisation des stations</div>
                    <p class="instruction">👆 Cliquez sur un point pour voir son historique ci-dessous</p>
                </div>
                {html_map}
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="icon">📈</span>
                    <div><h2 class="card-title">Analyse Temporelle</h2><div class="card-subtitle">Historique sur 48h</div></div>
                </div>
                {html_line}
            </div>

            <div class="card">
                <div class="card-header"><span class="icon">🚗</span><div><h2 class="card-title">Parkings Voitures</h2><div class="card-subtitle">État actuel</div></div></div>
                {html_cars}
            </div>

            <div class="card">
                <div class="card-header"><span class="icon">🚲</span><div><h2 class="card-title">Parkings Vélos</h2><div class="card-subtitle">État actuel</div></div></div>
                {html_bikes}
            </div>
            
            <footer>SAE15 • Données OpenData Montpellier</footer>
        </div>
        
        {js_script}
    </body>
    </html>
    """

    with open(FICHIER_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    print("Site mis à jour avec modifications design !")

if __name__ == "__main__":
    generer_html()