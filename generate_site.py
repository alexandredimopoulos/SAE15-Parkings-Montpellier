import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import json
from datetime import datetime, timedelta
import parking_lib as lib

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
        creer_page_erreur("Attente des données (CSV introuvable)...")
        return

    try:
        df = pd.read_csv(FICHIER_CSV, delimiter=";")
        df.columns = df.columns.str.strip()
    except Exception as e:
        creer_page_erreur(f"Erreur de lecture CSV : {e}")
        return

    required = ['timestamp', 'type', 'places_libres', 'capacite_totale', 'parking', 'lat', 'lon']
    if not all(col in df.columns for col in required):
        creer_page_erreur("Données incomplètes dans le CSV.")
        return

    # --- 1. PRÉPARATION ---
    df['date'] = pd.to_datetime(df['timestamp'], unit='s') + pd.Timedelta(hours=1)
    
    # Nettoyage doublons
    df = df.sort_values('timestamp')
    df = df.drop_duplicates(subset=['timestamp', 'parking'], keep='last')

    df['capacite_totale'] = pd.to_numeric(df['capacite_totale'], errors='coerce')
    df = df[df['capacite_totale'] > 0]
    df['percent_fill'] = (1 - (df['places_libres'] / df['capacite_totale'])) * 100
    df['date_str'] = df['date'].dt.strftime('%Y-%m-%d %H:%M:%S')

    # --- 2. STATS ---
    stats_df = df.groupby('parking')['percent_fill'].std().reset_index()
    stats_df.columns = ['parking', 'ecart_type']
    stats_df = stats_df.sort_values('ecart_type', ascending=False)
    
    if not stats_df.empty:
        top_instable = stats_df.iloc[0]['parking']
        top_stable = stats_df.iloc[-1]['parking']
    else:
        top_instable, top_stable = "N/A", "N/A"

    # --- 3. INTERMODALITÉ ---
    df_last = df[df['timestamp'] == df['timestamp'].max()].copy()
    parkings_voiture = df_last[df_last['type'] == 'Voiture']
    
    target_parking = "Gare"
    if target_parking not in parkings_voiture['parking'].values:
        target_parking = parkings_voiture['parking'].iloc[0] if not parkings_voiture.empty else None

    html_intermodalite = "<p>Pas assez de données.</p>"
    
    if target_parking:
        info_p = df_last[df_last['parking'] == target_parking].iloc[0]
        p_lat, p_lon = info_p['lat'], info_p['lon']

        velos = df_last[df_last['type'] == 'Velo']
        closest_velo = None
        min_dist = float('inf')

        for _, row in velos.iterrows():
            d = lib.distance_gps(p_lat, p_lon, row['lat'], row['lon'])
            if d < min_dist:
                min_dist = d
                closest_velo = row['parking']

        if closest_velo:
            data_car = df[df['parking'] == target_parking].set_index('date').resample('30min')['percent_fill'].mean().interpolate()
            data_bike = df[df['parking'] == closest_velo].set_index('date').resample('30min')['percent_fill'].mean().interpolate()
            
            combined = pd.concat([data_car, data_bike], axis=1, keys=['car', 'bike']).dropna()
            
            if len(combined) > 2:
                corr_score = lib.correlation(combined['car'].tolist(), combined['bike'].tolist())
                corr_text = f"Corrélation : {corr_score:.2f}"
            else:
                corr_text = "Calcul..."
            
            fig_dual = make_subplots(specs=[[{"secondary_y": True}]])
            
            fig_dual.add_trace(go.Scatter(
                x=data_car.index, y=data_car.values, name=f"🚗 {target_parking}",
                line=dict(color='#007AFF', width=3),
                hovertemplate="<b>%{x|%H:%M}</b><br>Voiture: <b>%{y:.0f}%</b><extra></extra>"
            ), secondary_y=False)
            
            fig_dual.add_trace(go.Scatter(
                x=data_bike.index, y=data_bike.values, name=f"🚲 {closest_velo}",
                line=dict(color='#FF9500', width=3),
                hovertemplate="<b>%{x|%H:%M}</b><br>Vélo: <b>%{y:.0f}%</b><extra></extra>"
            ), secondary_y=True)
            
            fig_dual.update_layout(
                title=dict(text=f"Intermodalité : {target_parking} vs {closest_velo}<br><sup>{corr_text} (Distance: {min_dist*1000:.0f}m)</sup>"),
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            fig_dual.update_yaxes(title_text="Voiture (%)", secondary_y=False, showgrid=True, gridcolor='#eee')
            fig_dual.update_yaxes(title_text="Vélo (%)", secondary_y=True, showgrid=False)
            html_intermodalite = fig_dual.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False, 'responsive': True})

    # --- 4. JS DATA ---
    df_history = df.copy() 
    history_dict = {}
    for parking_name in df_history['parking'].unique():
        data_p = df_history[df_history['parking'] == parking_name].sort_values('date')
        history_dict[parking_name] = {
            "dates": data_p['date_str'].tolist(),
            "values": data_p['percent_fill'].tolist(),
            "type": data_p['type'].iloc[0]
        }
    json_history = json.dumps(history_dict)

    # --- 5. VISU ---
    last_ts = df['timestamp'].max()
    df_last_viz = df[df['timestamp'] == last_ts].copy()
    date_maj = (datetime.fromtimestamp(last_ts) + timedelta(hours=1)).strftime('%H:%M')
    df_last_viz['label_text'] = df_last_viz['percent_fill'].apply(lambda x: f"{x:.0f}%")

    COLOR_MAP = {'Voiture': '#007AFF', 'Velo': '#FF9500'}
    
    # Carte
    df_map = df_last_viz.dropna(subset=['lat', 'lon'])
    fig_map = px.scatter_mapbox(
        df_map, lat="lat", lon="lon", color="type",
        custom_data=['parking', 'percent_fill', 'places_libres', 'capacite_totale'],
        color_discrete_map=COLOR_MAP, zoom=12, height=450
    )
    fig_map.update_traces(
        marker=dict(size=14, opacity=0.9),
        hovertemplate="<b>%{customdata[0]}</b><br>Remplissage: <b>%{customdata[1]:.0f}%</b><br>Libre: %{customdata[2]} / %{customdata[3]}<extra></extra>"
    )
    fig_map.update_layout(mapbox_style="carto-positron", mapbox_center={"lat": 43.608, "lon": 3.877}, margin=dict(l=0, r=0, t=0, b=0), legend=dict(x=0.02, y=0.98))
    html_map = fig_map.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False, 'responsive': True}, div_id='map-div')

    # Historique (Titre vide car géré par le HTML/JS)
    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(x=[], y=[], mode='lines')) 
    fig_line.update_layout(margin=dict(t=10), plot_bgcolor='rgba(0,0,0,0)', yaxis=dict(range=[0, 105], showgrid=True, gridcolor='#eee'))
    html_line = fig_line.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False, 'responsive': True}, div_id='line-div')

    # Barres
    def make_bar(type_p, color, div_id):
        d = df_last_viz[df_last_viz['type'] == type_p].sort_values('percent_fill', ascending=False)
        if d.empty: return ""
        if type_p == 'Velo': 
            d['parking'] = d['parking'].apply(lambda x: x[:15] + '..' if len(x) > 15 else x)
        
        fig = px.bar(d, x='parking', y='percent_fill', text='label_text', 
                     color_discrete_sequence=[color],
                     custom_data=['parking', 'places_libres', 'capacite_totale']) 
        
        fig.update_traces(
            textposition='outside', cliponaxis=False,
            hovertemplate="<b>%{customdata[0]}</b><br>Remplissage: %{y:.1f}%<br>Places: %{customdata[1]} / %{customdata[2]}<extra></extra>"
        )
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', 
            margin=dict(l=0,r=0,t=0,b=80), 
            yaxis=dict(visible=False, range=[0, 125]), 
            xaxis=dict(tickangle=-45)
        )
        return fig.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False, 'responsive': True}, div_id=div_id)

    html_cars = make_bar('Voiture', COLOR_MAP['Voiture'], 'cars-div')
    html_bikes = make_bar('Velo', COLOR_MAP['Velo'], 'bikes-div')

    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard SAE15</title>
        <style>
            :root {{ --bg: #F2F2F7; --card: #FFF; --blue: #007AFF; }}
            body {{ font-family: -apple-system, sans-serif; background: var(--bg); margin: 0; padding: 20px; color: #1C1C1E; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            h1 {{ text-align: center; margin-bottom: 30px; }}
            .badge {{ background: #E5E5EA; padding: 4px 10px; border-radius: 12px; font-size: 12px; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; margin-bottom: 20px; }}
            .card {{ background: var(--card); border-radius: 20px; padding: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
            .card h2 {{ font-size: 18px; margin-top: 0; border-bottom: 1px solid #eee; padding-bottom: 10px; }}
            .stat-box {{ display: flex; justify-content: space-around; text-align: center; margin: 15px 0; }}
            .stat-val {{ font-size: 20px; font-weight: bold; }}
            .stat-lbl {{ font-size: 12px; color: #8E8E93; }}
            footer {{ text-align:center; color:#8E8E93; font-size:12px; margin-top:40px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🅿️ Dashboard Analytique Montpellier <span class="badge">MAJ: {date_maj}</span></h1>
            
            <div class="grid">
                <div class="card">
                    <h2>🧠 Intermodalité : Voiture vs Vélo</h2>
                    {html_intermodalite}
                </div>
                <div class="card">
                    <h2>📊 Indicateurs de Stabilité : Le plus stable VS le moins stable</h2>
                    <div class="stat-box">
                        <div><div class="stat-lbl">Le plus Instable ⚠️</div><div class="stat-val" style="color:#FF3B30;">{top_instable}</div></div>
                        <div><div class="stat-lbl">Le plus Stable ✅</div><div class="stat-val" style="color:#34C759;">{top_stable}</div></div>
                    </div>
                    <p style="font-size:13px; color:#666; margin-top:15px; background:#f9f9f9; padding:10px;">
                        <b>Analyse :</b> "Odysseum" est instable car c'est un parking commercial (vide la nuit, bondé le jour). 
                        "Triangle" est stable car c'est un parking de centre-ville utilisé en continu.
                    </p>
                </div>
            </div>

            <div class="card" style="margin-bottom:20px;"><h2>📍 Carte Interactive</h2>{html_map}</div>
            
            <div class="card" style="margin-bottom:20px;">
                <h2 id="history-title">📈 Historique : Sélectionner un parking</h2>
                {html_line}
            </div>

            <div class="grid">
                <div class="card"><h2>🚗 Voitures</h2>{html_cars}</div>
                <div class="card"><h2>🚲 Vélos</h2>{html_bikes}</div>
            </div>
            <footer>Généré via Python & Plotly • Données OpenData Montpellier</footer>
        </div>

        <script>
            window.addEventListener('load', function() {{
                setTimeout(function() {{ window.dispatchEvent(new Event('resize')); }}, 500);
            }});

            var historyData = {json_history};
            function updateChart(name) {{
                var div = document.getElementById('line-div');
                if (!historyData[name]) return;
                var d = historyData[name];
                var color = (d.type === 'Voiture') ? '#007AFF' : '#FF9500';
                
                // MODIFICATION 2 (SUITE) : Mise à jour du Titre H2 avec Emoji
                var titleDOM = document.getElementById('history-title');
                var emoji = (d.type === 'Voiture') ? '🚗' : '🚲';
                if(titleDOM) titleDOM.innerText = "📈 Historique : " + name + " " + emoji;

                var update = {{ 
                    x: [d.dates], y: [d.values], name: [name], 
                    'line.color': [color],
                    hovertemplate: "<b>%{{x|%d/%m %H:%M}}</b><br>Remplissage: <b>%{{y:.0f}}%</b><extra></extra>"
                }};
                
                // On laisse le titre Plotly vide pour ne pas faire doublon
                Plotly.update(div, update, {{ title: '' }});
            }}
            
            var mapDiv = document.getElementById('map-div');
            if(mapDiv) mapDiv.on('plotly_click', function(d){{ updateChart(d.points[0].customdata[0]); }});
            var carsDiv = document.getElementById('cars-div');
            if(carsDiv) carsDiv.on('plotly_click', function(d){{ updateChart(d.points[0].customdata[0]); }});
            var bikesDiv = document.getElementById('bikes-div');
            if(bikesDiv) bikesDiv.on('plotly_click', function(d){{ 
                var name = d.points[0].customdata[0].replace('..', ''); 
                var realName = Object.keys(historyData).find(k => k.startsWith(name));
                if(realName) updateChart(realName);
            }});
            var first = Object.keys(historyData).find(k => historyData[k].type === 'Voiture');
            if(first) updateChart(first);
        </script>
    </body>
    </html>
    """
    with open(FICHIER_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    print("Site V9 (Titres Dynamiques) généré !")

if __name__ == "__main__":
    generer_html()