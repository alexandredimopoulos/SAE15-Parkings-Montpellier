import pandas as pd
import plotly.express as px
import os
from datetime import datetime

FICHIER_CSV = "data/suivi_global.csv"
FICHIER_HTML = "index.html"

def generer_html():
    if not os.path.exists(FICHIER_CSV):
        return

    try:
        df = pd.read_csv(FICHIER_CSV, delimiter=";")
        df.columns = df.columns.str.strip()
    except Exception as e:
        print(f"Erreur CSV: {e}")
        return

    # Vérification des colonnes nécessaires
    required = ['timestamp', 'type', 'places_libres', 'capacite_totale']
    if not all(col in df.columns for col in required):
        print("Colonnes manquantes. Supprimez le CSV et relancez la collecte.")
        return

    # Conversion date
    df['date'] = pd.to_datetime(df['timestamp'], unit='s') + pd.Timedelta(hours=1)
    
    # Dernier état
    last_ts = df['timestamp'].max()
    df_last = df[df['timestamp'] == last_ts].copy()
    date_maj = datetime.fromtimestamp(last_ts).strftime('%H:%M')

    # --- CALCULS ---
    # On évite la division par zéro
    df_last['capacite_totale'] = pd.to_numeric(df_last['capacite_totale'], errors='coerce')
    df_last = df_last[df_last['capacite_totale'] > 0] # On garde que ceux qui ont une capacité > 0

    # Calcul pourcentage d'occupation (remplissage)
    df_last['percent_fill'] = (1 - (df_last['places_libres'] / df_last['capacite_totale'])) * 100
    
    # Création du texte formaté : "75% (12 places)"
    # Le .0f arrondit le pourcentage
    df_last['label_text'] = df_last.apply(
        lambda x: f"{x['percent_fill']:.0f}% ({int(x['places_libres'])} places)", axis=1
    )

    # --- Style Global ---
    layout_config = {
        'plot_bgcolor': 'rgba(0,0,0,0)',
        'paper_bgcolor': 'rgba(0,0,0,0)',
        'font': {'family': '-apple-system, BlinkMacSystemFont, Roboto, sans-serif'},
        'margin': dict(l=10, r=10, t=10, b=10)
    }
    COLOR_MAP = {'Voiture': '#007AFF', 'Velo': '#FF9500'}

    # --- 1. CARTE ---
    df_map = df_last.dropna(subset=['lat', 'lon'])
    fig_map = px.scatter_mapbox(
        df_map, lat="lat", lon="lon", color="type",
        size="capacite_totale", # La taille du point dépend de la capacité totale
        size_max=15,
        hover_name="parking",
        hover_data={"places_libres": True, "percent_fill": ":.1f", "lat": False, "lon": False},
        color_discrete_map=COLOR_MAP, zoom=12, height=350
    )
    fig_map.update_layout(mapbox_style="carto-positron", mapbox_center={"lat": 43.608, "lon": 3.877}, margin=dict(l=0, r=0, t=0, b=0), legend=dict(yanchor="top", y=0.95, xanchor="left", x=0.05))
    html_map = fig_map.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False})

    # --- FONCTION POUR CRÉER LES GRAPHIQUES ---
    def create_bar_chart(data, color):
        if data.empty: return "<p>Données indisponibles</p>"
        
        # On trie par remplissage (le plus plein en haut/gauche)
        data = data.sort_values('percent_fill', ascending=False)
        
        fig = px.bar(
            data, x='parking', y='percent_fill',
            text='label_text', # C'est ici qu'on met notre texte personnalisé
            color_discrete_sequence=[color],
            # Custom Hover (ce qu'on voit quand on passe la souris)
            hover_data={'places_libres': True, 'capacite_totale': True, 'percent_fill': False, 'label_text': False} 
        )
        
        fig.update_traces(
            textposition='outside', 
            marker_cornerradius=5,
            hovertemplate="<b>%{x}</b><br>Rempli à: %{y:.1f}%<br>Places libres: %{customdata[0]}<br>Capacité totale: %{customdata[1]}"
        )
        fig.update_layout(**layout_config)
        fig.update_yaxes(visible=False, showgrid=False, range=[0, 115]) # Range un peu plus haut pour laisser place au texte
        fig.update_xaxes(title=None, tickangle=-45)
        
        return fig.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False})

    # --- 2. GRAPHIQUE VOITURES ---
    df_cars = df_last[df_last['type'] == 'Voiture']
    html_cars = create_bar_chart(df_cars, COLOR_MAP['Voiture'])

    # --- 3. GRAPHIQUE VÉLOS ---
    df_bikes = df_last[df_last['type'] == 'Velo'].copy()
    # Raccourcir les noms longs
    df_bikes['parking'] = df_bikes['parking'].apply(lambda x: x[:20] + '...' if len(x) > 20 else x)
    html_bikes = create_bar_chart(df_bikes, COLOR_MAP['Velo'])

    # --- HTML ---
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Mobilité Montpellier</title>
        <style>
            :root {{ --bg-color: #F2F2F7; --card-bg: #FFFFFF; --text-primary: #000; --text-secondary: #8E8E93; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: var(--bg-color); color: var(--text-primary); margin: 0; padding: 0; }}
            header {{ position: sticky; top: 0; background-color: rgba(255, 255, 255, 0.85); backdrop-filter: saturate(180%) blur(20px); -webkit-backdrop-filter: saturate(180%) blur(20px); border-bottom: 1px solid rgba(0,0,0,0.1); padding: 15px 20px; z-index: 1000; display: flex; justify-content: space-between; align-items: center; }}
            h1 {{ font-size: 20px; font-weight: 700; margin: 0; }}
            .status-pill {{ background-color: #E5E5EA; color: var(--text-secondary); padding: 5px 12px; border-radius: 15px; font-size: 13px; font-weight: 600; }}
            .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
            .card {{ background: var(--card-bg); border-radius: 20px; padding: 20px; margin-bottom: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); overflow: hidden; }}
            .card-header {{ display: flex; align-items: center; margin-bottom: 15px; }}
            .icon {{ font-size: 24px; margin-right: 12px; }}
            .card-title {{ font-size: 18px; font-weight: 600; margin: 0; }}
            .card-subtitle {{ font-size: 13px; color: var(--text-secondary); }}
            footer {{ text-align: center; color: var(--text-secondary); font-size: 11px; padding-bottom: 40px; }}
        </style>
    </head>
    <body>
        <header>
            <h1>Montpellier Live</h1>
            <div class="status-pill">{date_maj}</div>
        </header>
        <div class="container">
            <div class="card" style="padding:0;">
                <div style="padding: 20px 20px 5px 20px;">
                    <h2 class="card-title">Carte</h2>
                    <div class="card-subtitle">Taille des points selon la capacité</div>
                </div>
                {html_map}
            </div>
            <div class="card">
                <div class="card-header"><span class="icon">🚗</span><div><h2 class="card-title">Parkings</h2><div class="card-subtitle">Taux de remplissage</div></div></div>
                {html_cars}
            </div>
            <div class="card">
                <div class="card-header"><span class="icon">🚲</span><div><h2 class="card-title">Vélomagg</h2><div class="card-subtitle">Taux de remplissage des stations</div></div></div>
                {html_bikes}
            </div>
            <footer>SAE15 • Données OpenData Montpellier</footer>
        </div>
    </body>
    </html>
    """

    with open(FICHIER_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    print("Site mis à jour avec pourcentages !")

if __name__ == "__main__":
    generer_html()