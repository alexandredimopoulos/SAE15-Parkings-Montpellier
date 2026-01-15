import requests
import csv
import time
from datetime import datetime
import os

# Ton fichier précis
FICHIER = "data/suivi_global.csv"

# Les URLs officielles de Montpellier
URLS = [
    {"type": "Voiture", "url": "https://portail-api-data.montpellier3m.fr/offstreetparking?limit=1000", "key_tot": "totalSpotNumber", "key_free": "availableSpotNumber"},
    {"type": "Velo", "url": "https://portail-api-data.montpellier3m.fr/bikestation?limit=1000", "key_tot": "totalSlotNumber", "key_free": "availableBikeNumber"}
]

def collecter():
    # 1. On prépare la date et l'heure actuelles
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    heure_str = now.strftime("%H:%M")
    
    new_rows = []

    print(f"🔄 Récupération des données pour le {date_str} à {heure_str}...")

    for s in URLS:
        try:
            resp = requests.get(s['url'], timeout=10)
            data = resp.json()
            for item in data:
                try:
                    # Extraction des données
                    nom = item.get("name", {}).get("value", "Inconnu")
                    nom = str(nom).replace(";", ",").strip() # On évite les points-virgules qui cassent le CSV
                    
                    total = int(item.get(s['key_tot'], {}).get("value", 0))
                    free = int(item.get(s['key_free'], {}).get("value", 0))
                    
                    # Correction de données aberrantes
                    if free > total: free = total
                    if free < 0: free = 0
                    
                    if total > 0:
                        # On ajoute la ligne EXACTEMENT comme ton format :
                        # Date;Heure;Type;Nom;Places_Libres;Places_Totales
                        new_rows.append([date_str, heure_str, s['type'], nom, free, total])
                except:
                    continue
        except Exception as e:
            print(f"Erreur sur {s['type']}: {e}")

    # 2. Ajout au fichier CSV
    if new_rows:
        os.makedirs("data", exist_ok=True)
        # Si le fichier n'existe pas, on crée l'entête
        file_exists = os.path.exists(FICHIER)
        
        with open(FICHIER, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=";")
            if not file_exists:
                writer.writerow(["Date", "Heure", "Type", "Nom", "Places_Libres", "Places_Totales"])
            writer.writerows(new_rows)
        
        print(f"✅ {len(new_rows)} lignes ajoutées au fichier CSV.")
    else:
        print("⚠️ Aucune donnée récupérée.")

if __name__ == "__main__":
    collecter()