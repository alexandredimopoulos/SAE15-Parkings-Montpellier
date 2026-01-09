import requests
import time
import os
import csv

# On définit les deux sources de données
URLS = [
    {
        "type": "Voiture",
        "url": "https://portail-api-data.montpellier3m.fr/offstreetparking?limit=1000",
        "key_places": "availableSpotNumber"  # Nom du champ JSON pour les voitures
    },
    {
        "type": "Velo",
        "url": "https://portail-api-data.montpellier3m.fr/bikestation?limit=1000",
        "key_places": "availableBikeNumber"  # Nom du champ JSON pour les vélos
    }
]

FICHIER = "data/suivi_global.csv"

def collecter():
    timestamp = int(time.time())
    os.makedirs("data", exist_ok=True)
    
    # On prépare la liste des nouvelles données
    lignes_a_ecrire = []

    for source in URLS:
        try:
            print(f"Récupération des données {source['type']}...")
            response = requests.get(source['url'], timeout=10)
            response.raise_for_status()
            data = response.json()
            
            for item in data:
                # 1. Récupération du nom (gestion des structures différentes)
                nom = item.get("name", {}).get("value") # Structure standard
                if not nom:
                    # Parfois l'adresse est directement à la racine pour certains flux
                    nom = item.get("address", {}).get("value")

                # 2. Récupération des places (clé dynamique selon vélo ou voiture)
                places_obj = item.get(source['key_places'], {})
                places = places_obj.get("value")

                # 3. Validation et Ajout
                if nom is not None and places is not None:
                    # On ajoute le champ "type" à la ligne
                    lignes_a_ecrire.append([timestamp, source['type'], nom, places])
                    
        except Exception as e:
            print(f"Erreur sur l'API {source['type']} : {e}")

    # Écriture dans le CSV
    file_exists = os.path.exists(FICHIER)
    
    # Mode 'a' pour append (ajouter à la fin)
    with open(FICHIER, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        
        # Si le fichier est nouveau, on écrit l'en-tête AVEC la colonne 'type'
        if not file_exists:
            writer.writerow(["timestamp", "type", "parking", "places_libres"])
            
        writer.writerows(lignes_a_ecrire)
        print(f"{len(lignes_a_ecrire)} mesures ajoutées.")

if __name__ == "__main__":
    collecter()