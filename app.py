"""اسکنر سیگنال کریپتو — خروجی سبک: فقط «کارت سیگنال» در لحظه صدور.

بدون چارت، بدون گیج، بدون جدول؛ مناسب اینترنت کم‌سرعت.
"""
import json
from pathlib import Path

import streamlit as st

from data_sources import rank_universe, fetch_ohlcv
from scoring import analyze
from signal_card import build_card, card_html

st.set_page_config(page_title="اسکنر سیگنال کریپتو", page_icon="📈", layout="centered")

CFG = json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8"))

st.markdown("""
<style>
html, body, [class*="css"] { direction: rtl; font-family: "Vazirmatn","Segoe UI",Tahoma,sans-serif; }
.stApp { background:#0b1020; }
.sigcard { background:#121a2e; border:1px solid #2a3552; border-radius:14px;
           padding:14px 16px; margin:10px 0; line-height:2; font-size:.98rem; }
.sigcard .ttl { font-weight:800; margin-bottom:6px; }
.sigcard .hdr { font-size:1.15rem; font-weight:800; margin-bottom:10px; }
.sigcard .sec { color:#9aa7bd; margin-bottom:4px; }
.sigcard .row { color:#e6ebf5; }
.sigcard .score { margin-top:10px; font-weight:800; }
</style>
""", unsafe_allow_html=True)

ss = st.session_state
ss.setdefault("rank_from", 1)
ss.setdefault("rank_to", CFG["top_n"])
ss.setdefault("timeframe", CFG["timeframe"])
ss.setdefault("threshold", CFG["signal_threshold"])
ss.setdefault("cursor", 0)          # ادامه اسکن از این ایندکس
ss.setdefault("cards", [])          # کارت‌های صادرشده
ss.setdefault("last_note", "")

st.markdown("### 📈 اسکنر سیگنال کریپتو (خروجی سبک)")

with st.expander("⚙️ تنظیمات", expanded=not ss["cards"]):
    rng = st.slider("محدوده رتبه بازار", 1, CFG["max_top_n"], (ss["rank_from"], ss["rank_to"]))
    ss["rank_from"], ss["rank_to"] = rng
    ss["timeframe"] = st.selectbox("تایم‌فریم", list(CFG["htf_map"].keys()),
                                   index=list(CFG["htf_map"].keys()).index(ss["timeframe"]))
    st.caption(f"تأیید تایم‌فریم بالاتر: {CFG['htf_map'][ss['timeframe']]}")
    ss["threshold"] = st.slider("آستانه سیگنال", 55, 90, int(ss["threshold"]))
    CFG["signal_threshold"] = ss["threshold"]
    CFG["min_rr"] = st.slider("حداقل R:R", 1.0, 3.0, float(CFG["min_rr"]), 0.1)
    stop_first = st.toggle("توقف در اولین سیگنال و ادامه از همان نقطه", value=True)

c1, c2 = st.columns(2)
run = c1.button("🚀 شروع / ادامه اسکن", type="primary", use_container_width=True)
if c2.button("♻️ بازنشانی", use_container_width=True):
    ss["cursor"], ss["cards"], ss["last_note"] = 0, [], ""

stream = st.container()
for c in ss["cards"]:
    stream.markdown(card_html(c), unsafe_allow_html=True)

if run:
    try:
        src, universe = rank_universe(CFG["exchanges"], CFG["quote"], CFG["max_top_n"])
    except Exception as e:
        st.error(f"اتصال به صرافی برقرار نشد: {e}")
        st.stop()

    sel = universe[(universe["rank"] >= ss["rank_from"]) & (universe["rank"] <= ss["rank_to"])].reset_index(drop=True)
    start = min(ss["cursor"], len(sel))
    end = min(start + CFG["batch_size"], len(sel))
    status = st.empty()
    found = 0

    for i in range(start, end):
        r = sel.iloc[i]
        status.caption(f"بررسی {i + 1}/{len(sel)} — {r['symbol']}")
        ss["cursor"] = i + 1
        try:
            df = fetch_ohlcv(CFG["exchanges"], r["symbol"], ss["timeframe"], CFG["limit_candles"])
            dh = fetch_ohlcv(CFG["exchanges"], r["symbol"], CFG["htf_map"][ss["timeframe"]], 300)
            res = analyze(df, dh, CFG)
        except Exception:
            continue
        if not res["signal"]:
            continue
        card = build_card(r["symbol"], res, CFG["quote"])
        ss["cards"].append(card)
        stream.markdown(card_html(card), unsafe_allow_html=True)
        found += 1
        if stop_first:
            break

    status.empty()
    if found == 0:
        ss["last_note"] = (f"در بازه رتبه {start + 1} تا {end} سیگنالی صادر نشد." +
                           (" پایان محدوده." if ss["cursor"] >= len(sel) else " برای ادامه دکمه اسکن را بزنید."))
    else:
        ss["last_note"] = (f"{found} سیگنال صادر شد. ادامه اسکن از رتبه {ss['cursor'] + 1}."
                           if ss["cursor"] < len(sel) else "پایان محدوده.")
    if ss["cursor"] >= len(sel):
        ss["cursor"] = 0

if ss["last_note"]:
    st.caption(ss["last_note"])
