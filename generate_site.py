import pandas as pd
import plotly.express as px
import json
import os
from datetime import datetime

FICHIER_CSV = "data/suivi_global.csv"
FICHIER_HTML = "index.html"

# --- BASE GPS ÉTENDUE (Derniers ajouts) ---
GPS_FIX = {
    # Parkings Voitures
    "Antigone": [43.6086, 3.8864], "Comedie": [43.6085, 3.8794], "Corum": [43.6139, 3.8824],
    "Europa": [43.6081, 3.8907], "Foch": [43.6108, 3.8744], "Gambetta": [43.6065, 3.8722],
    "Gare": [43.6044, 3.8807], "Triangle": [43.6091, 3.8828], "Pitot": [43.6132, 3.8703],
    "Circe": [43.6033, 3.9189], "Garcia Lorca": [43.5901, 3.8953], "Mosson": [43.6167, 3.8203],
    "Sabines": [43.5835, 3.8601], "Sablassou": [43.6335, 3.9238], "Occitanie": [43.6360, 3.8502],
    "Polygone": [43.6082, 3.8851], "Arc de Triomphe": [43.6114, 3.8735], "Odysseum": [43.6040, 3.9180],
    "Euromedecine": [43.6393, 3.8340], "Saint Jean Le Sec": [43.5708, 3.8347],
    "Vicarello": [43.6330, 3.8400], "Gaumont EST": [43.6050, 3.9200], "Gaumont OUEST": [43.6050, 3.9150],
    "Charles de Gaulle": [43.6280, 3.8970], "Arceaux": [43.6120, 3.8680],
    
    # Vélos (Mots-clés pour recherche floue)
    "Gare Saint-Roch": [43.6055, 3.8812], "Comédie": [43.6085, 3.8794], "Hôtel de Ville": [43.5990, 3.8970],
    "Albert 1er": [43.6160, 3.8730], "Castellane": [43.6095, 3.8765], "Observatoire": [43.6060, 3.8760],
    "Rondelet": [43.6030, 3.8740], "Plan Cabanes": [43.6090, 3.8680], "Boutonnet": [43.6230, 3.8650],
    "Emile Combes": [43.6150, 3.8850], "Beaux-Arts": [43.6180, 3.8830], "Aubes": [43.6180, 3.8950],
    "Antigone": [43.6070, 3.8900], "Emile Zola": [43.6080, 3.8920], "Nombre d Or": [43.6085, 3.8880],
    "Louis Blanc": [43.6140, 3.8780], "Port Marianne": [43.6020, 3.9000], "Arceaux": [43.6120, 3.8680],
    "Cité Mion": [43.6030, 3.8850], "Nouveau Saint-Roch": [43.5990, 3.8780], "Renouvier": [43.6040, 3.8650],
    "Saint-Denis": [43.6045, 3.8735], "Richter": [43.6030, 3.8950], "Flahault": [43.6190, 3.8600],
    "Voltaire": [43.6040, 3.8880], "Prés d Arènes": [43.5950, 3.8850], "Malbosc": [43.6330, 3.8300],
    "Celleneuve": [43.6140, 3.8350], "Jules Ferry": [43.6055, 3.8812], "Occitanie": [43.6360, 3.8502],
    "Sabines": [43.5835, 3.8601], "Mosson": [43.6167, 3.8203], "Saint-Eloi": [43.6250, 3.8600],
    "Universités": [43.6300, 3.8600]
}

def page_maintenance(msg):
    html = f"""<!DOCTYPE html><html><body style="text-align:center;padding:50px;font-family:sans-serif;color:#555">
    <h1>⚠️ Maintenance en cours</h1><p>{msg}</p><p>Revenez dans quelques minutes.</p></body></html>"""
    with open(FICHIER_HTML, "w", encoding="utf-8") as f: f.write(html)

