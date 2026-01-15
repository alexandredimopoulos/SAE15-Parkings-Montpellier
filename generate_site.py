import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
from datetime import datetime

FICHIER_CSV = "data/suivi_global.csv"

# Coordonnées GPS manuelles (car absentes de ton CSV) pour que la carte marche
GPS_FIX = {
    "Antigone": [43.6086, 3.8864], "Comedie": [43.6085, 3.8794], "Corum": [43.6139, 3.8824],
    "Europa": [43.6081, 3.8907], "Foch": [43.6108, 3.8744], "Gambetta": [43.6065, 3.8722],
    "Gare": [43.6044, 3.8807], "Triangle": [43.6091, 3.8828], "Pitot": [43.6132, 3.8703],
    "Circe": [43.6033, 3.9189], "Garcia Lorca": [43.5901, 3.8953], "Mosson": [43.6167, 3.8203],
    "Sabines": [43.5835, 3.8601], "Sablassou": [43.6335, 3.9238], "Occitanie": [43.6360, 3.8502],
    "Polygone": [43.6082, 3.8851], "Arc de Triomphe": [43.6114, 3.8735],
    "Odysseum": [43.6040, 3.9180], "Euromedecine": [43.6393, 3.8340]
}

def generer():
    if not os.path.exists(FICHIER_CSV):
        print("❌ Fichier CSV introuvable."); return

    try:
        # 1. Lecture du CSV avec le bon séparateur
        df = pd.read_csv(FICHIER_CSV, sep=";", on_bad_lines='skip')
    except Exception as e:
        print(f"❌ Erreur lecture CSV : {e}"); return

    # Nettoyage des noms de colonnes (au cas où il y a des espaces)
    df.columns = df.columns.str.strip()
    
    # 2. Création de la colonne Date complète (Fusion Date + Heure)
    try:
        df['datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Heure'], format='%Y-%m-%d %H:%M')
    except:
        # Fallback si format différent
        df['datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Heure'], errors='coerce')

    df = df.dropna(subset=['datetime']) # On vire les lignes illisibles
    df = df.sort_values('datetime')

    # Calcul remplissage
    df['Places_Totales'] = pd.to_numeric(df['Places_Totales'], errors='coerce')
    df['Places_Libres'] = pd.to_numeric(df['Places_Libres'], errors='coerce')
    df = df[df['Places_Totales'] > 0]
    df['percent'] = (1 - (df['Places_Libres'] / df['Places_Totales'])) * 100
    df['percent'] = df['percent'].clip(0, 100)

    # 3. Optimisation pour le graph (1 point par heure max pour alléger)
    df['heure_fixe'] = df['datetime'].dt.floor('h')
    df_graph = df.groupby(['Nom', 'Type', 'heure_fixe'])['percent'].mean().reset_index()
    df_graph['date_str'] = df_graph['heure_fixe'].dt.strftime('%Y-%m-%d %H:%M')

    # 4. JSON pour les graphes JS
    history_data = {}
    for parking in df_graph['Nom'].unique():
        data_p = df_graph[df_graph['Nom'] == parking]
        history_data[parking] = {
            "dates": data_p['date_str'].tolist(),
            "values": [round(x, 1) for x in data_p['percent']],
            "type": data_p['Type'].iloc[0]
        }
    json_str = json.dumps(history_data)

    # 5. État Actuel (Dernière ligne du fichier)
    last_df = df.groupby('Nom').tail(1).copy()
    
    # Ajout des GPS manuellement puisque ton CSV ne les a pas
    def get_lat(nom): return GPS_FIX.get(nom, [None, None])[0]
    def get_lon(nom): return GPS_FIX.get(nom, [None, None])[1]
    
    last_df['lat'] = last_df['Nom'].apply(get_lat)
    last_df['lon'] = last_df['Nom'].apply(get_lon)
    
    date_maj = df['datetime'].max().strftime('%d/%m à %H:%M')

    # 6. Création des Visuels
    # Carte (uniquement pour ceux dont on a trouvé le GPS)
    map_df = last_df.dropna(subset=['lat', 'lon'])
    if not map_df.empty:
        fig_map = px.scatter_mapbox(map_df, lat="lat", lon="lon", color="Type", 
                                    custom_data=['Nom', 'percent'], zoom=12, height=450,
                                    color_discrete_map={'Voiture':'#007AFF', 'Velo':'#FF9500'})
        fig_map.update_layout(mapbox_style="carto-positron", mapbox_center={"lat": 43.608, "lon": 3.877}, margin=dict(l=0,r=0,t=0,b=0), legend=dict(y=0.95, x=0.05))
        html_map = fig_map.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False})
    else:
        html_map = "<p style='text-align:center'>Coordonnées GPS manquantes dans le script.</p>"

    # Barres
    def make_bar(data, col):
        if data.empty: return "<p>Pas de données</p>"
        fig = px.bar(data.sort_values('percent', ascending=False), x='Nom', y='percent', text=data['percent'].apply(lambda x: f"{x:.0f}%"), color_discrete_sequence=[col])
        fig.update_layout(margin=dict(l=0,r=0,t=0,b=0), plot_bgcolor='rgba(0,0,0,0)', yaxis=dict(visible=False, range=[0,110]), xaxis=dict(title=None))
        return fig.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False})

    html_cars = make_bar(last_df[last_df['Type']=='Voiture'], '#007AFF')
    html_bikes = make_bar(last_df[last_df['Type']=='Velo'], '#FF9500')

    # HTML Final
    html = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Suivi Montpellier</title>
    <style>
        body{{font-family:-apple-system, sans-serif; background:#F2F2F7; margin:0; padding:20px; color:#1C1E21}}
        .box{{background:white; border-radius:18px; padding:20px; margin-bottom:20px; box-shadow:0 4px 12px rgba(0,0,0,0.05)}}
        h1{{text-align:center; font-weight:800}} .maj{{font-size:0.6em; background:#E5E5EA; padding:5px 10px; border-radius:12px; color:#555; vertical-align:middle}}
        .grid{{display:grid; grid-template-columns:1fr 1fr; gap:20px}} @media(max-width:768px){{.grid{{grid-template-columns:1fr}}}}
    </style></head><body>
        <h1>🅿️ Montpellier Live <span class="maj">{date_maj}</span></h1>
        
        <div class="box"><h3>Carte (Principaux Parkings)</h3>{html_map}</div>
        
        <div class="box">
            <h3>Historique (7 Jours)</h3>
            <div id="graph" style="height:300px; text-align:center; line-height:300px; color:#888">Cliquez sur un élément pour voir l'historique</div>
        </div>

        <div class="grid">
            <div class="box"><h3>Voitures</h3>{html_cars}</div>
            <div class="box"><h3>Vélos</h3>{html_bikes}</div>
        </div>

    <script>
        var data = {json_str};
        function draw(name) {{
            if(!data[name]) return;
            var c = data[name].type=='Voiture'?'#007AFF':'#FF9500';
            Plotly.newPlot('graph', [{{
                x: data[name].dates, y: data[name].values, type: 'scatter', mode: 'lines',
                line: {{color: c, width: 3, shape: 'spline'}}, fill: 'tozeroy'
            }}], {{
                title: name, margin: {{l:30,r:10,t:40,b:30}}, hovermode: 'x unified'
            }}, {{displayModeBar: false, responsive: true}});
        }}
        
        // Ecouteur pour la carte
        var mapDiv = document.querySelector('.js-plotly-plot');
        if(mapDiv) {{
            mapDiv.on('plotly_click', function(d) {{
                var name = d.points[0].customdata[0];
                draw(name);
                document.getElementById('graph').scrollIntoView({{behavior:'smooth'}});
            }});
        }}
        
        // Pour les barres, c'est un peu plus dur sans ID unique, mais on tente le coup
        // Sinon l'utilisateur peut cliquer sur la carte, c'est le principal.
    </script></body></html>"""

    with open("index.html", "w", encoding="utf-8") as f: f.write(html)
    print("✅ Site généré (compatible Date/Heure séparés).")

if __name__ == "__main__": generer()