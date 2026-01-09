import requests
import time
import os

URL = "https://portail-api-data.montpellier3m.fr/offstreetparking?limit=1000"
FICHIER = "data/suivi_global.csv"

timestamp = int(time.time())

# Création du dossier data si nécessaire
os.makedirs("data", exist_ok=True)

response = requests.get(URL)
data = response.json()

# Création du fichier CSV avec en-tête
if not os.path.exists(FICHIER):
    with open(FICHIER, "w") as f:
        f.write("timestamp;parking;places_libres\n")

with open(FICHIER, "a") as f:
    for parking in data:
        nom = parking.get("name", {}).get("value")
        places = parking.get("availableSpotNumber", {}).get("value")

        if nom is not None and places is not None:
            f.write(f"{timestamp};{nom};{places}\n")
