import math

def moyenne(l):
    return sum(l) / len(l) if len(l) > 0 else None

def variance(l):
    m = moyenne(l)
    return sum((x - m) ** 2 for x in l) / len(l)

def ecart_type(l):
    return math.sqrt(variance(l))

def covariance(l1, l2):
    m1, m2 = moyenne(l1), moyenne(l2)
    return sum((x - m1) * (y - m2) for x, y in zip(l1, l2)) / len(l1)

def correlation(l1, l2):
    return covariance(l1, l2) / (ecart_type(l1) * ecart_type(l2))
