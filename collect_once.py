"""Collecte une mesure instantanée (Voiture + Vélo) et l'ajoute à data/suivi_global.csv.

Format CSV (délimiteur ;) :
Date;Heure;Type;Nom;Places_Libres;Places_Totales

- Date au format YYYY-MM-DD
- Heure au format HH:MM (heure locale France)

Ce format correspond à ton fichier suivi_global.csv actuel.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime

import requests

BASE_URL = "https://portail-api-data.montpellier3m.fr"
CSV_PATH = "data/suivi_global.csv"

SOURCES = [
    {
        "type": "Voiture",
        "url": f"{BASE_URL}/offstreetparking?limit=1000",
        "key_free": "availableSpotNumber",
        "key_total": "totalSpotNumber",
    },
    {
        "type": "Velo",
        "url": f"{BASE_URL}/bikestation?limit=1000",
        "key_free": "availableBikeNumber",
        "key_total": "totalSlotNumber",
    },
]


def _safe_name(item: dict) -> str:
    name = item.get("name", {}).get("value")
    if not name:
        addr_val = item.get("address", {}).get("value")
        if isinstance(addr_val, dict):
            name = addr_val.get("streetAddress", "Inconnu")
        else:
            name = str(addr_val) if addr_val is not None else "Inconnu"
    # éviter de casser le CSV
    return str(name).replace(";", ",").strip()


def collect_once() -> int:
    os.makedirs("data", exist_ok=True)

    now = datetime.now()  # heure locale machine/runner
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")

    rows: list[list[object]] = []

    for src in SOURCES:
        try:
            resp = requests.get(src["url"], timeout=15)
            resp.raise_for_status()
            items = resp.json()

            for item in items:
                name = _safe_name(item)

                free = item.get(src["key_free"], {}).get("value")
                total = item.get(src["key_total"], {}).get("value")

                if free is None or total is None:
                    continue

                try:
                    free_i = int(free)
                    total_i = int(total)
                except Exception:
                    continue

                if total_i <= 0:
                    continue

                # sécurité: certains capteurs peuvent dépasser le total
                if free_i > total_i:
                    free_i = total_i
                if free_i < 0:
                    free_i = 0

                rows.append([date_str, time_str, src["type"], name, free_i, total_i])

        except Exception as e:
            print(f"Erreur API {src['type']}: {e}")

    file_exists = os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        if not file_exists:
            writer.writerow(["Date", "Heure", "Type", "Nom", "Places_Libres", "Places_Totales"])
        writer.writerows(rows)

    print(f"OK: {len(rows)} lignes ajoutées dans {CSV_PATH}")
    return len(rows)


if __name__ == "__main__":
    collect_once()
