import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import json
from datetime import datetime, timedelta

FICHIER_CSV = "data/suivi_global.csv"
FICHIER_HTML = "index.html"

def generer_html():
    if not os.path.exists(FICHIER_CSV): return
    try:
        # On charge les vraies données
        df = pd.read_csv(FICHIER_CSV, delimiter=";", on_bad_lines='skip')
        df.columns = df.columns.str.strip()
    except: return

    # Préparation
    df['date'] = pd.to_datetime(df['timestamp'], unit='s') + timedelta(hours=1) # UTC+1
    df = df[df['capacite_totale'] > 0]
    df['percent_fill'] = (1 - (df['places_libres'] / df['capacite_totale'])) * 100
    df['percent_fill'] = df['percent_fill'].clip(0, 100) # Sécurité bornes

    # Pas de "resample" complexe ici car on a déjà filtré à 1h dans le script python
    # On arrondit juste l'heure pour grouper proprement
    df['heure'] = df['date'].dt.round('H')
    
    # Agrégation (Moyenne si jamais il y a des doublons)
    df_history = df.groupby(['parking', 'type', 'heure'])['percent_fill'].mean().reset_index()
    df_history['date_str'] = df_history['heure'].dt.strftime('%Y-%m-%d %H:%M')

    # Intermodalité (Moyenne globale par type)
    df_inter = df_history.groupby(['heure', 'type'])['percent_fill'].mean().reset_index()
    df_car = df_inter[df_inter['type'] == 'Voiture'].set_index('heure')['percent_fill']
    df_bike = df_inter[df_inter['type'] == 'Velo'].set_index('heure')['percent_fill']
    df_cmp = pd.merge(df_car, df_bike, left_index=True, right_index=True, suffixes=('_c', '_b'))

    html_inter = "<p>Données en cours...</p>"
    if not df_cmp.empty:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        # shape='linear' pour relier les points réels sans lissage artificiel
        fig.add_trace(go.Scatter(x=df_cmp.index, y=df_cmp['percent_fill_c'], name="Voiture", line=dict(color='#007AFF', width=3, shape='linear')), secondary_y=False)
        fig.add_trace(go.Scatter(x=df_cmp.index, y=df_cmp['percent_fill_b'], name="Vélo", line=dict(color='#FF9500', width=3, shape='linear')), secondary_y=True)
        fig.update_layout(margin=dict(l=0,r=0,t=30,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", y=1.1))
        html_inter = fig.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False})

    # JSON pour les graphiques individuels
    history = {}
    for p in df_history['parking'].unique():
        d = df_history[df_history['parking'] == p].sort_values('heure')
        history[p] = { 
            "dates": d['date_str'].tolist(), 
            "values": [round(x,1) for x in d['percent_fill']], 
            "type": d['type'].iloc[0] 
        }
    json_data = json.dumps(history)

    # État actuel (Dernier point connu)
    last_ts = df['timestamp'].max()
    date_maj = (datetime.fromtimestamp(last_ts) + timedelta(hours=1)).strftime('%d/%m %H:%M')
    
    # On prend le dernier point de chaque parking
    df_last = df.sort_values('timestamp').groupby('parking').tail(1)
    df_last['lbl'] = df_last.apply(lambda x: f"{x['percent_fill']:.0f}%", axis=1)

    # Carte
    fig_map = px.scatter_mapbox(df_last.dropna(subset=['lat','lon']), lat="lat", lon="lon", color="type", custom_data=['parking', 'percent_fill'], zoom=12, height=450, color_discrete_map={'Voiture':'#007AFF', 'Velo':'#FF9500'})
    fig_map.update_layout(mapbox_style="carto-positron", mapbox_center={"lat": 43.608, "lon": 3.877}, margin=dict(l=0,r=0,t=0,b=0), legend=dict(y=0.95, x=0.05))
    html_map = fig_map.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False}, div_id='map-div')

    # Barres
    def make_bar(data, color, did):
        if data.empty: return ""
        fig = px.bar(data.sort_values('percent_fill', ascending=False), x='parking', y='percent_fill', text='lbl', color_discrete_sequence=[color])
        fig.update_layout(margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis=dict(visible=False, range=[0,110]), xaxis=dict(title=None))
        return fig.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False}, div_id=did)

    html_cars = make_bar(df_last[df_last['type'] == 'Voiture'], '#007AFF', 'cars-div')
    html_bikes = make_bar(df_last[df_last['type'] == 'Velo'], '#FF9500', 'bikes-div')

    html = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Montpellier Live</title><style>
    body{{font-family:-apple-system,sans-serif;background:#F2F2F7;margin:0;padding:20px;color:#1C1C1E}}
    .box{{background:white;border-radius:16px;padding:20px;margin-bottom:20px;box-shadow:0 2px 10px rgba(0,0,0,0.05)}}
    h1{{text-align:center}} .grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}} @media(max-width:700px){{.grid{{grid-template-columns:1fr}}}}
    </style></head><body>
    <h1>🅿️ Données Réelles <small>{date_maj}</small></h1>
    <div class="grid"><div class="box"><h3>Comparatif</h3>{html_inter}</div><div class="box"><h3>Carte</h3>{html_map}</div></div>
    <div class="box"><h3>Historique</h3><div id="line-div" style="height:300px;text-align:center;line-height:300px;color:#888">Cliquez sur un parking</div></div>
    <div class="grid"><div class="box"><h3>Voitures</h3>{html_cars}</div><div class="box"><h3>Vélos</h3>{html_bikes}</div></div>
    <script>
    var d = {json_data};
    function up(n){{
        if(!d[n]) return;
        var c = d[n].type=='Voiture'?'#007AFF':'#FF9500';
        Plotly.newPlot('line-div',[{{x:d[n].dates,y:d[n].values,type:'scatter',line:{{color:c,width:3}}}}],{{title:n,margin:{{l:30,r:10,t:40,b:30}}}},{{displayModeBar:false,responsive:true}});
    }}
    window.onload=function(){{
        document.getElementById('map-div').on('plotly_click', function(e){{ up(e.points[0].customdata[0]); }});
        document.getElementById('cars-div').on('plotly_click', function(e){{ up(e.points[0].x); }});
        document.getElementById('bikes-div').on('plotly_click', function(e){{ up(e.points[0].x); }});
    }};
    </script></body></html>"""
    
    with open(FICHIER_HTML, "w", encoding="utf-8") as f: f.write(html)
    print("Site généré avec les vraies données (1h).")

if __name__ == "__main__": generer_html()