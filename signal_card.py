"""Signal card builder — light text output only (no charts, no online rendering).

Includes:
- EMA order line whose operators always match the real mathematical relations.
- A Persian "detailed analysis" summary that synthesizes the confluence factors.
"""
import pandas as pd

GREEN, RED = "#16c784", "#ea3943"

EMA_PERIODS = (20, 50, 100, 200)


def _fmt(p):
    if p >= 1000:
        return f"{p:,.0f}"
    if p >= 1:
        return f"{p:,.2f}"
    return f"{p:.6g}"


def _base(symbol):
    return symbol.split("/")[0]


def ema_chain(last):
    """Chain string built from the ACTUAL values, e.g. '20 > 50 > 100 < 200'."""
    vals = [float(last[f"ema{n}"]) for n in EMA_PERIODS]
    parts = [str(EMA_PERIODS[0])]
    for i in range(len(EMA_PERIODS) - 1):
        op = ">" if vals[i] > vals[i + 1] else "<"
        parts.append(op)
        parts.append(str(EMA_PERIODS[i + 1]))
    return " ".join(parts), vals


def ema_line(last, direction):
    chain, vals = ema_chain(last)
    up_ok = all(vals[i] > vals[i + 1] for i in range(3))
    dn_ok = all(vals[i] < vals[i + 1] for i in range(3))
    if up_ok:
        txt, tail = "صعودی", "هر چهار EMA به ترتیب بالاتر از هم هستند."
    elif dn_ok:
        txt, tail = "نزولی", "هر چهار EMA به ترتیب پایین‌تر از هم هستند."
    else:
        txt = "صعودی ناقص" if direction == "long" else "نزولی ناقص"
        tail = "ترتیب EMA کامل نیست."
    return f"روند EMA: {txt} ({chain}) - {tail}"


def ichimoku_line(d, direction):
    last = d.iloc[-1]
    a, b, c = last["span_a"], last["span_b"], last["close"]
    if pd.isna(a) or pd.isna(b):
        return "ساختار ایچیموکو: داده کافی نیست"
    if c > max(a, b):
        pos = "قیمت بالای ابر"
    elif c < min(a, b):
        pos = "قیمت زیر ابر"
    else:
        pos = "قیمت داخل ابر"
    span = "اسپن آ بالای اسپن ب" if a > b else "اسپن آ زیر اسپن ب"
    ref = d["close"].iloc[-27] if len(d) > 27 else d["close"].iloc[0]
    chikou = "چیکو صعودی" if c > ref else "چیکو نزولی"
    return f"ساختار ایچیموکو: {pos}، {span}، {chikou}"


def volume_line(last):
    vr = last["vol_ratio"]
    if pd.isna(vr):
        return "وضعیت حجم: داده کافی نیست"
    if vr >= 1.0:
        return "وضعیت حجم: بالاتر از میانگین (تأیید شده)"
    if vr >= 0.7:
        return "وضعیت حجم: نزدیک میانگین (تأیید ضعیف)"
    return "وضعیت حجم: پایین‌تر از میانگین (تأیید نشده)"


# ——— تحلیل تفصیلی (هم‌گرایی عوامل) ———
_FACTOR_FA = {
    "trend_ema_stack": "ترتیب و کراس میانگین‌های متحرک EMA",
    "kalman_slope": "شیب هموارشده کالمن (مشتق قیمت)",
    "ichimoku_cloud": "تأیید ساختار ابر ایچیموکو",
    "adx_strength": "قدرت روند بر پایه ADX",
    "rsi_position": "موقعیت RSI",
    "macd_hist": "هیستوگرام MACD",
    "stoch_rsi": "استوکاستیک RSI",
    "volume_ratio": "افزایش قابل توجه حجم معاملات",
    "bb_position": "موقعیت قیمت در باند بولینگر",
    "htf_alignment": "هم‌راستایی با تایم‌فریم بالاتر",
}


