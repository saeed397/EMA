"""Plain-language Persian narrative builder (presentation layer only).

Reads ONLY the values already computed by scoring.analyze() from real
exchange data. No formulas, weights, thresholds or decisions are changed
here: this module just translates numbers into casual Persian judgement.
"""
import pandas as pd


def _fmt(p):
    p = float(p)
    if p >= 1000:
        return f"{p:,.0f}"
    if p >= 1:
        return f"{p:,.2f}"
    return f"{p:.6g}"


def _ema_state(last):
    """Returns (kind, text) using the REAL ema values. kind in up/down/mixed."""
    v = [float(last[f"ema{n}"]) for n in (20, 50, 100, 200)]
    if all(v[i] > v[i + 1] for i in range(3)):
        return "up", "EMAها کاملاً منظم بالای هم هستن (۲۰ روی ۵۰، ۵۰ روی ۱۰۰ و ۱۰۰ روی ۲۰۰)."
    if all(v[i] < v[i + 1] for i in range(3)):
        return "down", "EMAها کاملاً منظم زیر هم هستن (۲۰ زیر ۵۰، ۵۰ زیر ۱۰۰ و ۱۰۰ زیر ۲۰۰)."
    names = (20, 50, 100, 200)
    bad = [f"EMA{names[i + 1]} {'بالاتر' if v[i] < v[i + 1] else 'پایین‌تر'} از EMA{names[i]}"
           for i in range(3) if (v[i] < v[i + 1]) == (float(last["close"]) > v[0])]
    detail = bad[0] if bad else "ترتیب کامل نیست"
    return "mixed", f"ترتیب EMA به‌هم‌ریخته‌ست ({detail})."


def _cloud_state(d):
    last = d.iloc[-1]
    a, b, c = last["span_a"], last["span_b"], float(last["close"])
    if pd.isna(a) or pd.isna(b):
        return "unknown", "داده ایچیموکو کافی نیست."
    ref = d["close"].iloc[-27] if len(d) > 27 else d["close"].iloc[0]
    chikou = "چیکو هم صعودیه" if c > float(ref) else "چیکو نزولیه"
    if c > max(a, b):
        return "up", f"قیمت بالای ابر ایچیموکوئه و {chikou}."
    if c < min(a, b):
        return "down", f"قیمت زیر ابر ایچیموکوئه و {chikou}."
    return "mixed", "ایچیموکو مبهمه؛ قیمت داخل ابره و جهت مشخصی نداره."


