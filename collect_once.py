import requests
import time
import os
import csv

URLS = [
    {
        "type": "Voiture",
        "url": "https://portail-api-data.montpellier3m.fr/offstreetparking?limit=1000",
        "key_free": "availableSpotNumber",
        "key_total": "totalSpotNumber"
    },
    {
        "type": "Velo",
        "url": "https://portail-api-data.montpellier3m.fr/bikestation?limit=1000",
        "key_free": "availableBikeNumber",
        "key_total": "totalSlotNumber"
    }
]

FICHIER = "data/suivi_global.csv"

def collecter():
    timestamp = int(time.time())
    os.makedirs("data", exist_ok=True)
    
    lignes_a_ecrire = []

    for source in URLS:
        try:
            response = requests.get(source['url'], timeout=10)
            response.raise_for_status()
            data = response.json()
            
            for item in data:
                # 1. Nom
                nom = item.get("name", {}).get("value")
                if not nom:
                    addr_val = item.get("address", {}).get("value")
                    nom = addr_val.get("streetAddress", "Inconnu") if isinstance(addr_val, dict) else str(addr_val)
                nom = str(nom).replace(";", ",").strip()

                # 2. Places Libres
                free_obj = item.get(source['key_free'], {})
                places_libres = free_obj.get("value")

                # 3. Capacité Totale (NOUVEAU)
                total_obj = item.get(source['key_total'], {})
                capacite_totale = total_obj.get("value")

                # 4. GPS
                coords = item.get("location", {}).get("value", {}).get("coordinates", [None, None])
                lon, lat = coords[0], coords[1]

                # On vérifie qu'on a bien les chiffres
                if nom and places_libres is not None and capacite_totale is not None:
                    lignes_a_ecrire.append([timestamp, source['type'], nom, places_libres, capacite_totale, lat, lon])
                    
        except Exception as e:
            print(f"Erreur sur l'API {source['type']} : {e}")

    # Écriture CSV
    file_exists = os.path.exists(FICHIER)
    
    with open(FICHIER, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        
        # En-tête mis à jour avec 'capacite_totale'
        if not file_exists:
            writer.writerow(["timestamp", "type", "parking", "places_libres", "capacite_totale", "lat", "lon"])
            
        writer.writerows(lignes_a_ecrire)
        print(f"{len(lignes_a_ecrire)} mesures ajoutées.")

if __name__ == "__main__":
    collecter()