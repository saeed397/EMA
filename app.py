"""اسکنر سیگنال کریپتو — معماری دو لایه.

لایه اول (نمایان): کارت سیگنال گرافیکی/عددی با شاخص‌های EMA و ایچیموکو.
لایه دوم (پنهان در st.expander): تحلیل ساده و خودی + تحلیل تفصیلی.

فقط لایه نمایش تغییر کرده است؛ منطق، فرمول‌ها، وزن‌ها و آستانه‌های استراتژی
دست‌نخورده باقی مانده‌اند (scoring.py / my_crypto_lib.py / kalman.py).
همه داده‌ها فقط از API واقعی صرافی‌ها (Binance / KuCoin / OKX) خوانده می‌شود.
"""
import json
from pathlib import Path

import streamlit as st

from data_sources import rank_universe, fetch_ohlcv
from scoring import analyze
from signal_card import build_card, card_html, summary_html
from narrative import build_narrative, narrative_html

st.set_page_config(page_title="اسکنر سیگنال کریپتو", page_icon="📈", layout="centered")

CFG = json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8"))

HTF_MAP = {"1m": "15m", "5m": "30m", **CFG["htf_map"],
           "1w": "1M", "1M": "1M", "1y": "1y"}
TF_OPTIONS = ["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M", "1y"]
TF_LABELS = {"1w": "هفتگی (1W)", "1M": "ماهانه (1M)", "1y": "سالانه (1Y)"}
SIDE_OPTIONS = ["فقط سیگنال‌های خرید", "فقط سیگنال‌های فروش", "همه سیگنال‌ها"]
SIDE_KEYS = {SIDE_OPTIONS[0]: "long", SIDE_OPTIONS[1]: "short", SIDE_OPTIONS[2]: "both"}

RANK_RANGES = [(1, 50), (1, 100), (1, 200), (1, 300), (1, 500),
               (51, 100), (101, 200), (201, 300), (301, 500)]
THRESHOLDS = [60, 65, 68, 70, 72, 75, 80, 85]
RR_OPTIONS = [1.0, 1.2, 1.5, 1.8, 2.0, 2.5, 3.0]

st.markdown("""
<style>
html, body, [class*="css"] { direction: rtl; font-family: "Vazirmatn","Segoe UI",Tahoma,sans-serif; }
.stApp { background:#0b1020; }
.sigcard { background:#121a2e; border:1px solid #2a3552; border-radius:14px;
           padding:14px 16px; margin:12px 0 0 0; line-height:2; font-size:.98rem; }
.sigcard .hdr { font-size:1.12rem; font-weight:800; margin-bottom:8px; }
.sigcard .sec { color:#9aa7bd; font-weight:700; margin:10px 0 4px 0; }
.sigcard .row { color:#e6ebf5; }
.sigcard .score { margin-top:10px; font-weight:800; }
.mgrid { display:grid; grid-template-columns:1fr; gap:2px; }
.mrow { display:flex; align-items:center; gap:8px; background:#0f1626;
        border:1px solid #222d47; border-radius:8px; padding:5px 8px; line-height:1.7; }
.mdot { font-size:.8rem; }
.mlbl { color:#9fb0c9; font-size:.85rem; flex:1; }
.mval { color:#eaf0fb; font-weight:700; font-size:.9rem;
        font-family:"Consolas","Menlo",monospace; direction:ltr; }
.bar { height:8px; background:#0f1626; border-radius:999px; margin-top:6px; overflow:hidden; }
.barfill { height:100%; border-radius:999px; }
.sigsum .row { color:#dfe6f3; }
.nsum { color:#dfe6f3; margin-bottom:10px; }
.nsec { color:#9aa7bd; font-weight:700; margin:10px 0 4px 0; }
.nrow { color:#e6ebf5; margin-bottom:6px; }
.nwhy { color:#9fb0c9; font-size:.86rem; line-height:1.9; }
.nverdict { margin-top:12px; font-weight:800; }
.badge { display:inline-block; padding:6px 12px; border-radius:999px; font-weight:800; font-size:.9rem; }
</style>
""", unsafe_allow_html=True)

ss = st.session_state
ss.setdefault("tf", CFG["timeframe"] if CFG["timeframe"] in TF_OPTIONS else "4h")
ss.setdefault("rank_idx", 0)
ss.setdefault("thr", CFG["signal_threshold"])
ss.setdefault("rr", CFG["min_rr"])
ss.setdefault("cursor", 0)
ss.setdefault("cards", [])
ss.setdefault("note", "")
ss.setdefault("side", SIDE_OPTIONS[2])

st.markdown("### 📈 اسکنر سیگنال کریپتو")


def tf_box(key):
    new = st.selectbox("تایم‌فریم", TF_OPTIONS, index=TF_OPTIONS.index(ss["tf"]), key=key,
                       format_func=lambda v: TF_LABELS.get(v, v))
    if new != ss["tf"]:
        ss["tf"] = new
        ss["cursor"] = 0


