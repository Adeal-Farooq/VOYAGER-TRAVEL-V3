"""TOPSIS multi-criteria scoring — moved from ml/topsis.py."""

import numpy as np
import pandas as pd


class TOPSIS:
    def __init__(self):
        self.criteria_weights = {
            "cost": 0.25,
            "time": 0.20,
            "comfort": 0.15,
            "safety": 0.15,
            "walking_distance": 0.10,
            "availability": 0.10,
            "weather_impact": 0.05
        }

    def set_weights(self, weights: dict):
        self.criteria_weights.update(weights)

    def evaluate(self, alternatives: list[dict]) -> list[dict]:
        if not alternatives:
            return []

        criteria = list(self.criteria_weights.keys())
        weights = np.array([self.criteria_weights[c] for c in criteria])

        matrix = []
        for alt in alternatives:
            row = [
                alt.get("fare", alt.get("total_fare", 0)),
                alt.get("duration_minutes", alt.get("total_duration_minutes", 0)),
                -alt.get("comfort", 3),
                -alt.get("safety", 3),
                alt.get("walking_km", alt.get("total_walking_km", 0)),
                -alt.get("availability", alt.get("overall_score", 50)),
                alt.get("weather_impact", 0)
            ]
            matrix.append(row)

        matrix = np.array(matrix, dtype=float)

        denom = np.sqrt(np.sum(matrix ** 2, axis=0))
        denom[denom == 0] = 1e-10
        norm_matrix = matrix / denom

        weighted_matrix = norm_matrix * weights

        ideal_best = np.min(weighted_matrix, axis=0)
        ideal_worst = np.max(weighted_matrix, axis=0)

        dist_best = np.sqrt(np.sum((weighted_matrix - ideal_best) ** 2, axis=1))
        dist_worst = np.sqrt(np.sum((weighted_matrix - ideal_worst) ** 2, axis=1))

        denom = dist_best + dist_worst
        denom[denom == 0] = 1e-10
        scores = dist_worst / denom

        for i, alt in enumerate(alternatives):
            alt["topsis_score"] = round(float(scores[i]), 4)

        sorted_alts = sorted(alternatives, key=lambda x: x["topsis_score"], reverse=True)
        for i, alt in enumerate(sorted_alts):
            alt["rank"] = i + 1

        return sorted_alts


topsis = TOPSIS()
