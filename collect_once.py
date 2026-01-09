import requests
import time
import os
import csv

# Configuration des deux API (Voitures et Vélos)
URLS = [
    {
        "type": "Voiture",
        "url": "https://portail-api-data.montpellier3m.fr/offstreetparking?limit=1000",
        "key_free": "availableSpotNumber",   # Clé JSON pour places libres
        "key_total": "totalSpotNumber"       # Clé JSON pour capacité totale
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
    
    # Création du dossier data s'il n'existe pas
    os.makedirs("data", exist_ok=True)
    
    lignes_a_ecrire = []

    for source in URLS:
        try:
            print(f"Connexion à l'API {source['type']}...")
            response = requests.get(source['url'], timeout=10)
            response.raise_for_status()
            data = response.json()
            
            for item in data:
                # 1. Extraction du NOM (Gestion des cas particuliers)
                nom = item.get("name", {}).get("value")
                if not nom:
                    # Pour certains vélos, le nom est dans l'adresse
                    addr_val = item.get("address", {}).get("value")
                    if isinstance(addr_val, dict):
                        nom = addr_val.get("streetAddress", "Inconnu")
                    else:
                        nom = str(addr_val)
                
                # Nettoyage : on enlève les points-virgules qui casseraient le CSV
                nom = str(nom).replace(";", ",").strip()

                # 2. Extraction des PLACES (Libres et Totales)
                free_obj = item.get(source['key_free'], {})
                places_libres = free_obj.get("value")

                total_obj = item.get(source['key_total'], {})
                capacite_totale = total_obj.get("value")

                # 3. Extraction GPS (Latitude / Longitude)
                coords = item.get("location", {}).get("value", {}).get("coordinates", [None, None])
                lon, lat = coords[0], coords[1]

                # 4. Validation : On ne garde que si on a toutes les infos
                if nom and places_libres is not None and capacite_totale is not None:
                    lignes_a_ecrire.append([
                        timestamp, 
                        source['type'], 
                        nom, 
                        places_libres, 
                        capacite_totale, 
                        lat, 
                        lon
                    ])
                    
        except Exception as e:
            print(f"Erreur sur l'API {source['type']} : {e}")

    # Écriture dans le fichier CSV
    file_exists = os.path.exists(FICHIER)
    
    with open(FICHIER, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        
        # Si le fichier est nouveau, on écrit l'en-tête complet
        if not file_exists:
            writer.writerow(["timestamp", "type", "parking", "places_libres", "capacite_totale", "lat", "lon"])
            
        writer.writerows(lignes_a_ecrire)
        print(f"Succès : {len(lignes_a_ecrire)} lignes ajoutées au CSV.")

if __name__ == "__main__":
    collecter()