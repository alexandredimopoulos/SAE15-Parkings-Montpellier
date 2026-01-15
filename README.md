# SAE15 — Parkings Montpellier (Dashboard)

Ce dépôt génère un **site statique** (un `index.html`) qui affiche :
- un comparatif **Voiture vs Vélo** (occupation moyenne par heure)
- une **stabilité** (parking voiture le plus stable / le plus instable sur les dernières 24h)
- une **carte** (coordonnées récupérées via l'API)
- un **historique interactif** (clic sur carte ou barres)
- des **classements** (occupation actuelle)

Le tout est compatible avec le format CSV Excel :
`Date;Heure;Type;Nom;Places_Libres;Places_Totales`

---

## 1) Installer les dépendances (local)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 2) Générer / mettre à jour les coordonnées (carte)

```bash
python sync_locations.py
```
Cela crée `data/locations.json`.

---

## 3) Générer le site

```bash
python generate_site.py
```
Tu obtiens `index.html` (ouvre-le dans ton navigateur).

---

## 4) Collecter une mesure (optionnel)

```bash
python collect_once.py
python sync_locations.py
python generate_site.py
```

---

## 5) Automatisation GitHub Actions

- `.github/workflows/collect.yml` : collecte toutes les 20 minutes + rebuild du site
- `.github/workflows/init_data.yml` : rebuild manuel (si tu veux juste régénérer)

Pour GitHub Pages :
- soit tu sers `index.html` depuis la racine
- soit tu peux déplacer vers `/docs` (option non activée ici)

