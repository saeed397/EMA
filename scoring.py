"""Weighted 0-100 scoring: 10 components in 4 blocks + HTF gate."""
import numpy as np
import pandas as pd
from my_crypto_lib import enrich
from kalman import normalized_kalman_slope

BLOCKS = {
    "trend": ["trend_ema_stack", "kalman_slope", "ichimoku_cloud", "adx_strength"],
    "momentum": ["rsi_position", "macd_hist", "stoch_rsi"],
    "volume": ["volume_ratio"],
    "structure": ["bb_position", "htf_alignment"],
}
LABELS = {
    "trend_ema_stack": "ترتیب EMA (20/50/100/200)",
    "kalman_slope": "شیب کالمن (مشتق هموار)",
    "ichimoku_cloud": "موقعیت ابر ایچیموکو",
    "adx_strength": "قدرت روند (ADX)",
    "rsi_position": "موقعیت RSI",
    "macd_hist": "هیستوگرام MACD",
    "stoch_rsi": "استوکاستیک RSI",
    "volume_ratio": "نسبت حجم",
    "bb_position": "موقعیت باند بولینگر",
    "htf_alignment": "هم‌راستایی تایم‌فریم بالاتر",
}


def _clip(x):
    return float(np.clip(x, 0, 100))


def htf_bias(df_htf, cfg):
    """Returns (bias, strength 0..100). bias in {'long','short','neutral'}"""
    d = enrich(df_htf, cfg)
    _, _, ks = normalized_kalman_slope(d["close"], cfg["kalman_q"], cfg["kalman_r"])
    last = d.iloc[-1]
    kslope = float(ks.iloc[-1])
    cloud_ok = pd.notna(last["span_a"]) and pd.notna(last["span_b"])
    up = int(last["close"] > last["ema200"]) + int(last["ema50"] > last["ema200"]) + int(kslope > 55) + int(
        cloud_ok and last["close"] > max(last["span_a"], last["span_b"]))
    dn = int(last["close"] < last["ema200"]) + int(last["ema50"] < last["ema200"]) + int(kslope < 45) + int(
        cloud_ok and last["close"] < min(last["span_a"], last["span_b"]))
    strength = _clip(50 + (up - dn) * 12.5)
    if up >= 3 and up > dn:
        return "long", strength
    if dn >= 3 and dn > up:
        return "short", strength
    return "neutral", strength


def component_scores(d, kslope_score, bias_strength, direction):
    last = d.iloc[-1]
    c = last["close"]
    s = {}

    order_up = [last["ema20"] > last["ema50"], last["ema50"] > last["ema100"], last["ema100"] > last["ema200"], c > last["ema20"]]
    stack = sum(bool(x) for x in order_up) / 4 * 100
    s["trend_ema_stack"] = _clip(stack)
    s["kalman_slope"] = _clip(kslope_score)

    if pd.notna(last["span_a"]) and pd.notna(last["span_b"]):
        top, bot = max(last["span_a"], last["span_b"]), min(last["span_a"], last["span_b"])
        if c > top:
            cl = 85 + min(15, (c - top) / top * 300)
        elif c < bot:
            cl = 15 - min(15, (bot - c) / bot * 300)
        else:
            cl = 50
    else:
        cl = 50
    s["ichimoku_cloud"] = _clip(cl)

    adx_v = float(last["adx"])
    dir_up = last["pdi"] >= last["mdi"]
    mag = min(50, adx_v / 40 * 50)
    s["adx_strength"] = _clip(50 + mag if dir_up else 50 - mag)

    s["rsi_position"] = _clip(float(last["rsi"]))
    hist = d["macd_hist"]
    ref = hist.abs().rolling(100, min_periods=20).quantile(0.9).iloc[-1]
    s["macd_hist"] = _clip(50 + np.clip(hist.iloc[-1] / (ref or 1), -1, 1) * 50)
    s["stoch_rsi"] = _clip(float(last["srsi"]))

    vr = float(last["vol_ratio"]) if pd.notna(last["vol_ratio"]) else 1.0
    s["volume_ratio"] = _clip(50 + np.clip((vr - 1) / 1.5, -1, 1) * 50)

    rng = last["bb_up"] - last["bb_dn"]
    pos = (c - last["bb_dn"]) / rng * 100 if rng and pd.notna(rng) else 50
    s["bb_position"] = _clip(pos)

    align = bias_strength if direction == "long" else 100 - bias_strength
    s["htf_alignment"] = _clip(align)
    return s


def aggregate(scores, cfg, direction):
    w = cfg["weights"]
    tot = sum(w.values())
    eff = {k: (v if direction == "long" else 100 - v) for k, v in scores.items()}
    final = sum(eff[k] * w[k] for k in w) / tot
    blocks = {}
    for b, keys in BLOCKS.items():
        bw = sum(w[k] for k in keys)
        blocks[b] = sum(eff[k] * w[k] for k in keys) / bw
    return final, blocks, eff


def analyze(df, df_htf, cfg):
    d = enrich(df, cfg)
    level, pct, ks = normalized_kalman_slope(d["close"], cfg["kalman_q"], cfg["kalman_r"])
    d["k_level"], d["k_slope_pct"] = level, pct
    bias, strength = htf_bias(df_htf, cfg)

    results = {}
    for direction in ("long", "short"):
        raw = component_scores(d, float(ks.iloc[-1]), strength, direction)
        final, blocks, eff = aggregate(raw, cfg, direction)
        results[direction] = {"score": final, "blocks": blocks, "components": eff}

    direction = "long" if bias == "long" else "short" if bias == "short" else None
    warnings = []
    if bias == "neutral":
        warnings.append("تایم‌فریم بالاتر بی‌روند است — سیگنال صادر نمی‌شود.")

    last = d.iloc[-1]
    price, a = float(last["close"]), float(last["atr"])
    plan, passed, reason = None, False, "روند تایم‌فریم بالاتر خنثی"
    if direction:
        r = results[direction]
        gates = cfg["block_gates"]
        failed = [b for b, th in gates.items() if r["blocks"][b] < th]
        rr = None
        if direction == "long":
            sl = price - cfg["sl_atr_mult"] * a
            tp = price + 2.2 * cfg["sl_atr_mult"] * a
        else:
            sl = price + cfg["sl_atr_mult"] * a
            tp = price - 2.2 * cfg["sl_atr_mult"] * a
        rr = abs(tp - price) / max(abs(price - sl), 1e-9)
        plan = {"entry": price, "sl": sl, "tp": tp, "rr": rr, "atr": a}
        if failed:
            reason = "عدم عبور از گیت بلوک: " + ", ".join(failed)
            warnings.append(reason)
        elif r["score"] < cfg["signal_threshold"]:
            reason = f"امتیاز {r['score']:.1f} کمتر از آستانه {cfg['signal_threshold']}"
        elif rr < cfg["min_rr"]:
            reason = f"نسبت R:R = {rr:.2f} کمتر از حد مجاز"
        else:
            passed, reason = True, "تأیید شده"
        if float(last["adx"]) < 18:
            warnings.append("ADX پایین: بازار رِنج، احتمال سیگنال کاذب.")
        if pd.notna(last["vol_ratio"]) and last["vol_ratio"] < 0.7:
            warnings.append("حجم کم‌تر از میانگین: تأیید ضعیف.")

    return {
        "df": d, "htf_bias": bias, "htf_strength": strength, "direction": direction,
        "results": results, "plan": plan, "signal": passed, "reason": reason,
        "warnings": warnings,
        "score": results[direction]["score"] if direction else max(results["long"]["score"], results["short"]["score"]),
    }
