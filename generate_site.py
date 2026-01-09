import pandas as pd
import plotly.express as px
import os
from datetime import datetime

FICHIER_CSV = "data/suivi_global.csv"
FICHIER_HTML = "index.html"

# --- Fonction de secours (Maintenance) ---
def creer_page_erreur(message):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Maintenance</title></head>
    <body style="font-family:-apple-system, sans-serif; text-align:center; padding:50px; color:#333;">
        <h1>⚠️ Maintenance en cours</h1>
        <p>{message}</p>
        <p>Le système redémarre, veuillez patienter quelques minutes.</p>
    </body>
    </html>
    """
    with open(FICHIER_HTML, "w", encoding="utf-8") as f:
        f.write(html)

def generer_html():
    if not os.path.exists(FICHIER_CSV):
        creer_page_erreur("Initialisation des données...")
        return

    try:
        df = pd.read_csv(FICHIER_CSV, delimiter=";")
        df.columns = df.columns.str.strip()
    except Exception as e:
        creer_page_erreur(f"Erreur lecture CSV : {e}")
        return

    # Vérification colonnes
    required = ['timestamp', 'type', 'places_libres', 'capacite_totale']
    if not all(col in df.columns for col in required):
        creer_page_erreur("Mise à jour de la structure des données en cours...")
        return

    # --- PRÉPARATION DONNÉES ---
    df['date'] = pd.to_datetime(df['timestamp'], unit='s') + pd.Timedelta(hours=1)
    
    # On garde la dernière mesure
    last_ts = df['timestamp'].max()
    df_last = df[df['timestamp'] == last_ts].copy()
    date_maj = datetime.fromtimestamp(last_ts).strftime('%H:%M')

    # Nettoyage et Calculs
    df_last['capacite_totale'] = pd.to_numeric(df_last['capacite_totale'], errors='coerce')
    df_last = df_last[df_last['capacite_totale'] > 0]
    
    # Calcul % remplissage
    df_last['percent_fill'] = (1 - (df_last['places_libres'] / df_last['capacite_totale'])) * 100
    
    # Texte étiquette (Barres)
    df_last['label_text'] = df_last.apply(
        lambda x: f"{x['percent_fill']:.0f}% ({int(x['places_libres'])} pl.)", axis=1
    )

    # --- CONFIGURATION STYLE ---
    layout_config = {
        'plot_bgcolor': 'rgba(0,0,0,0)', 
        'paper_bgcolor': 'rgba(0,0,0,0)',
        'font': {'family': '-apple-system, BlinkMacSystemFont, Roboto, sans-serif'},
        'margin': dict(l=0, r=0, t=0, b=0)
    }
    COLOR_MAP = {'Voiture': '#007AFF', 'Velo': '#FF9500'}

    # --- 1. CARTE (Corrigée : Taille fixe + InfoBulle propre) ---
    df_map = df_last.dropna(subset=['lat', 'lon'])
    
    fig_map = px.scatter_mapbox(
        df_map, 
        lat="lat", 
        lon="lon", 
        color="type",
        # On supprime le paramètre size pour que tous les points aient la même taille
        hover_name="parking",
        # On passe les données qu'on veut afficher dans custom_data
        custom_data=['type', 'percent_fill', 'places_libres'], 
        color_discrete_map=COLOR_MAP,
        zoom=12, 
        height=350
    )
    
    fig_map.update_traces(
        marker=dict(size=12, opacity=0.9), # Taille des boules plus grosse et fixe
        # C'est ici qu'on définit exactement ce qui s'affiche au survol
        hovertemplate="<b>%{hovertext}</b><br>" +
                      "Type: %{customdata[0]}<br>" +
                      "Remplissage: %{customdata[1]:.0f}%<br>" +
                      "Places libres: %{customdata[2]}<extra></extra>" 
                      # <extra></extra> enlève le cadre secondaire inutile
    )
    
    fig_map.update_layout(
        mapbox_style="carto-positron", 
        mapbox_center={"lat": 43.608, "lon": 3.877},
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(yanchor="top", y=0.95, xanchor="left", x=0.05, bgcolor="rgba(255,255,255,0.9)")
    )
    html_map = fig_map.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False})

    # --- FONCTION GRAPHIQUE (Corrigée : Texte plus gros) ---
    def create_bar_chart(data, color):
        if data.empty: return "<p style='text-align:center; color:#999;'>Aucune donnée disponible</p>"
        
        data = data.sort_values('percent_fill', ascending=False)
        
        fig = px.bar(
            data, x='parking', y='percent_fill', text='label_text',
            color_discrete_sequence=[color]
        )
        
        fig.update_traces(
            textposition='outside',
            textfont_size=14,  # Texte plus gros
            textfont_weight='bold', # Texte en gras
            marker_cornerradius=5,
            cliponaxis=False, # Empêche le texte d'être coupé en haut
            hovertemplate="<b>%{x}</b><br>Remplissage: %{y:.1f}%<extra></extra>"
        )
        
        fig.update_layout(**layout_config)
        # On laisse de la place en haut (range max 130%) pour le texte
        fig.update_yaxes(visible=False, showgrid=False, range=[0, 135]) 
        fig.update_xaxes(title=None, tickangle=-45)
        
        return fig.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False})

    # --- GÉNÉRATION DES BLOCS ---
    html_cars = create_bar_chart(df_last[df_last['type'] == 'Voiture'], COLOR_MAP['Voiture'])
    
    # Pour les vélos, on coupe les noms trop longs
    df_bikes = df_last[df_last['type'] == 'Velo'].copy()
    if not df_bikes.empty:
        df_bikes['parking'] = df_bikes['parking'].apply(lambda x: x[:15] + '..' if len(x) > 15 else x)
    html_bikes = create_bar_chart(df_bikes, COLOR_MAP['Velo'])

    # --- HTML FINAL (Style iOS) ---
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
            h1 {{ font-size: 20px; font-weight: 700; margin: 0; letter-spacing: -0.5px; }}
            .pill {{ background: #E5E5EA; color: var(--text-secondary); padding: 6px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; }}
            
            .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
            .card {{ background: var(--card-bg); border-radius: 22px; padding: 24px; margin-bottom: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.04); overflow: hidden; }}
            
            .card-header {{ display: flex; align-items: center; margin-bottom: 20px; }}
            .icon {{ font-size: 24px; margin-right: 12px; }}
            .card-title {{ font-size: 19px; font-weight: 700; margin: 0; }}
            .card-subtitle {{ font-size: 14px; color: var(--text-secondary); margin-top: 2px; }}
            
            footer {{ text-align: center; color: var(--text-secondary); font-size: 12px; padding: 20px 0 40px 0; }}
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
                </div>
                {html_map}
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="icon">🚗</span>
                    <div><h2 class="card-title">Parkings</h2><div class="card-subtitle">Taux de remplissage</div></div>
                </div>
                {html_cars}
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="icon">🚲</span>
                    <div><h2 class="card-title">Vélomagg</h2><div class="card-subtitle">Taux de remplissage</div></div>
                </div>
                {html_bikes}
            </div>
            
            <footer>SAE15 • Données OpenData Montpellier</footer>
        </div>
    </body>
    </html>
    """

    with open(FICHIER_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    print("Site mis à jour !")

if __name__ == "__main__":
    generer_html()