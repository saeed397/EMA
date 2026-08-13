"""Market data: symbol universe by market-cap-proxy rank + OHLCV with fallback."""
import time
import ccxt
import pandas as pd
import streamlit as st

STABLES = {"USDT", "USDC", "BUSD", "FDUSD", "TUSD", "DAI", "USDE", "USDD", "PYUSD", "EURI", "EUR", "TRY", "BRL"}


def get_exchange(name):
    return getattr(ccxt, name)({"enableRateLimit": True, "timeout": 20000})


@st.cache_data(ttl=900, show_spinner=False)
def rank_universe(exchange_names, quote="USDT", max_n=500):
    """Rank spot symbols by 24h quote volume (liquid proxy for market-cap rank)."""
    last_err = None
    for name in exchange_names:
        try:
            ex = get_exchange(name)
            ex.load_markets()
            tickers = ex.fetch_tickers()
            rows = []
            for sym, t in tickers.items():
                m = ex.markets.get(sym)
                if not m or not m.get("spot") or not m.get("active"):
                    continue
                if m.get("quote") != quote or m.get("base") in STABLES:
                    continue
                qv = t.get("quoteVolume") or 0
                if not qv:
                    continue
                rows.append({"symbol": sym, "base": m["base"], "quote_volume": float(qv),
                             "last": t.get("last"), "change": t.get("percentage")})
            df = pd.DataFrame(rows).sort_values("quote_volume", ascending=False).head(max_n).reset_index(drop=True)
            df.insert(0, "rank", df.index + 1)
            return name, df
        except Exception as e:  # try next exchange
            last_err = e
            continue
    raise RuntimeError(f"No exchange reachable: {last_err}")


@st.cache_data(ttl=300, show_spinner=False)
def fetch_ohlcv(exchange_names, symbol, timeframe, limit=400):
    last_err = None
    for name in exchange_names:
        try:
            ex = get_exchange(name)
            raw = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if not raw or len(raw) < 120:
                raise ValueError("not enough candles")
            df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
            df["ts"] = pd.to_datetime(df["ts"], unit="ms")
            return df.set_index("ts")
        except Exception as e:
            last_err = e
            time.sleep(0.2)
            continue
    raise RuntimeError(f"{symbol}: {last_err}")
