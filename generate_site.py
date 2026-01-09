import pandas as pd
import plotly.express as px
import os
from datetime import datetime

FICHIER_CSV = "data/suivi_global.csv"
FICHIER_HTML = "index.html"

def generer_html():
    # 1. Vérification de l'existence du fichier
    if not os.path.exists(FICHIER_CSV):
        print(f"Erreur : Le fichier {FICHIER_CSV} n'existe pas encore.")
        return

    # 2. Chargement des données
    try:
        # On lit le CSV avec le séparateur point-virgule
        df = pd.read_csv(FICHIER_CSV, delimiter=";")
        
        # --- CORRECTION CRITIQUE ICI ---
        # On enlève les espaces potentiels autour des noms de colonnes
        # (Ex: " timestamp" devient "timestamp")
        df.columns = df.columns.str.strip()
        
    except Exception as e:
        print(f"Erreur lors de la lecture du CSV : {e}")
        return

    # 3. Vérification de la colonne timestamp
    if 'timestamp' not in df.columns:
        print("Erreur : La colonne 'timestamp' est introuvable. Colonnes vues :", df.columns.tolist())
        return

    # 4. Traitement des dates
    try:
        # Conversion du timestamp UNIX en date lisible (+1h pour fuseau horaire approx)
        df['date'] = pd.to_datetime(df['timestamp'], unit='s') + pd.Timedelta(hours=1)
    except Exception as e:
        print(f"Erreur de conversion de date : {e}")
        return

    # 5. Préparation des données pour le dernier état connu (Barres)
    # On prend le timestamp le plus récent
    last_timestamp = df['timestamp'].max()
    df_last = df[df['timestamp'] == last_timestamp].sort_values(by='places_libres', ascending=False)
    
    date_maj = datetime.fromtimestamp(last_timestamp).strftime('%d/%m/%Y à %H:%M')

    # 6. Création des Graphiques avec Plotly
    
    # Graphique 1 : Places libres actuelles (Barres)
    fig_bar = px.bar(
        df_last, 
        x='parking', 
        y='places_libres', 
        color='places_libres',
        title=f"Places disponibles (Dernière mise à jour : {date_maj})",
        labels={'places_libres': 'Places Libres', 'parking': 'Parking'},
        color_continuous_scale='Viridis'
    )

    # Graphique 2 : Historique (Courbes)
    # On ne garde que les 2000 dernières mesures pour que le graph reste lisible
    df_history = df.tail(2000) 
    fig_line = px.line(
        df_history, 
        x='date', 
        y='places_libres', 
        color='parking',
        title="Évolution de l'occupation (Historique récent)",
        labels={'places_libres': 'Places Libres', 'date': 'Heure'}
    )

    # 7. Génération du HTML complet
    # On convertit les graphiques en HTML
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
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; background-color: #f0f2f5; color: #333; }}
            header {{ background-color: #2c3e50; color: white; padding: 20px; text-align: center; }}
            .container {{ max-width: 1200px; margin: 20px auto; padding: 0 15px; }}
            .card {{ background: white; padding: 25px; margin-bottom: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            h1 {{ margin: 0; font-size: 2rem; }}
            h2 {{ color: #2c3e50; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
            footer {{ text-align: center; padding: 20px; color: #7f8c8d; font-size: 0.9em; }}
        </style>
    </head>
    <body>
        <header>
            <h1>🅿️ Suivi des Parkings de Montpellier</h1>
        </header>

        <div class="container">
            <div class="card">
                <h2>État Actuel</h2>
                {graph_bar_html}
            </div>

            <div class="card">
                <h2>Historique</h2>
                {graph_line_html}
            </div>
            
            <footer>
                <p>Données actualisées automatiquement toutes les 10 minutes.</p>
                <p>Source : API Open Data Montpellier | Projet SAE15</p>
            </footer>
        </div>
    </body>
    </html>
    """

    # Écriture du fichier
    with open(FICHIER_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print("Site web généré avec succès !")

if __name__ == "__main__":
    generer_html()