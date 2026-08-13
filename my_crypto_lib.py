"""Technical indicators (pure pandas/numpy, no TA-Lib needed)."""
import numpy as np
import pandas as pd


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def rsi(close, n=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def stoch_rsi(close, n=14, k=3):
    r = rsi(close, n)
    lo = r.rolling(n).min()
    hi = r.rolling(n).max()
    sr = ((r - lo) / (hi - lo).replace(0, np.nan)) * 100
    return sr.rolling(k).mean().fillna(50)


def macd(close, fast=12, slow=26, signal=9):
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return line, sig, line - sig


def true_range(df):
    pc = df["close"].shift()
    return pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)


def atr(df, n=14):
    return true_range(df).ewm(alpha=1 / n, adjust=False).mean()


def adx(df, n=14):
    up = df["high"].diff()
    dn = -df["low"].diff()
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = true_range(df).ewm(alpha=1 / n, adjust=False).mean()
    pdi = 100 * pd.Series(plus, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / tr.replace(0, np.nan)
    mdi = 100 * pd.Series(minus, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / tr.replace(0, np.nan)
    dx = ((pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)) * 100
    return dx.ewm(alpha=1 / n, adjust=False).mean().fillna(0), pdi.fillna(0), mdi.fillna(0)


def bollinger(close, n=20, k=2.0):
    ma = close.rolling(n).mean()
    sd = close.rolling(n).std()
    return ma + k * sd, ma, ma - k * sd


def ichimoku(df, t=9, k=26, s=52):
    conv = (df["high"].rolling(t).max() + df["low"].rolling(t).min()) / 2
    base = (df["high"].rolling(k).max() + df["low"].rolling(k).min()) / 2
    span_a = ((conv + base) / 2).shift(k)
    span_b = ((df["high"].rolling(s).max() + df["low"].rolling(s).min()) / 2).shift(k)
    return conv, base, span_a, span_b


def enrich(df, cfg):
    out = df.copy()
    for n in (20, 50, 100, 200):
        out[f"ema{n}"] = ema(out["close"], n)
    out["rsi"] = rsi(out["close"])
    out["srsi"] = stoch_rsi(out["close"])
    out["macd"], out["macd_sig"], out["macd_hist"] = macd(out["close"])
    out["atr"] = atr(out, cfg.get("atr_period", 14))
    out["adx"], out["pdi"], out["mdi"] = adx(out)
    out["bb_up"], out["bb_mid"], out["bb_dn"] = bollinger(out["close"])
    out["conv"], out["base"], out["span_a"], out["span_b"] = ichimoku(out)
    out["vol_ma"] = out["volume"].rolling(20).mean()
    out["vol_ratio"] = out["volume"] / out["vol_ma"].replace(0, np.nan)
    return out
