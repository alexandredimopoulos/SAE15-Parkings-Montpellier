import requests
import csv
import os
import random
import math
import time
from datetime import datetime, timedelta

# Configuration
DAYS_BACK = 14  # On génère 2 semaines d'historique
FICHIER = "data/suivi_global.csv"

# Sources pour récupérer les vrais noms/capacités
URLS = [
    {
        "type": "Voiture",
        "url": "https://portail-api-data.montpellier3m.fr/offstreetparking?limit=1000",
        "key_total": "totalSpotNumber"
    },
    {
        "type": "Velo",
        "url": "https://portail-api-data.montpellier3m.fr/bikestation?limit=1000",
        "key_total": "totalSlotNumber"
    }
]

def generate_history():
    print("1. Récupération de la structure réelle des parkings...")
    parkings_struct = []

    # On récupère la liste réelle pour que la carte soit juste
    for source in URLS:
        try:
            resp = requests.get(source['url'], timeout=10)
            data = resp.json()
            for item in data:
                # Nom
                nom = item.get("name", {}).get("value")
                if not nom:
                    addr = item.get("address", {}).get("value")
                    nom = addr.get("streetAddress", str(addr)) if isinstance(addr, dict) else str(addr)
                nom = str(nom).replace(";", ",").strip()

                # Capacité
                total_obj = item.get(source['key_total'], {})
                total = total_obj.get("value")
                
                # GPS
                coords = item.get("location", {}).get("value", {}).get("coordinates", [None, None])
                lon, lat = coords[0], coords[1]

                if nom and total and lat and lon:
                    parkings_struct.append({
                        "type": source['type'],
                        "parking": nom,
                        "capacite_totale": int(total),
                        "lat": lat,
                        "lon": lon,
                        # Chaque parking aura un "profil" d'occupation légèrement différent
                        "random_offset": random.uniform(0.8, 1.2) 
                    })
        except Exception as e:
            print(f"Erreur source {source['type']}: {e}")

    # Correction de la ligne qui posait problème (guillemets sécurisés)
    print(f"{len(parkings_struct)} infrastructures identifiées. Génération historique...")

    # 2. Génération des données temporelles
    now = datetime.now()
    start_date = now - timedelta(days=DAYS_BACK)
    current_date = start_date
    
    rows = []

    # On avance heure par heure
    while current_date <= now:
        timestamp = int(current_date.timestamp())
        hour = current_date.hour
        weekday = current_date.weekday() # 0=Lundi, 6=Dimanche
        
        # Cycle journalier (0 = vide, 1 = plein)
        activity = max(0, math.sin((hour - 6) * math.pi / 12))
        
        # Le weekend, c'est différent
        if weekday >= 5: 
            activity *= 0.7 
            
        for p in parkings_struct:
            # Calcul du taux d'occupation
            occupancy_rate = activity * p['random_offset'] + random.uniform(-0.05, 0.05)
            occupancy_rate = min(max(occupancy_rate, 0.05), 0.95)

            places_occupees = int(p['capacite_totale'] * occupancy_rate)
            places_libres = p['capacite_totale'] - places_occupees

            rows.append([
                timestamp,
                p['type'],
                p['parking'],
                places_libres,
                p['capacite_totale'],
                p['lat'],
                p['lon']
            ])
        
        current_date += timedelta(hours=1)

    # 3. Écriture du fichier CSV
    os.makedirs("data", exist_ok=True)
    with open(FICHIER, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["timestamp", "type", "parking", "places_libres", "capacite_totale", "lat", "lon"])
        writer.writerows(rows)
    
    print(f"Succès ! {len(rows)} points de données générés.")

if __name__ == "__main__":
    generate_history()