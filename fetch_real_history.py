import requests
import csv
import os
import time
from datetime import datetime, timedelta

# Configuration
DAYS_BACK = 7
FICHIER = "data/suivi_global.csv"
BASE_URL = "https://portail-api-data.montpellier3m.fr"

SOURCES = [
    {
        "type": "Velo", # On commence par les vélos
        "list_url": f"{BASE_URL}/bikestation?limit=1000",
        "history_path": "/bikestation_timeseries/{id}/attrs/availableBikeNumber",
        "key_total": "totalSlotNumber"
    },
    {
        "type": "Voiture",
        "list_url": f"{BASE_URL}/offstreetparking?limit=1000",
        "history_path": "/parking_timeseries/{id}/attrs/availableSpotNumber",
        "key_total": "totalSpotNumber"
    }
]

def get_real_history_sampled():
    print("🌍 Démarrage récupération VRAIES DONNÉES (1 point/heure)...")
    
    start_date = (datetime.now() - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%dT%H:%M:%S")
    all_rows = []

    for source in SOURCES:
        print(f"\n📡 Source : {source['type']}...")
        try:
            resp = requests.get(source['list_url'], timeout=10)
            items = resp.json()
            print(f"   {len(items)} stations trouvées.")

            for index, item in enumerate(items):
                try:
                    item_id = item.get("id")
                    
                    # Récupération Nom
                    nom = item.get("name", {}).get("value")
                    if not nom:
                        addr = item.get("address", {}).get("value")
                        nom = addr.get("streetAddress", str(addr)) if isinstance(addr, dict) else str(addr)
                    nom = str(nom).replace(";", ",").strip()

                    # Récupération Info
                    total = item.get(source['key_total'], {}).get("value", 0)
                    coords = item.get("location", {}).get("value", {}).get("coordinates", [None, None])
                    lon, lat = coords[0], coords[1]

                    if not item_id or not total: continue

                    # Appel API Historique
                    hist_url = f"{BASE_URL}{source['history_path'].format(id=item_id)}"
                    params = {"fromDate": start_date}
                    
                    # On tente 3 fois en cas d'erreur
                    for attempt in range(3):
                        try:
                            h_resp = requests.get(hist_url, params=params, timeout=10)
                            if h_resp.status_code == 200:
                                h_data = h_resp.json()
                                timestamps = h_data.get("index", [])
                                values = h_data.get("values", [])
                                
                                # FILTRAGE INTELLIGENT : On ne garde qu'un point par heure
                                # Cela évite le fichier de 30Mo tout en gardant la vérité
                                last_saved_hour = -1
                                
                                for i in range(len(timestamps)):
                                    ts_str = timestamps[i]
                                    val = values[i]
                                    
                                    try:
                                        # Conversion date
                                        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                                        
                                        # On ne garde que si l'heure a changé depuis la dernière sauvegarde
                                        # ou si c'est la toute dernière donnée (pour le temps réel)
                                        current_hour = dt.day * 24 + dt.hour
                                        if current_hour != last_saved_hour or i == len(timestamps) - 1:
                                            
                                            ts_unix = int(dt.timestamp())
                                            places_libres = int(val)
                                            if places_libres > total: places_libres = total # Correction bug capteur
                                            
                                            all_rows.append([ts_unix, source['type'], nom, places_libres, total, lat, lon])
                                            last_saved_hour = current_hour
                                            
                                    except: continue
                                
                                print(f"   [{index+1}/{len(items)}] {nom[:15]}... OK")
                                break # Succès, on sort de la boucle retry
                            
                            elif h_resp.status_code == 429:
                                print("⏳ Pause API (Rate Limit)...")
                                time.sleep(10)
                            else:
                                break
                                
                        except Exception as e:
                            time.sleep(2)
                    
                    time.sleep(0.5) # Petite pause pour ménager l'API

                except Exception: continue

        except Exception as e:
            print(f"Erreur liste : {e}")

    # Sauvegarde CSV
    print(f"\n💾 Sauvegarde de {len(all_rows)} points réels...")
    os.makedirs("data", exist_ok=True)
    with open(FICHIER, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["timestamp", "type", "parking", "places_libres", "capacite_totale", "lat", "lon"])
        writer.writerows(all_rows)
    print("✅ Terminé.")

if __name__ == "__main__":
    get_real_history_sampled()