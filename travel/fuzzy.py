
from __future__ import annotations

from dataclasses import dataclass

import numpy as np



def trimf(x, a, b, c):
    """Triangular membership: 0 at a and c, 1 at b."""
    x = np.asarray(x, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        left = np.where(b > a, (x - a) / (b - a), np.where(x >= b, 1.0, 0.0))
        right = np.where(c > b, (c - x) / (c - b), np.where(x <= b, 1.0, 0.0))
    return np.clip(np.minimum(left, right), 0.0, 1.0)


def trapmf(x, a, b, c, d):
    """Trapezoidal membership (used for shoulders); a<=b<=c<=d."""
    x = np.asarray(x, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        left = np.where(b > a, (x - a) / (b - a), 1.0)
        right = np.where(d > c, (d - x) / (d - c), 1.0)
    return np.clip(np.minimum(np.minimum(left, right), 1.0), 0.0, 1.0)



def aff_cheap(r):     return trapmf(r, -1, -1, 0.5, 0.9)
def aff_moderate(r):  return trimf(r, 0.6, 0.95, 1.3)
def aff_expensive(r): return trapmf(r, 1.0, 1.5, 5, 5)

def rate_low(s):      return trapmf(s, 0, 0, 2.0, 3.0)
def rate_medium(s):   return trimf(s, 2.5, 3.25, 4.0)
def rate_high(s):     return trapmf(s, 3.5, 4.5, 5, 5)


_GRID = np.linspace(0, 100, 101)
def out_poor(z):      return trapmf(z, 0, 0, 20, 45)
def out_average(z):   return trimf(z, 35, 55, 80)
def out_good(z):      return trapmf(z, 65, 85, 100, 100)


_RULES = [
    (aff_cheap, rate_high, out_good),
    (aff_cheap, rate_medium, out_good),
    (aff_cheap, rate_low, out_average),
    (aff_moderate, rate_high, out_good),
    (aff_moderate, rate_medium, out_average),
    (aff_moderate, rate_low, out_poor),
    (aff_expensive, rate_high, out_average),
    (aff_expensive, rate_medium, out_poor),
    (aff_expensive, rate_low, out_poor),
]


@dataclass
class HotelScore:
    hotel: object
    score: float


def infer(price: float, budget: float, rating: float) -> float:

    r = price / budget if budget else 2.0
    aggregated = np.zeros_like(_GRID)
    for aff_fn, rate_fn, out_fn in _RULES:
        strength = min(float(aff_fn(r)), float(rate_fn(rating)))  
        if strength > 0:
            clipped = np.minimum(strength, out_fn(_GRID))          
            aggregated = np.maximum(aggregated, clipped)           
    denom = aggregated.sum()
    if denom == 0:
        return 0.0
    return float((_GRID * aggregated).sum() / denom)               


def recommend_hotels(hotels, budget_per_night: float, top_n: int | None = None):

    scored = [
        HotelScore(h, round(infer(h.price_npr, budget_per_night, h.star_rating), 1))
        for h in hotels
    ]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:top_n] if top_n else scored
