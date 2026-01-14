import math

# --- STATISTIQUES DE BASE ---

def moyenne(l):
    """Calcule la moyenne d'une liste."""
    return sum(l) / len(l) if len(l) > 0 else 0

def variance(l):
    """Calcule la variance (dispersion) d'une liste."""
    if len(l) < 2: return 0
    m = moyenne(l)
    return sum((x - m) ** 2 for x in l) / len(l)

def ecart_type(l):
    """Calcule l'écart-type (racine carrée de la variance)."""
    return math.sqrt(variance(l))

def covariance(l1, l2):
    """Calcule la covariance entre deux listes de même taille."""
    if len(l1) != len(l2) or len(l1) == 0: return 0
    m1, m2 = moyenne(l1), moyenne(l2)
    return sum((x - m1) * (y - m2) for x, y in zip(l1, l2)) / len(l1)

def correlation(l1, l2):
    """Calcule le coefficient de corrélation de Pearson (entre -1 et 1)."""
    st1, st2 = ecart_type(l1), ecart_type(l2)
    if st1 == 0 or st2 == 0: return 0
    return covariance(l1, l2) / (st1 * st2)

# --- GÉOGRAPHIE ---

def distance_gps(lat1, lon1, lat2, lon2):
    """
    Calcule la distance en km entre deux points GPS 
    (Formule de Haversine).
    """
    R = 6371  # Rayon de la Terre en km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) * math.sin(dlat / 2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dlon / 2) * math.sin(dlon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c