def build_narrative(symbol, res, quote="USDT"):
    """Returns dict(title, summary, pros, cons, verdict) — all Persian strings."""
    d = res["df"]
    last = d.iloc[-1]
    direction = res["direction"]
    long_side = direction == "long"
    dir_fa = "خرید" if long_side else ("فروش" if direction else "خنثی")
    score = float(res["score"])

    pros, cons = [], []

    # --- Trend: EMA order ---
    ek, etxt = _ema_state(last)
    good_ema = (ek == "up" and long_side) or (ek == "down" and not long_side)
    if good_ema:
        pros.append((etxt, "یعنی بازار یکدست در همین جهته و روندش به هم نریخته — قوی‌ترین حالت ممکنه."))
    else:
        cons.append((etxt, "یعنی روند بلندمدت هنوز کامل تأیید نشده و ممکنه فقط یه موج موقت باشه."))

    # --- Structure: Ichimoku ---
    ck, ctxt = _cloud_state(d)
    if (ck == "up" and long_side) or (ck == "down" and not long_side):
        pros.append((ctxt, "یعنی ساختار روند از دو جهت مستقل تأیید شده."))
    elif ck == "unknown":
        cons.append((ctxt, "یعنی نمی‌شه به تأیید ساختاری تکیه کرد."))
    else:
        cons.append((ctxt, "یعنی ساختار قیمت هنوز طرف این سیگنال رو نگرفته."))

    # --- Trend strength: ADX ---
    adx = float(last["adx"])
    if adx >= 25:
        pros.append((f"قدرت روند (ADX ~{adx:.0f}) بالاست.",
                     "یعنی حرکت واقعیه و فقط یه نوسان ساده نیست."))
    elif adx >= 18:
        cons.append((f"قدرت روند متوسطه (ADX ~{adx:.0f}).",
                     "یعنی حرکت هنوز جون نگرفته و ممکنه نصفه‌کاره بمونه."))
    else:
        cons.append((f"قدرت روند پایینه (ADX ~{adx:.0f}).",
                     "یعنی بازار رِنجه و احتمال سیگنال کاذب بالاست."))

    # --- Momentum: MACD ---
    mh = float(last["macd_hist"])
    macd_ok = (mh > 0) if long_side else (mh < 0)
    if macd_ok:
        pros.append((f"MACD {'مثبته' if mh > 0 else 'منفیه'} و هم‌جهت سیگناله.",
                     "یعنی نیروی محرکه حرکت هنوز تموم نشده."))
    else:
        cons.append((f"MACD {'مثبته' if mh > 0 else 'منفیه'} و مخالف جهت سیگناله.",
                     "یعنی مومنتوم کوتاه‌مدت این حرکت رو تأیید نمی‌کنه."))

    # --- Momentum: RSI ---
    rsi = float(last["rsi"])
    rsi_ok = rsi >= 50 if long_side else rsi <= 50
    if rsi_ok:
        pros.append((f"RSI روی {rsi:.0f} است ({'بالای' if rsi >= 50 else 'زیر'} ۵۰).",
                     "یعنی فشار " + ("خرید از فروش بیشتره." if long_side else "فروش از خرید بیشتره.")))
    else:
        cons.append((f"RSI روی {rsi:.0f} است و هم‌سو با سیگنال نیست.",
                     "یعنی تمایل غالب بازار هنوز برنگشته."))

    # --- Kalman smoothed derivative ---
    ks = float(res["results"][direction]["components"]["kalman_slope"]) if direction else 50.0
    if ks >= 60:
        pros.append(("شیب هموارشده کالمن (مشتق قیمت) هم‌جهت سیگناله.",
                     "یعنی روند بدون نویز و پایداره، نه یه جهش لحظه‌ای."))
    elif ks <= 45:
        cons.append(("شیب هموارشده کالمن با جهت سیگنال هم‌سو نیست.",
                     "یعنی حرکت زیرپوستی قیمت هنوز نچرخیده."))

    # --- Volume ---
    vr = last["vol_ratio"]
    if pd.isna(vr):
        cons.append(("داده حجم کافی نیست.", "یعنی نمی‌شه فهمید پول واقعی پشت حرکته یا نه."))
    else:
        vr = float(vr)
        if vr >= 1.0:
            pros.append((f"حجم معاملات بالاتر از میانگینه (~{vr:.2f} برابر).",
                         "یعنی این حرکت با پول واقعی حمایت شده."))
        elif vr >= 0.7:
            cons.append((f"حجم نزدیک میانگینه (~{vr:.2f} برابر) و تأییدش ضعیفه.",
                         "یعنی پشتوانه حرکت متوسطه و ممکنه کِش نیاد."))
        else:
            cons.append((f"حجم معاملات پایین‌تر از میانگینه (~{vr:.2f} برابر).",
                         "یعنی این حرکت هنوز با «پول واقعی» حمایت نشده و می‌تونه ضعیف بشه."))

    # --- HTF alignment ---
    htf_fa = {"long": "صعودی", "short": "نزولی", "neutral": "خنثی"}[res["htf_bias"]]
    if res["htf_bias"] == direction:
        pros.append((f"تایم‌فریم بالاتر {htf_fa}ه و هم‌راستا با سیگناله.",
                     "یعنی داری هم‌جهت با موج بزرگ‌تر بازار حرکت می‌کنی."))
    else:
        cons.append((f"تایم‌فریم بالاتر {htf_fa}ه و هم‌راستا نیست.",
                     "یعنی سیگنال خلاف جریان اصلی بازاره و ریسکش بالاتره."))

    # --- Risk plan (real ATR-based numbers) ---
    plan = res.get("plan")
    if plan:
        rr = float(plan["rr"])
        line = (f"ورود {_fmt(plan['entry'])} {quote}، حد ضرر {_fmt(plan['sl'])}، "
                f"هدف {_fmt(plan['tp'])} و R:R = {rr:.2f}.")
        if rr >= 1.5:
            pros.append((line, "یعنی نسبت سود به ریسک منطقیه و ارزش ریسک کردن داره."))
        else:
            cons.append((line, "یعنی سود احتمالی نسبت به ریسک کمه."))

    for w in res.get("warnings", []):
        cons.append((str(w), "یعنی این مورد می‌تونه سیگنال رو نیمه‌کاره رها کنه."))

    if not cons:
        cons.append(("هیچ فاکتور منفی صریحی دیده نشد، اما هیچ سیگنالی بدون ریسک نیست.",
                     "یعنی حتی در بهترین حالت هم حجم پوزیشن رو محافظه‌کارانه ببند."))

    # --- Summary line ---
    if score >= 80 and len(cons) <= 2:
        head = "👌 خلاصه: این سیگنال از نظر «روند» و «ساختار» در بهترین حالت ممکنه، اما نقطه ضعف واقعی داره که باید بهش توجه کنی."
        grade = "قوی، ولی با یه هشدار"
    elif score >= 65:
        head = "🙂 خلاصه: سیگنال قابل قبولیه؛ بیشتر فاکتورها موافقن ولی یکی دو مورد کامل تأیید نشده."
        grade = "متوسط تا خوب"
    else:
        head = "🤔 خلاصه: این سیگنال نصفه‌نیمه‌ست. بعضی فاکتورها خوبن ولی بعضی دقیقاً مخالفشو می‌گن. بهتره عجله نکنی."
        grade = "ضعیف — ماندن در حالت انتظار توصیه می‌شه"

    weak_titles = "، ".join(t.rstrip("؛.") for t, _ in cons[:2])
    verdict = (f"🎯 جمع‌بندی: مهم‌ترین ضعف‌ها: {weak_titles}. "
               f"امتیاز نهایی: {score:.1f}/100 — {grade}.")

    return {
        "title": f"📊 سیگنال {dir_fa} — {symbol}",
        "summary": head,
        "pros": pros,
        "cons": cons,
        "verdict": verdict,
        "score": score,
        "long_side": long_side,
    }


def narrative_text(n):
    out = [n["title"], "", n["summary"], "", "✅ نقاط قوت:"]
    out += [f"• {t}\n  {w}" for t, w in n["pros"]]
    out += ["", "⚠️ نقاط ضعف:"]
    out += [f"• {t}\n  {w}" for t, w in n["cons"]]
    out += ["", n["verdict"]]
    return "\n".join(out)


def narrative_html(n):
    color = "#16c784" if n["long_side"] else "#ea3943"

    def block(title, items):
        rows = "".join(
            f"<div class='nrow'>• {t}<div class='nwhy'>{w}</div></div>" for t, w in items)
        return f"<div class='nsec'>{title}</div>{rows}"

    return f"""
<div class="sigcard" style="border-color:{color}55">
  <div class="hdr" style="color:{color}">{n['title']}</div>
  <div class="nsum">{n['summary']}</div>
  {block("✅ نقاط قوت:", n['pros'])}
  {block("⚠️ نقاط ضعف:", n['cons'])}
  <div class="nverdict" style="color:{color}">{n['verdict']}</div>
</div>"""
