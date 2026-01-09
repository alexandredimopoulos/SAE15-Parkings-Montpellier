import pandas as pd
import plotly.express as px
import os
from datetime import datetime

FICHIER_CSV = "data/suivi_global.csv"
FICHIER_HTML = "index.html"

# Fonction de secours pour toujours créer un fichier HTML
def creer_page_erreur(message):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Maintenance</title></head>
    <body style="font-family:sans-serif; text-align:center; padding:50px; color:#333;">
        <h1>⚠️ Maintenance en cours</h1>
        <p>{message}</p>
        <p>Le système redémarre, veuillez patienter 10 minutes.</p>
    </body>
    </html>
    """
    with open(FICHIER_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Page de maintenance générée : {message}")

def generer_html():
    # 1. Vérification présence CSV
    if not os.path.exists(FICHIER_CSV):
        creer_page_erreur("Le fichier de données (CSV) est en cours de création.")
        return

    try:
        df = pd.read_csv(FICHIER_CSV, delimiter=";")
        df.columns = df.columns.str.strip()
    except Exception as e:
        creer_page_erreur(f"Erreur de lecture du CSV : {e}")
        return

    # 2. Vérification des colonnes (C'est souvent ici que ça bloque si le collecteur est vieux)
    required = ['timestamp', 'type', 'places_libres', 'capacite_totale']
    missing = [col for col in required if col not in df.columns]
    
    if missing:
        creer_page_erreur(f"Colonnes manquantes dans les données : {', '.join(missing)}.<br>Le script de collecte doit être mis à jour.")
        return

    # --- À partir d'ici, on sait que les données sont bonnes ---
    
    # Conversion date
    df['date'] = pd.to_datetime(df['timestamp'], unit='s') + pd.Timedelta(hours=1)
    
    # Dernier état
    last_ts = df['timestamp'].max()
    df_last = df[df['timestamp'] == last_ts].copy()
    date_maj = datetime.fromtimestamp(last_ts).strftime('%H:%M')

    # --- CALCULS ---
    df_last['capacite_totale'] = pd.to_numeric(df_last['capacite_totale'], errors='coerce')
    df_last = df_last[df_last['capacite_totale'] > 0] # On garde que ceux qui ont une capacité > 0

    # Calcul pourcentage
    df_last['percent_fill'] = (1 - (df_last['places_libres'] / df_last['capacite_totale'])) * 100
    
    # Texte formaté : "75% (12 places)"
    df_last['label_text'] = df_last.apply(
        lambda x: f"{x['percent_fill']:.0f}% ({int(x['places_libres'])} pl.)", axis=1
    )

    # --- STYLE ---
    layout_config = {
        'plot_bgcolor': 'rgba(0,0,0,0)', 'paper_bgcolor': 'rgba(0,0,0,0)',
        'font': {'family': '-apple-system, BlinkMacSystemFont, Roboto, sans-serif'},
        'margin': dict(l=10, r=10, t=10, b=10)
    }
    COLOR_MAP = {'Voiture': '#007AFF', 'Velo': '#FF9500'}

    # --- CARTE ---
    df_map = df_last.dropna(subset=['lat', 'lon'])
    fig_map = px.scatter_mapbox(
        df_map, lat="lat", lon="lon", color="type",
        size="capacite_totale", size_max=15, zoom=12, height=350,
        color_discrete_map=COLOR_MAP
    )
    fig_map.update_layout(mapbox_style="carto-positron", mapbox_center={"lat": 43.608, "lon": 3.877}, margin=dict(l=0, r=0, t=0, b=0), legend=dict(yanchor="top", y=0.95, xanchor="left", x=0.05))
    html_map = fig_map.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False})

    # --- FONCTION GRAPHIQUE ---
    def create_bar_chart(data, color):
        if data.empty: return "<p class='card-subtitle'>Données indisponibles</p>"
        data = data.sort_values('percent_fill', ascending=False)
        fig = px.bar(
            data, x='parking', y='percent_fill', text='label_text',
            color_discrete_sequence=[color]
        )
        fig.update_traces(textposition='outside', marker_cornerradius=5)
        fig.update_layout(**layout_config)
        fig.update_yaxes(visible=False, showgrid=False, range=[0, 125])
        fig.update_xaxes(title=None, tickangle=-45)
        return fig.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False})

    html_cars = create_bar_chart(df_last[df_last['type'] == 'Voiture'], COLOR_MAP['Voiture'])
    
    # Pour les vélos, on raccourcit les noms
    df_bikes = df_last[df_last['type'] == 'Velo'].copy()
    if not df_bikes.empty:
        df_bikes['parking'] = df_bikes['parking'].apply(lambda x: x[:18] + '..' if len(x) > 18 else x)
    html_bikes = create_bar_chart(df_bikes, COLOR_MAP['Velo'])

    # --- HTML FINAL ---
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
                    <div class="card-subtitle">Localisation et densité</div>
                </div>
                {html_map}
            </div>
            <div class="card">
                <div class="card-header"><span class="icon">🚗</span><div><h2 class="card-title">Parkings</h2><div class="card-subtitle">Taux de remplissage</div></div></div>
                {html_cars}
            </div>
            <div class="card">
                <div class="card-header"><span class="icon">🚲</span><div><h2 class="card-title">Vélomagg</h2><div class="card-subtitle">Taux de remplissage</div></div></div>
                {html_bikes}
            </div>
            <footer>SAE15 • Données OpenData Montpellier</footer>
        </div>
    </body>
    </html>
    """

    with open(FICHIER_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    print("Site mis à jour avec succès !")

if __name__ == "__main__":
    generer_html()