def build_summary(res, direction, quote="USDT"):
    """Multi-line Persian deep-dive summary, synthesized from existing scores."""
    comps = res["results"][direction]["components"]
    blocks = res["results"][direction]["blocks"]
    d = res["df"]
    last = d.iloc[-1]
    dir_fa = "خرید" if direction == "long" else "فروش"

    htf_fa = {"long": "صعودی", "short": "نزولی", "neutral": "خنثی"}[res["htf_bias"]]
    strong = [k for k, v in sorted(comps.items(), key=lambda x: -x[1]) if v >= 65]
    weak = [k for k, v in sorted(comps.items(), key=lambda x: x[1])
            if v <= 40 and k != "htf_alignment"]
    htf_conf = res["htf_strength"] if direction == "long" else 100 - res["htf_strength"]

    conf = "، ".join(_FACTOR_FA[k] for k in strong[:4]) or "عوامل امتیازی خنثی"
    lines = [
        f"این سیگنال {dir_fa} بر اثر هم‌گرایی {conf} صادر شده است.",
        "— جمع‌بندی بلوک‌ها: "
        + "، ".join([
            f"روند {blocks['trend']:.0f}",
            f"مومنتوم {blocks['momentum']:.0f}",
            f"حجم {blocks['volume']:.0f}",
            f"ساختار {blocks['structure']:.0f}",
        ])
        + " (از ۱۰۰)",
        f"— {ema_line(last, direction)}",
        f"— {ichimoku_line(d, direction)}",
        f"— {volume_line(last)}",
        f"— RSI: {float(last['rsi']):.1f} | استوک RSI: {float(last['srsi']):.1f} | "
        f"ADX: {float(last['adx']):.1f} ({'DI+ برتر' if last['pdi'] >= last['mdi'] else 'DI− برتر'})",
        f"— هیستوگرام MACD: {float(last['macd_hist']):+.6g} "
        f"({'مثبت و مؤید ادامه حرکت' if last['macd_hist'] > 0 else 'منفی'})",
        f"— شیب کالمن (نرمال‌شده ۰..۱۰۰): {comps['kalman_slope']:.0f}؛ "
        + ("مشتق هموار قیمت، جهت سیگنال را تأیید می‌کند."
           if comps['kalman_slope'] >= 50 else "مشتق هموار قیمت با جهت سیگنال هم‌سو نیست."),
        f"— تایم‌فریم بالاتر: {htf_fa} با قدرت {htf_conf:.0f}/100"
        + ("، هم‌راستا با جهت سیگنال." if res["htf_bias"] == direction else "، مخالف جهت سیگنال."),
    ]
    plan = res.get("plan")
    if plan:
        lines.append(
            f"— مدیریت ریسک: ورود {_fmt(plan['entry'])} {quote} | حد ضرر {_fmt(plan['sl'])} | "
            f"هدف {_fmt(plan['tp'])} | R:R = {plan['rr']:.2f} (بر پایه ATR = {_fmt(plan['atr'])})"
        )
    if weak:
        lines.append("— نقاط ضعف/هشدار: " + "، ".join(_FACTOR_FA[k] for k in weak[:3]) + ".")
    for w in res.get("warnings", []):
        lines.append(f"— ⚠️ {w}")
    lines.append(
        f"— نتیجه: امتیاز نهایی {res['score']:.1f}/100 و وضعیت «{res.get('reason', '')}»."
    )
    return lines


def _dot(ok):
    """Status circle: green=confirmed, red=not confirmed, gray=unknown."""
    return {True: "🟢", False: "🔴", None: "⚪"}[ok]


