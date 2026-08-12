"""Multi-Timeframe Confluence Crypto Scanner (Streamlit) — Kalman-smoothed derivatives."""
import json
import time
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from data_sources import rank_universe, fetch_ohlcv
from scoring import analyze, LABELS, BLOCKS

st.set_page_config(page_title="اسکنر سیگنال کریپتو", page_icon="📈", layout="wide")

CFG = json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8"))
GREEN, RED, GREY = "#16c784", "#ea3943", "#8892a6"
BLOCK_FA = {"trend": "روند", "momentum": "مومنتوم", "volume": "حجم", "structure": "ساختار"}

st.markdown("""
<style>
html, body, [class*="css"] { direction: rtl; font-family: "Vazirmatn","Segoe UI",Tahoma,sans-serif; }
.stApp { background: radial-gradient(1200px 600px at 20% -10%, #16233a 0%, #0d1220 45%, #0a0e18 100%); }
.card { background: linear-gradient(160deg, rgba(255,255,255,.06), rgba(255,255,255,.02));
        border: 1px solid rgba(255,255,255,.09); border-radius: 18px; padding: 16px 18px; margin-bottom: 12px;
        box-shadow: 0 10px 30px rgba(0,0,0,.25); }
.badge { display:inline-block; padding:4px 12px; border-radius:999px; font-size:.8rem; font-weight:700; }
.big { font-size:2rem; font-weight:800; }
h1,h2,h3,h4 { letter-spacing:.2px; }
[data-testid="stMetricValue"] { font-size: 1.4rem; }
</style>
""", unsafe_allow_html=True)


def color_for(v):
    return GREEN if v >= 50 else RED


def card(html):
    st.markdown(f'<div class="card">{html}</div>', unsafe_allow_html=True)


def gauge(score, direction):
    col = GREEN if direction == "long" else RED if direction == "short" else GREY
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=round(score, 1),
        number={"suffix": " / 100", "font": {"color": col, "size": 34}},
        gauge={"axis": {"range": [0, 100], "tickcolor": GREY},
               "bar": {"color": col, "thickness": 0.3},
               "bgcolor": "rgba(0,0,0,0)",
               "borderwidth": 0,
               "steps": [{"range": [0, 50], "color": "rgba(234,57,67,.16)"},
                         {"range": [50, 72], "color": "rgba(136,146,166,.16)"},
                         {"range": [72, 100], "color": "rgba(22,199,132,.20)"}],
               "threshold": {"line": {"color": "#fff", "width": 3}, "value": CFG["signal_threshold"]}}))
    fig.update_layout(height=230, margin=dict(l=10, r=10, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#e6ebf5"))
    return fig


def components_bar(components):
    keys = list(components.keys())
    vals = [components[k] for k in keys]
    fig = go.Figure(go.Bar(
        x=vals, y=[LABELS[k] for k in keys], orientation="h",
        marker=dict(color=[color_for(v) for v in vals]),
        text=[f"{v:.0f}" for v in vals], textposition="outside",
        textfont=dict(color=[color_for(v) for v in vals], size=13)))
    fig.add_vline(x=50, line_dash="dot", line_color=GREY)
    fig.update_layout(height=430, xaxis=dict(range=[0, 108], title="امتیاز (۰-۱۰۰)", gridcolor="rgba(255,255,255,.07)"),
                      yaxis=dict(autorange="reversed"), margin=dict(l=10, r=10, t=10, b=30),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#e6ebf5"))
    return fig


def blocks_radar(blocks):
    keys = list(blocks.keys())
    vals = [blocks[k] for k in keys]
    avg = sum(vals) / len(vals)
    fig = go.Figure(go.Scatterpolar(r=vals + [vals[0]], theta=[BLOCK_FA[k] for k in keys] + [BLOCK_FA[keys[0]]],
                                    fill="toself", line=dict(color=color_for(avg)),
                                    fillcolor="rgba(22,199,132,.18)" if avg >= 50 else "rgba(234,57,67,.18)"))
    fig.update_layout(height=300, polar=dict(bgcolor="rgba(255,255,255,.03)",
                                             radialaxis=dict(range=[0, 100], gridcolor="rgba(255,255,255,.12)")),
                      margin=dict(l=30, r=30, t=20, b=20), paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e6ebf5"),
                      showlegend=False)
    return fig


def price_chart(d, symbol, plan, direction):
    d = d.tail(180)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.74, 0.26], vertical_spacing=0.04)
    fig.add_trace(go.Candlestick(x=d.index, open=d["open"], high=d["high"], low=d["low"], close=d["close"],
                                 increasing_line_color=GREEN, decreasing_line_color=RED, name=symbol), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["span_a"], line=dict(width=0), showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["span_b"], line=dict(width=0), fill="tonexty",
                             fillcolor="rgba(120,140,255,.16)", name="ابر ایچیموکو"), row=1, col=1)
    for n, c in zip((20, 50, 100, 200), ("#f5c542", "#4ea8ff", "#b47bff", "#ff8a5c")):
        fig.add_trace(go.Scatter(x=d.index, y=d[f"ema{n}"], line=dict(width=1.2, color=c), name=f"EMA{n}"), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["k_level"], line=dict(width=2.2, color="#ffffff", dash="dot"),
                             name="فیلتر کالمن"), row=1, col=1)
    if plan:
        for y, lbl, c in ((plan["entry"], "ورود", "#ffffff"), (plan["sl"], "حد ضرر", RED), (plan["tp"], "هدف", GREEN)):
            fig.add_hline(y=y, line_dash="dash", line_color=c, opacity=.7,
                          annotation_text=lbl, annotation_position="left", row=1, col=1)
    slope = d["k_slope_pct"].fillna(0)
    fig.add_trace(go.Bar(x=d.index, y=slope, marker_color=[GREEN if v >= 0 else RED for v in slope],
                         name="مشتق کالمن (%)"), row=2, col=1)
    fig.update_layout(height=560, xaxis_rangeslider_visible=False, paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#e6ebf5"),
                      legend=dict(orientation="h", y=1.06), margin=dict(l=10, r=10, t=30, b=10))
    fig.update_yaxes(gridcolor="rgba(255,255,255,.07)")
    fig.update_xaxes(gridcolor="rgba(255,255,255,.05)")
    return fig


