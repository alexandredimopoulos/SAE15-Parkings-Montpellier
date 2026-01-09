import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime

FICHIER_CSV = "data/suivi_global.csv"
FICHIER_HTML = "index.html"

def generer_html():
    # 1. Chargement des données
    if not os.path.exists(FICHIER_CSV):
        print("Pas de données disponibles.")
        return

    try:
        df = pd.read_csv(FICHIER_CSV, delimiter=";")
    except Exception:
        print("Erreur de lecture du CSV (fichier vide ?)")
        return

    # Conversion du timestamp UNIX en date lisible
    df['date'] = pd.to_datetime(df['timestamp'], unit='s') + pd.Timedelta(hours=1) # Ajustement fuseau horaire approx

    # 2. Préparation des données pour le dernier état connu
    # On prend la dernière mesure pour chaque parking
    last_timestamp = df['timestamp'].max()
    df_last = df[df['timestamp'] == last_timestamp].sort_values(by='places_libres', ascending=False)

    # 3. Création des Graphiques
    
    # Graphique 1 : Places libres actuelles (Barres)
    fig_bar = px.bar(
        df_last, 
        x='parking', 
        y='places_libres', 
        color='places_libres',
        title=f"Places disponibles (Dernière mise à jour : {datetime.fromtimestamp(last_timestamp)})",
        labels={'places_libres': 'Places Libres', 'parking': 'Parking'},
        color_continuous_scale='Viridis'
    )

    # Graphique 2 : Historique (Courbes) - On limite aux 5000 derniers points pour ne pas surcharger
    # Pour un graph lisible, on peut filtrer sur les dernières 24h
    df_history = df.tail(2000) 
    fig_line = px.line(
        df_history, 
        x='date', 
        y='places_libres', 
        color='parking',
        title="Évolution de l'occupation (Historique récent)",
        labels={'places_libres': 'Places Libres', 'date': 'Heure'}
    )

    # 4. Génération du HTML complet
    # On exporte les graphiques en HTML partiel (div)
    graph_bar_html = fig_bar.to_html(full_html=False, include_plotlyjs='cdn')
    graph_line_html = fig_line.to_html(full_html=False, include_plotlyjs='cdn')

    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Météo des Parkings - Montpellier</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f9; }}
            h1 {{ text-align: center; color: #333; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .card {{ background: white; padding: 20px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            footer {{ text-align: center; margin-top: 40px; color: #777; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🅿️ Suivi des Parkings de Montpellier</h1>
            
            <div class="card">
                {graph_bar_html}
            </div>

            <div class="card">
                {graph_line_html}
            </div>
            
            <footer>
                <p>Données issues de l'Open Data Montpellier. Actualisé automatiquement via GitHub Actions.</p>
                <p>Projet SAE15.</p>
            </footer>
        </div>
    </body>
    </html>
    """

    with open(FICHIER_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print("Site web généré avec succès !")

if __name__ == "__main__":
    generer_html()