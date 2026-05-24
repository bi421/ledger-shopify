# src/measurement/wilson.py
import math
from typing import Tuple

def wilson_score_interval(successes: int, trials: int, z: float = 1.96) -> Tuple[float, float]:
    """
    Binomial proportion confidence interval (Wilson score).
    Pure mathematical function. No side effects.
    """
    if trials <= 0:
        return 0.0, 1.0
    
    # Edge case protection: Meta API sometimes returns glitchy data (e.g., saves > views)
    successes = max(0, min(successes, trials))
    
    p_hat = successes / trials
    denominator = 1 + z**2 / trials
    centre = (p_hat + z**2 / (2 * trials)) / denominator
    spread = z * math.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * trials)) / trials) / denominator
    
    return max(0.0, centre - spread), min(1.0, centre + spread)