# ---------------------------------------------------------------- state
ss = st.session_state
ss.setdefault("rank_from", 1)
ss.setdefault("rank_to", CFG["top_n"])
ss.setdefault("timeframe", CFG["timeframe"])
ss.setdefault("threshold", CFG["signal_threshold"])
ss.setdefault("auto_batch", False)
ss.setdefault("batch_cursor", 0)
ss.setdefault("scan_rows", [])
ss.setdefault("details", {})

st.markdown("## 📈 اسکنر هم‌گرایی چند تایم‌فریمی کریپتو")
tab_scan, tab_settings, tab_help = st.tabs(["🔎 سیگنال‌ها", "⚙️ تنظیمات", "📘 راهنما"])

# ---------------------------------------------------------------- settings
with tab_settings:
    st.markdown("### محدوده رمزارزها بر اساس رتبه بازار")
    c1, c2 = st.columns([3, 2])
    with c1:
        rng = st.slider("رتبه (از / تا)", 1, CFG["max_top_n"], (ss["rank_from"], ss["rank_to"]), step=1)
        ss["rank_from"], ss["rank_to"] = rng
        st.caption(f"تعداد انتخاب‌شده: **{rng[1] - rng[0] + 1}** رمزارز (حداکثر {CFG['max_top_n']})")
    with c2:
        ss["timeframe"] = st.selectbox("تایم‌فریم", list(CFG["htf_map"].keys()),
                                       index=list(CFG["htf_map"].keys()).index(ss["timeframe"]))
        st.caption(f"تایم‌فریم تأییدکننده: **{CFG['htf_map'][ss['timeframe']]}**")

    st.markdown("### افزودن رمزارزها")
    b1, b2, b3 = st.columns(3)
    if b1.button(f"➕ افزودن {CFG['batch_size']} رمزارز بعدی", use_container_width=True):
        ss["rank_to"] = min(CFG["max_top_n"], ss["rank_to"] + CFG["batch_size"])
    if b2.button("🤖 بررسی اتوماتیک ۵۰ تا ۵۰ تا", use_container_width=True):
        ss["auto_batch"] = True
        ss["batch_cursor"] = ss["rank_from"] - 1
        ss["scan_rows"] = []
        ss["details"] = {}
    if b3.button("♻️ بازنشانی", use_container_width=True):
        ss["auto_batch"] = False
        ss["batch_cursor"] = 0
        ss["scan_rows"] = []
        ss["details"] = {}
    st.caption("در حالت اتوماتیک، همان تایم‌فریم انتخابی به‌صورت دسته‌های ۵۰تایی تا انتهای محدوده اسکن می‌شود.")

    st.markdown("### آستانه‌ها و مدیریت ریسک")
    d1, d2, d3 = st.columns(3)
    ss["threshold"] = d1.slider("آستانه سیگنال", 55, 90, int(ss["threshold"]))
    CFG["min_rr"] = d2.slider("حداقل R:R", 1.0, 3.0, float(CFG["min_rr"]), 0.1)
    CFG["sl_atr_mult"] = d3.slider("ضریب ATR برای حد ضرر", 0.5, 3.0, float(CFG["sl_atr_mult"]), 0.1)
    CFG["signal_threshold"] = ss["threshold"]

    st.markdown("### فیلتر کالمن (مشتق هموارشده)")
    k1, k2, k3 = st.columns(3)
    CFG["use_kalman"] = k1.toggle("فعال‌سازی فیلتر کالمن", value=CFG["use_kalman"])
    CFG["kalman_q"] = k2.select_slider("نویز فرآیند (q)", [1e-5, 5e-5, 1e-4, 5e-4, 1e-3], value=CFG["kalman_q"])
    CFG["kalman_r"] = k3.select_slider("نویز اندازه‌گیری (r)", [1e-3, 5e-3, 1e-2, 5e-2, 1e-1], value=CFG["kalman_r"])

    with st.expander("وزن مؤلفه‌ها (۱۰ مؤلفه در ۴ بلوک)"):
        cols = st.columns(2)
        for i, (k, v) in enumerate(CFG["weights"].items()):
            CFG["weights"][k] = cols[i % 2].slider(LABELS[k], 0, 25, int(v))
        st.caption("مجموع وزن‌ها به‌صورت خودکار نرمال‌سازی می‌شود.")
    with st.expander("گیت‌های بلوکی (حداقل امتیاز هر بلوک)"):
        gc = st.columns(4)
        for i, (b, v) in enumerate(CFG["block_gates"].items()):
            CFG["block_gates"][b] = gc[i].slider(BLOCK_FA[b], 0, 80, int(v))

