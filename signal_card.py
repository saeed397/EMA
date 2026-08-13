"""Signal card builder — light text/HTML output only (no charts, no online rendering)."""
import pandas as pd

GREEN, RED = "#16c784", "#ea3943"


def _fmt(p):
    if p >= 1000:
        return f"{p:,.0f}"
    if p >= 1:
        return f"{p:,.2f}"
    return f"{p:.6g}"


def _base(symbol):
    return symbol.split("/")[0]


def ema_line(last, direction):
    order = ["20", "50", "100", "200"]
    vals = [last["ema20"], last["ema50"], last["ema100"], last["ema200"]]
    if direction == "long":
        ok = all(vals[i] > vals[i + 1] for i in range(3))
        chain = " > ".join(order)
        txt = "صعودی" if ok else "صعودی ناقص"
        tail = "هر چهار EMA به ترتیب بالاتر از هم هستند." if ok else "ترتیب EMA کامل نیست."
    else:
        ok = all(vals[i] < vals[i + 1] for i in range(3))
        chain = " < ".join(order)
        txt = "نزولی" if ok else "نزولی ناقص"
        tail = "هر چهار EMA به ترتیب پایین‌تر از هم هستند." if ok else "ترتیب EMA کامل نیست."
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


def build_card(symbol, res, quote="USDT"):
    """Returns dict(title, dir_fa, color, lines, score, price, text)."""
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
    text = (
        f"کارت سیگنال {dir_fa}\n\n{header}\n\nتحلیل فنی:\n"
        + "\n".join(f"• {l}" for l in lines)
        + f"\n\nامتیاز: {score}/100"
    )
    return {"header": header, "dir_fa": dir_fa, "color": color, "lines": lines,
            "score": score, "price": price, "text": text}


def card_html(c):
    items = "".join(f"<div class='row'>• {l}</div>" for l in c["lines"])
    return f"""
<div class="sigcard" style="border-color:{c['color']}55">
  <div class="ttl" style="color:{c['color']}">کارت سیگنال {c['dir_fa']}</div>
  <div class="hdr" style="color:{c['color']}">{c['header']}</div>
  <div class="sec">تحلیل فنی:</div>
  {items}
  <div class="score" style="color:{c['color']}">امتیاز: {c['score']}/100</div>
</div>"""
