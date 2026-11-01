"""
Statistical metrics and confidence interval computation for research hypotheses.
Implements Wilson Score 95% confidence intervals and logistic regression for BVR.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class WilsonCI:
    proportion: float
    ci_lower: float
    ci_upper: float
    count: int
    total: int

    def __str__(self) -> str:
        return f"{self.proportion * 100:.1f}% [95% CI: {self.ci_lower * 100:.1f}% – {self.ci_upper * 100:.1f}%] (n={self.total})"


def compute_wilson_ci(k: int, n: int, confidence: float = 0.95) -> WilsonCI:
    """
    Computes Wilson score interval for binomial proportion k/n.
    Accurately handles small sample sizes and boundary probabilities (0% and 100%).
    """
    if n <= 0:
        return WilsonCI(proportion=0.0, ci_lower=0.0, ci_upper=0.0, count=0, total=0)

    p_hat = k / n
    # z for 95% confidence = 1.959963984540054
    z = 1.95996 if confidence == 0.95 else 1.64485 if confidence == 0.90 else 2.57583

    denominator = 1 + (z**2) / n
    center = (p_hat + (z**2) / (2 * n)) / denominator
    margin = (z / denominator) * math.sqrt((p_hat * (1 - p_hat) / n) + ((z**2) / (4 * (n**2))))

    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)

    return WilsonCI(
        proportion=round(p_hat, 4),
        ci_lower=round(lower, 4),
        ci_upper=round(upper, 4),
        count=k,
        total=n,
    )


@dataclass
class LogisticRegressionResult:
    intercept: float
    coef_depth: float
    coef_lag: float
    converged: bool
    iterations: int

    def odds_ratio_depth(self) -> float:
        return math.exp(self.coef_depth)

    def odds_ratio_lag(self) -> float:
        return math.exp(self.coef_lag)


def fit_bvr_logistic_regression(
    samples: List[Tuple[int, int, bool]], max_iter: int = 1000, lr: float = 0.05, tol: float = 1e-3
) -> Optional[LogisticRegressionResult]:
    """
    Fits logistic regression: P(Violation) = sigma(beta_0 + beta_depth * depth + beta_lag * lag).
    sample format: (turn_depth, instruction_lag, violated: bool).
    Pure-standard library gradient ascent implementation (zero numpy/scipy dependency).
    """
    if not samples or len(samples) < 5:
        return None

    # Check if all outcomes are identical
    outcomes = [1.0 if s[2] else 0.0 for s in samples]
    if len(set(outcomes)) == 1:
        # Degenerate case (e.g. perfect 0% or 100% violations)
        return LogisticRegressionResult(
            intercept=-10.0 if outcomes[0] == 0.0 else 10.0,
            coef_depth=0.0,
            coef_lag=0.0,
            converged=True,
            iterations=0,
        )

    # Weights: w0 (intercept), w1 (depth), w2 (lag)
    w0, w1, w2 = 0.0, 0.0, 0.0
    n = float(len(samples))

    for it in range(max_iter):
        grad0, grad1, grad2 = 0.0, 0.0, 0.0
        for depth, lag, y_bool in samples:
            y = 1.0 if y_bool else 0.0
            z = w0 + (w1 * depth) + (w2 * lag)
            # Clip z to avoid overflow in exp
            z_clipped = max(-20.0, min(20.0, z))
            p = 1.0 / (1.0 + math.exp(-z_clipped))
            error = y - p
            grad0 += error
            grad1 += error * depth
            grad2 += error * lag

        grad0 /= n
        grad1 /= n
        grad2 /= n

        # Check convergence
        if abs(grad0) < tol and abs(grad1) < tol and abs(grad2) < tol:
            return LogisticRegressionResult(
                intercept=round(w0, 4),
                coef_depth=round(w1, 4),
                coef_lag=round(w2, 4),
                converged=True,
                iterations=it,
            )

        w0 += lr * grad0
        w1 += lr * grad1
        w2 += lr * grad2

    return LogisticRegressionResult(
        intercept=round(w0, 4),
        coef_depth=round(w1, 4),
        coef_lag=round(w2, 4),
        converged=True,
        iterations=max_iter,
    )
