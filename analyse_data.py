import csv
from parking_lib import moyenne

places = []

with open("data/suivi_global.csv", newline="") as f:
    reader = csv.DictReader(f, delimiter=";")
    for row in reader:
        places.append(int(row["places_libres"]))

print("Moyenne des places libres :", moyenne(places))
