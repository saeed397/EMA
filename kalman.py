"""Kalman filter smoothing + derivative (slope) estimation for price series."""
import numpy as np
import pandas as pd


def kalman_level_trend(series, q: float = 1e-4, r: float = 1e-2):
    """Local-linear-trend Kalman filter.

    Returns (level, slope) as pandas Series. `slope` is a smooth derivative
    estimate (change per candle), far less noisy than a raw diff().
    """
    z = pd.Series(series).astype(float).values
    n = len(z)
    level = np.zeros(n)
    slope = np.zeros(n)
    if n == 0:
        return pd.Series(level), pd.Series(slope)

    A = np.array([[1.0, 1.0], [0.0, 1.0]])
    H = np.array([[1.0, 0.0]])
    Q = np.array([[q, 0.0], [0.0, q]])
    R = np.array([[r]])

    x = np.array([[z[0]], [0.0]])
    P = np.eye(2)

    for i in range(n):
        x = A @ x
        P = A @ P @ A.T + Q
        y = np.array([[z[i]]]) - H @ x
        S = H @ P @ H.T + R
        K = P @ H.T @ np.linalg.inv(S)
        x = x + K @ y
        P = (np.eye(2) - K @ H) @ P
        level[i] = x[0, 0]
        slope[i] = x[1, 0]

    idx = pd.Series(series).index
    return pd.Series(level, index=idx), pd.Series(slope, index=idx)


def normalized_kalman_slope(close, q=1e-4, r=1e-2, lookback=100):
    """Slope normalized by price -> percent per candle, then mapped to 0..100."""
    level, slope = kalman_level_trend(close, q, r)
    pct = (slope / level.replace(0, np.nan)) * 100.0
    ref = pct.abs().rolling(lookback, min_periods=10).quantile(0.9)
    scaled = (pct / ref.replace(0, np.nan)).clip(-1, 1)
    score = (scaled + 1) * 50.0
    return level, pct, score.fillna(50.0)