with st.expander("⚙️ تنظیمات اسکن", expanded=not ss["cards"]):
    a1, = st.columns(1)
    with a1:
        ss["rank_idx"] = RANK_RANGES.index(st.selectbox(
            "محدوده رتبه بازار", RANK_RANGES, index=ss["rank_idx"],
            format_func=lambda r: f"رتبه {r[0]} تا {r[1]}"))
    b1, = st.columns(1)
    with b1:
        ss["thr"] = st.selectbox("آستانه سیگنال (امتیاز نهایی)", THRESHOLDS,
                                 index=THRESHOLDS.index(ss["thr"]) if ss["thr"] in THRESHOLDS else 4,
                                 format_func=lambda v: f"{v} از ۱۰۰")
    c1, c2 = st.columns(2)
    with c1:
        ss["rr"] = st.selectbox("حداقل نسبت سود به ریسک (R:R)", RR_OPTIONS,
                                index=RR_OPTIONS.index(ss["rr"]) if ss["rr"] in RR_OPTIONS else 2,
                                format_func=lambda v: f"{v:.1f} به ۱")
    with c2:
        tf_box("tf_rr")

    new_side = st.radio("نوع سیگنال", SIDE_OPTIONS,
                        index=SIDE_OPTIONS.index(ss["side"]), horizontal=True, key="side_radio")
    if new_side != ss["side"]:
        ss["side"] = new_side
        ss["cursor"] = 0

    st.caption(f"تأیید تایم‌فریم بالاتر: {HTF_MAP[ss['tf']]}")

stop_first = st.toggle("توقف در اولین سیگنال", value=True, key="stop_toggle",
                       help="روشن: با اولین سیگنال متوقف می‌شود و دفعه بعد از همان نقطه ادامه می‌دهد. خاموش: اسکن پیوسته.")
if stop_first:
    st.markdown("<span class='badge' style='background:#16c78422;color:#16c784'>"
                "🟢 روشن — با اولین سیگنال توقف و ادامه از همان نقطه</span>", unsafe_allow_html=True)
else:
    st.markdown("<span class='badge' style='background:#ea394322;color:#ea3943'>"
                "🔴 خاموش — اسکن پیوسته بدون توقف</span>", unsafe_allow_html=True)

CFG["signal_threshold"] = ss["thr"]
CFG["min_rr"] = ss["rr"]

r1, r2 = st.columns(2)
run = r1.button("🚀 شروع / ادامه اسکن", type="primary", use_container_width=True)
if r2.button("♻️ بازنشانی", use_container_width=True):
    ss["cursor"], ss["cards"], ss["note"] = 0, [], ""


def render_signal(target, item):
    """لایه ۱: کارت گرافیکی/عددی — لایه ۲: تفسیر ساده داخل expander."""
    card, narr = item["card"], item["narrative"]
    with target.container():
        st.markdown(card_html(card), unsafe_allow_html=True)
        with st.expander("💬 تفسیر ساده و خودی (اختیاری)"):
            st.markdown(narrative_html(narr), unsafe_allow_html=True)
            st.markdown("**تحلیل تفصیلی:**")
            st.markdown(summary_html(card), unsafe_allow_html=True)


stream = st.container()
for it in ss["cards"]:
    want = SIDE_KEYS[ss["side"]]
    if want == "both" or it.get("dir") == want:
        render_signal(stream, it)

if run:
    try:
        src, universe = rank_universe(CFG["exchanges"], CFG["quote"], CFG["max_top_n"])
    except Exception as e:
        st.error(f"اتصال به صرافی برقرار نشد: {e}")
        st.stop()

    lo, hi = RANK_RANGES[ss["rank_idx"]]
    sel = universe[(universe["rank"] >= lo) & (universe["rank"] <= hi)].reset_index(drop=True)
    start = min(ss["cursor"], len(sel))
    end = min(start + CFG["batch_size"], len(sel)) if stop_first else len(sel)
    status = st.empty()
    found = 0

    for i in range(start, end):
        r = sel.iloc[i]
        status.caption(f"بررسی {i + 1}/{len(sel)} — {r['symbol']}")
        ss["cursor"] = i + 1
        try:
            df = fetch_ohlcv(CFG["exchanges"], r["symbol"], ss["tf"], CFG["limit_candles"])
            dh = fetch_ohlcv(CFG["exchanges"], r["symbol"], HTF_MAP[ss["tf"]], 300)
            res = analyze(df, dh, CFG)
        except Exception:
            continue
        if not res["signal"]:
            continue
        want = SIDE_KEYS[ss["side"]]
        if want != "both" and res["direction"] != want:
            continue
        item = {"card": build_card(r["symbol"], res, CFG["quote"]),
                "narrative": build_narrative(r["symbol"], res, CFG["quote"]),
                "dir": res["direction"]}
        ss["cards"].append(item)
        render_signal(stream, item)
        found += 1
        if stop_first:
            break

    status.empty()
    if found == 0:
        ss["note"] = "در این بازه سیگنالی صادر نشد." + (
            " پایان محدوده." if ss["cursor"] >= len(sel) else " برای ادامه دکمه اسکن را بزنید.")
    else:
        ss["note"] = (f"{found} سیگنال صادر شد؛ ادامه اسکن از رتبه {lo + ss['cursor']}."
                      if ss["cursor"] < len(sel) else "پایان محدوده.")
    if ss["cursor"] >= len(sel):
        ss["cursor"] = 0

if ss["note"]:
    st.caption(ss["note"])
