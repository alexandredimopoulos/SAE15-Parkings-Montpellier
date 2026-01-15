"""Récupère les positions (lat/lon) des parkings Voiture et stations Vélo.

Le CSV historique fourni (Date/Heure/Type/Nom/...) ne contient pas les coordonnées.
Ce script fabrique un mapping stable Nom -> (lat, lon, id) dans data/locations.json
pour afficher la carte.

On essaie de joindre par nom *normalisé* (minuscule, accents retirés, espaces compressés).
"""

from __future__ import annotations

import json
import os
import re
import unicodedata

import requests

BASE_URL = "https://portail-api-data.montpellier3m.fr"
OUT_PATH = "data/locations.json"

SOURCES = [
    {
        "type": "Voiture",
        "url": f"{BASE_URL}/offstreetparking?limit=1000",
    },
    {
        "type": "Velo",
        "url": f"{BASE_URL}/bikestation?limit=1000",
    },
]


def norm_name(s: str) -> str:
    s = s.strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")  # enlève accents
    s = re.sub(r"\s+", " ", s)
    return s


def safe_name(item: dict) -> str:
    name = item.get("name", {}).get("value")
    if not name:
        addr_val = item.get("address", {}).get("value")
        if isinstance(addr_val, dict):
            name = addr_val.get("streetAddress", "Inconnu")
        else:
            name = str(addr_val) if addr_val is not None else "Inconnu"
    return str(name).replace(";", ",").strip()


def sync_locations() -> dict:
    os.makedirs("data", exist_ok=True)

    out: dict = {"Voiture": {}, "Velo": {}}

    for src in SOURCES:
        t = src["type"]
        try:
            resp = requests.get(src["url"], timeout=20)
            resp.raise_for_status()
            items = resp.json()
        except Exception as e:
            print(f"Erreur liste {t}: {e}")
            continue

        for item in items:
            try:
                name = safe_name(item)
                n = norm_name(name)
                item_id = item.get("id")
                coords = item.get("location", {}).get("value", {}).get("coordinates", [None, None])
                lon, lat = None, None
                if isinstance(coords, list) and len(coords) >= 2:
                    lon, lat = coords[0], coords[1]

                if lat is None or lon is None:
                    continue

                out[t][n] = {
                    "name": name,
                    "id": item_id,
                    "lat": float(lat),
                    "lon": float(lon),
                }
            except Exception:
                continue

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"OK: locations sauvegardées -> {OUT_PATH}")
    return out


if __name__ == "__main__":
    sync_locations()