def build_metrics(res, direction):
    """Numerical grid rows: (label, value_text, status) — presentation only."""
    d = res["df"]
    last = d.iloc[-1]
    comps = res["results"][direction]["components"]
    blocks = res["results"][direction]["blocks"]
    long_side = direction == "long"
    vals = [float(last[f"ema{n}"]) for n in EMA_PERIODS]
    chain, _ = ema_chain(last)
    ema_ok = all(vals[i] > vals[i + 1] for i in range(3)) if long_side \
        else all(vals[i] < vals[i + 1] for i in range(3))
    a, b, c = last["span_a"], last["span_b"], float(last["close"])
    if pd.isna(a) or pd.isna(b):
        cloud_ok, cloud_txt = None, "—"
    else:
        cloud_ok = (c > max(a, b)) if long_side else (c < min(a, b))
        cloud_txt = f"{_fmt(c)} / ابر {_fmt(float(min(a, b)))}–{_fmt(float(max(a, b)))}"
    vr = None if pd.isna(last["vol_ratio"]) else float(last["vol_ratio"])
    rsi, srsi, adx = float(last["rsi"]), float(last["srsi"]), float(last["adx"])
    mh = float(last["macd_hist"])
    rows = [
        ("EMA (20/50/100/200)", chain, ema_ok),
        ("EMA 20 / EMA 200", f"{_fmt(vals[0])} / {_fmt(vals[3])}", ema_ok),
        ("ایچیموکو (قیمت/ابر)", cloud_txt, cloud_ok),
        ("RSI", f"{rsi:.1f}", (rsi >= 50) if long_side else (rsi <= 50)),
        ("Stoch RSI", f"{srsi:.1f}", (srsi >= 50) if long_side else (srsi <= 50)),
        ("MACD hist", f"{mh:+.6g}", (mh > 0) if long_side else (mh < 0)),
        ("ADX (DI+/DI−)", f"{adx:.1f} ({float(last['pdi']):.0f}/{float(last['mdi']):.0f})",
         adx >= 20),
        ("نسبت حجم", "—" if vr is None else f"{vr:.2f}×", None if vr is None else vr >= 1.0),
        ("شیب کالمن (۰..۱۰۰)", f"{comps['kalman_slope']:.0f}", comps['kalman_slope'] >= 50),
        ("HTF", f"{res['htf_bias']} ({res['htf_strength']:.0f})",
         res["htf_bias"] == direction),
        ("بلوک‌ها روند/مومنتوم/حجم/ساختار",
         f"{blocks['trend']:.0f} / {blocks['momentum']:.0f} / "
         f"{blocks['volume']:.0f} / {blocks['structure']:.0f}", None),
    ]
    plan = res.get("plan")
    if plan:
        rows += [
            ("ورود / حد ضرر / هدف",
             f"{_fmt(plan['entry'])} / {_fmt(plan['sl'])} / {_fmt(plan['tp'])}", None),
            ("R:R  |  ATR", f"{plan['rr']:.2f}  |  {_fmt(plan['atr'])}", plan['rr'] >= 1.5),
        ]
    return rows


def build_card(symbol, res, quote="USDT"):
    """Returns dict(header, dir_fa, color, lines, summary, score, price, text)."""
    d = res["df"]
    last = d.iloc[-1]
    direction = res["direction"]
    long_side = direction == "long"
    dir_fa = "خرید" if long_side else "فروش"
    color = GREEN if long_side else RED
    price = _fmt(float(last["close"]))
    htf = {"long": "صعودی", "short": "نزولی", "neutral": "خنثی"}[res["htf_bias"]]
    agree = "موافق" if res["htf_bias"] == direction else f"مخالف ({htf})"
    lines = [
        ema_line(last, direction),
        ichimoku_line(d, direction),
        volume_line(last),
        f"تایم‌فریم بالاتر: {agree}",
    ]
    score = int(round(res["score"]))
    dot = "🟢" if long_side else "🔴"
    header = f"{dot} {_base(symbol)} - {price} {quote} - {dir_fa}"
    summary = build_summary(res, direction, quote)
    metrics = build_metrics(res, direction)
    text = (
        f"{header}\n\nتحلیل فنی:\n"
        + "\n".join(f"• {l}" for l in lines)
        + f"\n\nامتیاز: {score}/100\n\nتحلیل تفصیلی:\n"
        + "\n".join(summary)
    )
    return {"header": header, "dir_fa": dir_fa, "color": color, "lines": lines,
            "summary": summary, "metrics": metrics, "score": score, "price": price,
            "text": text}


def card_html(c):
    """Primary layer: high-fidelity graphical + numerical signal card."""
    items = "".join(f"<div class='row'>• {l}</div>" for l in c["lines"])
    grid = "".join(
        f"<div class='mrow'><span class='mdot'>{_dot(ok)}</span>"
        f"<span class='mlbl'>{lbl}</span><span class='mval'>{val}</span></div>"
        for lbl, val, ok in c.get("metrics", [])
    )
    pct = max(0, min(100, c["score"]))
    return f"""
<div class="sigcard" style="border-color:{c['color']}55">
  <div class="hdr" style="color:{c['color']}">{c['header']}</div>
  <div class="sec">تحلیل فنی:</div>
  {items}
  <div class="sec">داده‌های عددی و وضعیت شاخص‌ها:</div>
  <div class="mgrid">{grid}</div>
  <div class="score" style="color:{c['color']}">امتیاز: {c['score']}/100</div>
  <div class="bar"><div class="barfill" style="width:{pct}%;background:{c['color']}"></div></div>
</div>"""


def summary_html(c):
    rows = "".join(f"<div class='row'>{l}</div>" for l in c["summary"])
    return f"<div class='sigsum'>{rows}</div>"
