import requests
import csv
import os
import time
from datetime import datetime, timedelta

# Configuration
DAYS_BACK = 7        # 1 semaine d'historique
DELAY_SECONDS = 1.0  # Pause réduite à 1 seconde pour aller plus vite
FICHIER = "data/suivi_global.csv"
BASE_URL = "https://portail-api-data.montpellier3m.fr"

SOURCES = [
    {
        "type": "Voiture",
        "list_url": f"{BASE_URL}/offstreetparking?limit=1000",
        "history_path": "/parking_timeseries/{id}/attrs/availableSpotNumber",
        "key_total": "totalSpotNumber"
    },
    {
        "type": "Velo",
        "list_url": f"{BASE_URL}/bikestation?limit=1000",
        "history_path": "/bikestation_timeseries/{id}/attrs/availableBikeNumber",
        "key_total": "totalSlotNumber"
    }
]

def get_real_history_optimized():
    print("⚡ Démarrage récupération VRAIES données (Optimisé 7 jours)...")
    
    start_date = (datetime.now() - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%dT%H:%M:%S")
    
    all_rows = []

    for source in SOURCES:
        print(f"\n📡 Liste : {source['type']}...")
        try:
            resp = requests.get(source['list_url'], timeout=10)
            items = resp.json()
            print(f"   {len(items)} stations. Traitement rapide...")

            for index, item in enumerate(items):
                try:
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

                    # Récupération Historique
                    hist_url = f"{BASE_URL}{source['history_path'].format(id=item_id)}"
                    params = {"fromDate": start_date}
                    
                    h_resp = requests.get(hist_url, params=params, timeout=5)
                    
                    if h_resp.status_code == 200:
                        h_data = h_resp.json()
                        timestamps = h_data.get("index", [])
                        values = h_data.get("values", [])
                        
                        if timestamps:
                            # On garde 1 point par heure
                            for i in range(0, len(timestamps), 1):
                                try:
                                    ts_str = timestamps[i]
                                    val = values[i]
                                    dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                                    ts_unix = int(dt.timestamp())
                                    
                                    places_libres = int(val)
                                    if places_libres > total: places_libres = total
                                    
                                    all_rows.append([ts_unix, source['type'], nom, places_libres, total, lat, lon])
                                except:
                                    continue
                            print(f"   [{index+1}/{len(items)}] {nom[:15]}... OK")
                        else:
                            print(f"   [{index+1}/{len(items)}] {nom[:15]}... Vide")
                    else:
                        print(f"   [{index+1}/{len(items)}] {nom[:15]}... Erreur API")

                    # Pause courte
                    time.sleep(DELAY_SECONDS)

                except Exception as e:
                    print(f"   Erreur item: {e}")
                    time.sleep(1)
                    continue

        except Exception as e_global:
            print(f"Erreur globale : {e_global}")

    # Sauvegarde
    print(f"\n💾 Écriture de {len(all_rows)} lignes...")
    os.makedirs("data", exist_ok=True)
    
    with open(FICHIER, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["timestamp", "type", "parking", "places_libres", "capacite_totale", "lat", "lon"])
        writer.writerows(all_rows)
    
    print("✅ Terminé !")

if __name__ == "__main__":
    get_real_history_optimized()