# ---------------------------------------------------------------- scanner
with tab_scan:
    top = st.columns([2, 2, 2, 3])
    top[0].metric("محدوده رتبه", f"{ss['rank_from']} – {ss['rank_to']}")
    top[1].metric("تایم‌فریم", ss["timeframe"])
    top[2].metric("تأیید HTF", CFG["htf_map"][ss["timeframe"]])
    run = top[3].button("🚀 شروع اسکن", type="primary", use_container_width=True)

    if run or ss["auto_batch"]:
        try:
            src, universe = rank_universe(CFG["exchanges"], CFG["quote"], CFG["max_top_n"])
        except Exception as e:
            st.error(f"اتصال به صرافی برقرار نشد: {e}")
            st.stop()
        sel = universe[(universe["rank"] >= ss["rank_from"]) & (universe["rank"] <= ss["rank_to"])]
        if ss["auto_batch"]:
            batches = [sel.iloc[i:i + CFG["batch_size"]] for i in range(0, len(sel), CFG["batch_size"])]
        else:
            batches = [sel]
        st.caption(f"منبع داده: **{src}** — تعداد نمادها: **{len(sel)}** در **{len(batches)}** دسته")

        rows, details = [], {}
        prog = st.progress(0.0, text="در حال اسکن…")
        done, total = 0, max(len(sel), 1)
        for bi, batch in enumerate(batches, 1):
            for _, r in batch.iterrows():
                done += 1
                prog.progress(done / total, text=f"دسته {bi}/{len(batches)} — {r['symbol']}")
                try:
                    df = fetch_ohlcv(CFG["exchanges"], r["symbol"], ss["timeframe"], CFG["limit_candles"])
                    dh = fetch_ohlcv(CFG["exchanges"], r["symbol"], CFG["htf_map"][ss["timeframe"]], 300)
                    res = analyze(df, dh, CFG)
                except Exception:
                    continue
                details[r["symbol"]] = res
                rows.append({"رتبه": int(r["rank"]), "نماد": r["symbol"],
                             "جهت": {"long": "خرید", "short": "فروش"}.get(res["direction"], "—"),
                             "امتیاز": round(res["score"], 1),
                             "روند HTF": {"long": "صعودی", "short": "نزولی", "neutral": "خنثی"}[res["htf_bias"]],
                             "R:R": round(res["plan"]["rr"], 2) if res["plan"] else None,
                             "سیگنال": "✅" if res["signal"] else "—", "علت": res["reason"]})
        prog.empty()
        ss["scan_rows"], ss["details"], ss["auto_batch"] = rows, details, False

    rows, details = ss["scan_rows"], ss["details"]
    if rows:
        table = pd.DataFrame(rows).sort_values(["سیگنال", "امتیاز"], ascending=[True, False])
        conf = table[table["سیگنال"] == "✅"]
        st.markdown(f"#### ✅ سیگنال‌های تأییدشده: {len(conf)}")
        if conf.empty:
            near = table.head(5)
            st.warning("سیگنالی یافت نشد. نزدیک‌ترین کاندیدها و علت رد شدن:")
            st.dataframe(near[["رتبه", "نماد", "جهت", "امتیاز", "روند HTF", "علت"]], use_container_width=True, hide_index=True)
        else:
            def style(df):
                def col(v):
                    if v == "خرید" or v == "صعودی":
                        return f"color:{GREEN};font-weight:700"
                    if v == "فروش" or v == "نزولی":
                        return f"color:{RED};font-weight:700"
                    return ""
                s = df.style.map(col, subset=["جهت", "روند HTF"])
                return s.map(lambda v: f"color:{GREEN if v >= 50 else RED};font-weight:700", subset=["امتیاز"])
            st.dataframe(style(conf), use_container_width=True, hide_index=True)

        with st.expander("جدول کامل اسکن"):
            st.dataframe(table, use_container_width=True, hide_index=True)

        pick = st.selectbox("مشاهده جزئیات نماد", list(details.keys()))
        res = details[pick]
        direction = res["direction"]
        dir_fa = {"long": "خرید", "short": "فروش"}.get(direction, "بدون جهت")
        col = GREEN if direction == "long" else RED if direction == "short" else GREY
        card(f'<span class="badge" style="background:{col}22;color:{col}">{dir_fa}</span>'
             f'<span class="big" style="color:{col};margin-inline-start:12px">{res["score"]:.1f}</span>'
             f'<span style="color:#9aa7bd"> / 100 — {pick} — وضعیت: {res["reason"]}</span>')

        g1, g2, g3 = st.columns([1.1, 1, 1.4])
        with g1:
            st.plotly_chart(gauge(res["score"], direction), use_container_width=True)
            if res["plan"]:
                p = res["plan"]
                st.markdown(
                    f'<div class="card">ورود: <b>{p["entry"]:.6g}</b><br>'
                    f'حد ضرر: <b style="color:{RED}">{p["sl"]:.6g}</b><br>'
                    f'هدف: <b style="color:{GREEN}">{p["tp"]:.6g}</b><br>'
                    f'R:R: <b style="color:{GREEN if p["rr"] >= CFG["min_rr"] else RED}">{p["rr"]:.2f}</b></div>',
                    unsafe_allow_html=True)
        with g2:
            st.plotly_chart(blocks_radar(res["results"][direction or "long"]["blocks"]), use_container_width=True)
            if res["warnings"]:
                st.markdown('<div class="card"><b>⚠️ هشدارها</b><ul>' +
                            "".join(f"<li>{w}</li>" for w in res["warnings"]) + "</ul></div>",
                            unsafe_allow_html=True)
        with g3:
            st.plotly_chart(components_bar(res["results"][direction or "long"]["components"]), use_container_width=True)

        st.plotly_chart(price_chart(res["df"], pick, res["plan"], direction), use_container_width=True)
    else:
        card("برای شروع، محدوده رتبه و تایم‌فریم را در تب <b>تنظیمات</b> انتخاب کنید و سپس «🚀 شروع اسکن» را بزنید.")

with tab_help:
    st.markdown("""
#### منطق سیستم
- **۱۰ مؤلفه** در **۴ بلوک** (روند، مومنتوم، حجم، ساختار) با وزن‌دهی و نرمال‌سازی ۰–۱۰۰.
- **فیلتر کالمن (Local Linear Trend)** روی قیمت اجرا می‌شود و *شیب* (مشتق هموارشده) را می‌دهد؛
  این جایگزین کم‌نویزِ `diff()` است و whipsaw را به‌شدت کاهش می‌دهد.
- **فیلتر تایم‌فریم بالاتر:** سیگنال خلاف روند HTF هرگز اعلام نمی‌شود؛ HTF خنثی هم = بدون سیگنال.
- **گیت‌های بلوکی + شرط R:R ≥ حد تعیین‌شده** برای حذف سیگنال‌های ضعیف.
- رنگ‌بندی: بالای ۵۰ سبز (خرید) و زیر ۵۰ قرمز (فروش).
""")