def generer():
    # Sécurité : si fichier inexistant ou trop petit (vide)
    if not os.path.exists(FICHIER_CSV) or os.path.getsize(FICHIER_CSV) < 50:
        page_maintenance("Initialisation des données...")
        return

    try:
        df = pd.read_csv(FICHIER_CSV, sep=";", on_bad_lines='skip')
    except: 
        page_maintenance("Fichier de données illisible.")
        return

    df.columns = df.columns.str.strip()
    
    # Parsing Date
    try:
        df['datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Heure'], format='%Y-%m-%d %H:%M')
    except:
        df['datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Heure'], errors='coerce')

    df = df.dropna(subset=['datetime']).sort_values('datetime')
    if df.empty:
        page_maintenance("Aucune donnée valide trouvée.")
        return

    # Calculs Remplissage
    df['Places_Totales'] = pd.to_numeric(df['Places_Totales'], errors='coerce')
    df['Places_Libres'] = pd.to_numeric(df['Places_Libres'], errors='coerce')
    df = df[df['Places_Totales'] > 0]
    df['percent'] = (1 - (df['Places_Libres'] / df['Places_Totales'])) * 100
    df['percent'] = df['percent'].clip(0, 100)

    # Préparation JSON (Dates ISO)
    df['heure_fixe'] = df['datetime'].dt.floor('h')
    df_graph = df.groupby(['Nom', 'Type', 'heure_fixe'])['percent'].mean().reset_index()
    df_graph['date_iso'] = df_graph['heure_fixe'].dt.strftime('%Y-%m-%dT%H:%M:%S')

    history_data = {}
    available_parkings = []
    for parking in df_graph['Nom'].unique():
        available_parkings.append(parking)
        data_p = df_graph[df_graph['Nom'] == parking]
        history_data[parking] = {
            "dates": data_p['date_iso'].tolist(),
            "values": [round(x, 1) for x in data_p['percent']],
            "type": data_p['Type'].iloc[0]
        }
    json_str = json.dumps(history_data)
    
    # Choix du parking de démarrage (Priorité aux connus)
    default_parking = None
    preferred = ["Comédie", "Gare Saint-Roch", "Foch", "Antigone", "Polygone"]
    for p in preferred:
        if p in available_parkings:
            default_parking = p
            break
    if not default_parking and available_parkings:
        default_parking = available_parkings[0]
        
    default_script = f"draw('{default_parking}');" if default_parking else "document.getElementById('graph').innerHTML = 'Aucune donnée historique';"

    # Dernières données pour Carte/Barres
    last_df = df.groupby('Nom').tail(1).copy()
    
    def find_gps(nom):
        if nom in GPS_FIX: return GPS_FIX[nom]
        for key, val in GPS_FIX.items(): 
            if key in nom: return val # Recherche floue
        return [None, None]

    last_df['coords'] = last_df['Nom'].apply(find_gps)
    last_df['lat'] = last_df['coords'].apply(lambda x: x[0])
    last_df['lon'] = last_df['coords'].apply(lambda x: x[1])
    
    date_maj = df['datetime'].max().strftime('%d/%m à %H:%M')

    # Carte
    map_df = last_df.dropna(subset=['lat', 'lon'])
    html_map = "<p style='text-align:center;padding:20px'>Carte indisponible</p>"
    if not map_df.empty:
        fig_map = px.scatter_mapbox(map_df, lat="lat", lon="lon", color="Type", 
                                    custom_data=['Nom', 'percent'], zoom=12, height=500,
                                    color_discrete_map={'Voiture':'#007AFF', 'Velo':'#FF9500'})
        fig_map.update_traces(marker=dict(size=15, opacity=0.9), hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]:.0f}%")
        fig_map.update_layout(mapbox_style="carto-positron", mapbox_center={"lat": 43.608, "lon": 3.877}, margin=dict(l=0,r=0,t=0,b=0), legend=dict(y=0.98, x=0.02, bgcolor="rgba(255,255,255,0.8)"))
        html_map = fig_map.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False})

    # Barres (Top 15)
    def make_bar(data, col):
        if data.empty: return "<p>Pas de données</p>"
        data_top = data.sort_values('percent', ascending=False).head(15)
        fig = px.bar(data_top, x='Nom', y='percent', text=data_top['percent'].apply(lambda x: f"{x:.0f}%"), color_discrete_sequence=[col])
        fig.update_layout(
            margin=dict(l=10,r=10,t=10,b=10), plot_bgcolor='rgba(0,0,0,0)', 
            yaxis=dict(visible=False, range=[0,115]), xaxis=dict(title=None, tickfont=dict(size=10)), height=300
        )
        return fig.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False})

    html_cars = make_bar(last_df[last_df['Type']=='Voiture'], '#007AFF')
    html_bikes = make_bar(last_df[last_df['Type']=='Velo'], '#FF9500')

    # HTML FINAL
    html = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Suivi Montpellier</title>
    <style>
        body{{font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background:#F2F2F7; margin:0; padding:15px; color:#1C1E21}}
        .container{{max-width:1200px; margin:0 auto}}
        .box{{background:white; border-radius:20px; padding:20px; margin-bottom:20px; box-shadow:0 4px 15px rgba(0,0,0,0.05); transition: transform 0.2s}}
        .box:hover {{ transform: translateY(-2px); }}
        h1{{text-align:center; font-weight:800; letter-spacing:-0.5px}} 
        .maj{{font-size:0.6em; background:#E5E5EA; padding:5px 12px; border-radius:15px; color:#555; vertical-align:middle; font-weight:normal}}
        h3{{margin-top:0; color:#111; font-size:1.2rem}}
        .grid{{display:flex; flex-wrap:wrap; gap:20px}} .col{{flex:1; min-width:300px}}
        #graph-box {{ border: 2px solid #007AFF; }}
        .legend-hint {{ text-align:center; color:#888; font-size:0.85rem; margin-top:10px; }}
    </style></head><body>
    <div class="container">
        <h1>🅿️ Montpellier Live <span class="maj">{date_maj}</span></h1>
        
        <div class="box">
            <h3>Carte Interactive</h3>
            {html_map}
            <p class="legend-hint">Note : Seuls les parkings géolocalisés s'affichent.</p>
        </div>
        
        <div class="box" id="graph-box">
            <h3>Historique (7 derniers jours)</h3>
            <div id="graph" style="height:350px; text-align:center; line-height:350px; color:#aaa">Chargement des données...</div>
        </div>

        <div class="grid">
            <div class="box col"><h3>Voitures (Top 15 Remplissage)</h3>{html_cars}</div>
            <div class="box col"><h3>Vélos (Top 15 Remplissage)</h3>{html_bikes}</div>
        </div>
    </div>
    <script>
        var data = {json_str};

        function draw(name) {{
            if(!data[name]) return;
            var c = data[name].type=='Voiture'?'#007AFF':'#FF9500';
            // Configuration Plotly pour un affichage fluide
            Plotly.newPlot('graph', [{{
                x: data[name].dates, y: data[name].values, type: 'scatter', mode: 'lines',
                line: {{color: c, width: 3, shape: 'spline'}}, fill: 'tozeroy'
            }}], {{
                title: name, margin: {{l:40,r:20,t:50,b:40}}, hovermode: 'x unified',
                xaxis: {{type: 'date', tickformat: '%d/%m %Hh'}}, 
                yaxis: {{range: [0, 105], title: '% Remplissage'}},
                bg_color: 'rgba(0,0,0,0)'
            }}, {{displayModeBar: false, responsive: true}});
        }}
        
        // AUTO-START : Lance le graphique au chargement
        window.onload = function() {{
            {default_script}
        }};

        // Écouteur de clics sur tous les graphiques
        document.querySelectorAll('.js-plotly-plot').forEach(el => {{
            if(el.id !== 'graph') {{
                el.on('plotly_click', function(d) {{
                    var name = d.points[0].customdata ? d.points[0].customdata[0] : d.points[0].x;
                    draw(name);
                    // Scroll doux vers le graphique
                    document.getElementById('graph-box').scrollIntoView({{behavior:'smooth', block:'center'}});
                }});
            }}
        }});
    </script></body></html>"""

    with open(FICHIER_HTML, "w", encoding="utf-8") as f: f.write(html)
    print("✅ Site généré V6 (Finale & Polie).")

if __name__ == "__main__": generer()