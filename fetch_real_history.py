import requests
import csv
import os
import time
from datetime import datetime, timedelta

# Configuration
DAYS_BACK = 7  # On récupère les 7 derniers jours
FICHIER = "data/suivi_global.csv"
BASE_URL = "https://portail-api-data.montpellier3m.fr"

# Configuration des endpoints
SOURCES = [
    {
        "type": "Voiture",
        "list_url": f"{BASE_URL}/offstreetparking?limit=1000",
        # Endpoint historique : /parking_timeseries/{id}/attrs/availableSpotNumber
        "history_path": "/parking_timeseries/{id}/attrs/availableSpotNumber",
        "key_total": "totalSpotNumber",
        "key_free": "availableSpotNumber"
    },
    {
        "type": "Velo",
        "list_url": f"{BASE_URL}/bikestation?limit=1000",
        # Endpoint historique : /bikestation_timeseries/{id}/attrs/availableBikeNumber
        "history_path": "/bikestation_timeseries/{id}/attrs/availableBikeNumber",
        "key_total": "totalSlotNumber",
        "key_free": "availableBikeNumber"
    }
]

def get_history():
    print("🚀 Démarrage de la récupération du VRAI historique...")
    
    # Calcul de la date de départ (il y a 7 jours) au format requis par l'API
    # Format API attendu : 2023-01-01T00:00:00
    start_date = (datetime.now() - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%dT%H:%M:%S")
    
    all_rows = []

    for source in SOURCES:
        print(f"\n📡 Récupération de la liste : {source['type']}...")
        try:
            # 1. On récupère la liste des objets (Parkings ou Stations)
            resp = requests.get(source['list_url'], timeout=10)
            resp.raise_for_status()
            items = resp.json()
            
            print(f"   {len(items)} éléments trouvés. Téléchargement des historiques...")

            for item in items:
                try:
                    # Extraction des infos statiques (Nom, Capacité, GPS, ID)
                    item_id = item.get("id")
                    
                    # Nom
                    nom = item.get("name", {}).get("value")
                    if not nom:
                        addr = item.get("address", {}).get("value")
                        nom = addr.get("streetAddress", str(addr)) if isinstance(addr, dict) else str(addr)
                    nom = str(nom).replace(";", ",").strip()

                    # Capacité & GPS
                    total = item.get(source['key_total'], {}).get("value", 0)
                    coords = item.get("location", {}).get("value", {}).get("coordinates", [None, None])
                    lon, lat = coords[0], coords[1]

                    if not item_id or not total:
                        continue

                    # 2. On appelle l'API Historique pour CET item
                    # URL ex: /parking_timeseries/urn:ngsi-ld:parking:001/attrs/availableSpotNumber?fromDate=...
                    hist_url = f"{BASE_URL}{source['history_path'].format(id=item_id)}"
                    params = {"fromDate": start_date}
                    
                    h_resp = requests.get(hist_url, params=params, timeout=5)
                    
                    if h_resp.status_code == 200:
                        h_data = h_resp.json()
                        
                        # L'API renvoie souvent un format { "index": [dates...], "values": [valeurs...] }
                        # ou parfois directement une liste de valeurs. On s'adapte.
                        timestamps = h_data.get("index", [])
                        values = h_data.get("values", [])
                        
                        # Si on a bien des données
                        if timestamps and values:
                            # On ne garde qu'un point toutes les ~30 minutes pour ne pas avoir un CSV de 500Mo
                            # (L'API peut renvoyer une donnée par minute)
                            step = 30 
                            for i in range(0, len(timestamps), step):
                                ts_str = timestamps[i]  # Ex: 2023-10-25T08:00:00.000Z
                                val = values[i]
                                
                                # Conversion date string -> timestamp UNIX pour le CSV
                                try:
                                    # On nettoie le string (enlève le Z ou les millisecondes si besoin)
                                    dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                                    ts_unix = int(dt.timestamp())
                                    
                                    all_rows.append([
                                        ts_unix, source['type'], nom, val, total, lat, lon
                                    ])
                                except ValueError:
                                    continue
                                    
                except Exception as e_item:
                    # Si un parking plante, on continue aux autres
                    continue
                    
        except Exception as e:
            print(f"❌ Erreur globale sur {source['type']} : {e}")

    # 3. Sauvegarde CSV
    print(f"\n💾 Écriture de {len(all_rows)} mesures historiques...")
    os.makedirs("data", exist_ok=True)
    
    with open(FICHIER, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["timestamp", "type", "parking", "places_libres", "capacite_totale", "lat", "lon"])
        writer.writerows(all_rows)
    
    print("✅ Terminé ! Le fichier contient maintenant de vraies données.")

if __name__ == "__main__":
    get_history()