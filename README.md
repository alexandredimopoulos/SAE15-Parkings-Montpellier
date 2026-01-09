# SAE15 – Analyse des parkings de Montpellier

## Objectif
Ce projet a pour but de collecter, sauvegarder, analyser et visualiser les données
d’occupation des parkings de Montpellier à partir de l’API Open Data officielle.

La collecte est automatisée grâce à GitHub Actions.

---

## Fonctionnement

- Une action GitHub s’exécute toutes les 10 minutes
- Une requête HTTP est envoyée à l’API
- Les données sont ajoutées dans un fichier CSV horodaté
- Le dépôt conserve l’historique complet

---

## Structure du projet

- `collect_once.py` : collecte une mesure
- `parking_lib.py` : librairie de fonctions statistiques
- `analyse_data.py` : analyse des données collectées
- `.github/workflows/collect.yml` : automatisation
- `data/suivi_global.csv` : base de données

---

## Choix techniques

- Une seule requête par exécution (respect de l’API)
- Horodatage UNIX
- Données exploitables dans Excel / Python / Jupyter
- Automatisation demandée explicitement dans le cadre de la SAE15

---

## Auteur
BUT Réseaux & Télécommunications – IUT de Béziers
