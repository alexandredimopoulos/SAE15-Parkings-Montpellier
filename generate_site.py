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

    if 'timestamp' not in df.columns or 'type' not in df.columns:
        print("Colonnes manquantes.")
        return

    # Conversion date
    df['date'] = pd.to_datetime(df['timestamp'], unit='s') + pd.Timedelta(hours=1)
    
    # Dernier état
    last_ts = df['timestamp'].max()
    df_last = df[df['timestamp'] == last_ts].copy()
    date_maj = datetime.fromtimestamp(last_ts).strftime('%H:%M')
    date_jour = datetime.fromtimestamp(last_ts).strftime('%d/%m/%Y')

    # --- Configuration du style des graphiques (Minimaliste) ---
    layout_config = {
        'plot_bgcolor': 'rgba(0,0,0,0)',
        'paper_bgcolor': 'rgba(0,0,0,0)',
        'font': {'family': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'},
        'margin': dict(l=20, r=20, t=20, b=20)
    }

    # --- 1. GRAPHIQUE VOITURES ---
    df_cars = df_last[df_last['type'] == 'Voiture'].sort_values('places_libres', ascending=False)
    
    if not df_cars.empty:
        fig_cars = px.bar(
            df_cars, x='parking', y='places_libres',
            text='places_libres', # Affiche le nombre sur la barre
            color_discrete_sequence=['#007AFF'] # Bleu iOS System
        )
        fig_cars.update_traces(textposition='outside', marker_cornerradius=5)
        fig_cars.update_layout(**layout_config)
        fig_cars.update_yaxes(visible=False, showgrid=False) # On cache l'axe Y pour épurer
        fig_cars.update_xaxes(title=None, tickangle=-45)
        html_cars = fig_cars.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False})
    else:
        html_cars = "<p>Pas de données voitures.</p>"
    
    # --- 2. GRAPHIQUE VÉLOS ---
    df_bikes = df_last[df_last['type'] == 'Velo'].sort_values('places_libres', ascending=False)
    
    if not df_bikes.empty:
        fig_bikes = px.bar(
            df_bikes, x='parking', y='places_libres',
            text='places_libres',
            color_discrete_sequence=['#FF9500'] # Orange iOS System
        )
        fig_bikes.update_traces(textposition='outside', marker_cornerradius=5)
        fig_bikes.update_layout(**layout_config)
        fig_bikes.update_yaxes(visible=False, showgrid=False)
        fig_bikes.update_xaxes(title=None, tickangle=-45)
        html_bikes = fig_bikes.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False})
    else:
        html_bikes = "<p>Pas de données vélos.</p>"

    # --- GÉNÉRATION HTML STYLE IOS ---
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Mobilité Montpellier</title>
        <style>
            :root {{
                --bg-color: #F2F2F7; /* iOS System Gray 6 */
                --card-bg: #FFFFFF;
                --text-primary: #000000;
                --text-secondary: #8E8E93;
                --accent-blue: #007AFF;
                --accent-orange: #FF9500;
            }}

            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                background-color: var(--bg-color);
                color: var(--text-primary);
                margin: 0;
                padding: 0;
                -webkit-font-smoothing: antialiased;
            }}

            /* Header avec effet "Glassmorphism" */
            header {{
                position: sticky;
                top: 0;
                background-color: rgba(255, 255, 255, 0.85);
                backdrop-filter: saturate(180%) blur(20px);
                -webkit-backdrop-filter: saturate(180%) blur(20px);
                border-bottom: 1px solid rgba(0,0,0,0.1);
                padding: 15px 20px;
                z-index: 1000;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}

            h1 {{
                font-size: 22px;
                font-weight: 700;
                margin: 0;
                letter-spacing: -0.5px;
            }}

            .status-pill {{
                background-color: #E5E5EA;
                color: var(--text-secondary);
                padding: 6px 12px;
                border-radius: 20px;
                font-size: 13px;
                font-weight: 600;
            }}

            .container {{
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }}

            .section-title {{
                font-size: 28px;
                font-weight: 800;
                margin: 30px 0 15px 5px;
                color: #1C1C1E;
            }}

            /* Carte style iOS */
            .card {{
                background: var(--card-bg);
                border-radius: 22px; /* Arrondi prononcé */
                padding: 24px;
                margin-bottom: 24px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.06); /* Ombre douce et diffuse */
                transition: transform 0.2s ease;
            }}

            .card-header {{
                display: flex;
                align-items: center;
                margin-bottom: 15px;
            }}

            .icon {{
                font-size: 24px;
                margin-right: 12px;
            }}

            .card-title {{
                font-size: 19px;
                font-weight: 600;
                margin: 0;
            }}

            .card-subtitle {{
                font-size: 14px;
                color: var(--text-secondary);
                margin-top: 4px;
            }}

            footer {{
                text-align: center;
                padding: 40px;
                color: var(--text-secondary);
                font-size: 12px;
            }}
            
            /* Responsive */
            @media (max-width: 600px) {{
                .container {{ padding: 15px; }}
                .card {{ padding: 15px; border-radius: 18px; }}
                .section-title {{ font-size: 24px; margin-left: 0; }}
            }}
        </style>
    </head>
    <body>

        <header>
            <h1>Montpellier Live</h1>
            <div class="status-pill">Maj : {date_maj}</div>
        </header>

        <div class="container">
            
            <div class="section-title">Aujourd'hui</div>

            <div class="card">
                <div class="card-header">
                    <span class="icon">🚗</span>
                    <div>
                        <h2 class="card-title">Parkings</h2>
                        <div class="card-subtitle">Places disponibles en temps réel</div>
                    </div>
                </div>
                {html_cars}
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="icon">🚲</span>
                    <div>
                        <h2 class="card-title">Vélomagg</h2>
                        <div class="card-subtitle">Vélos disponibles en station</div>
                    </div>
                </div>
                {html_bikes}
            </div>

            <footer>
                Projet SAE15 • Données OpenData Montpellier<br>
                Actualisé automatiquement via GitHub Actions
            </footer>
        </div>

    </body>
    </html>
    """

    with open(FICHIER_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print("Site web style iOS généré !")

if __name__ == "__main__":
    generer_html()