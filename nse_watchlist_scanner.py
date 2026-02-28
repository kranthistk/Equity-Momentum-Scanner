import streamlit as st
import pandas as pd
from curl_cffi import requests
import time
from datetime import datetime
import pytz

st.set_page_config(page_title="NSE Watchlist Scanner", layout="wide")

st.title("📊 NSE Watchlist Momentum Scanner")
st.markdown("Auto-updates every **30 seconds** | Tracking select equity stocks")

# ── Watchlist ──────────────────────────────────────────────────────────────────
# Note: Oracle Financial Services trades as OFSS on NSE, not OFSBANK.
# Update the symbol below if needed.
WATCHLIST = {
    "GODREJPROP": "Godrej Properties",
    "OFSS":       "Oracle Financial Services",   # ← was OFSBANK in your request
    "ZYDUSLIFE":  "Zydus Life Sciences",
    "VOLTAS":     "Voltas Limited",
    "POLICYBZR":  "Policy Bazaar",
    "ASTRAL":     "Astral Limited",
    "AMBER":     "Amber Enterprises",
}
# ──────────────────────────────────────────────────────────────────────────────


def make_session() -> requests.Session:
    """Create a fresh browser-impersonating session and seed NSE cookies."""
    session = requests.Session()
    session.get("https://www.nseindia.com", impersonate="chrome120", timeout=12)
    return session


def fetch_quote(session: requests.Session, symbol: str) -> dict | None:
    """
    Fetch live quote + trade-info section for a single NSE symbol.
    Returns a flat dict of fields we care about, or None on failure.
    """
    base_url  = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
    quote_url = f"{base_url}&timestamp={int(time.time())}"
    trade_url = f"{base_url}&section=trade_info&timestamp={int(time.time())}"

    try:
        # ── Primary quote ──────────────────────────────────────────────────
        resp = session.get(quote_url, impersonate="chrome120", timeout=10)
        if resp.status_code != 200:
            return None
        data       = resp.json()
        price_info = data.get("priceInfo", {})
        sec_info   = data.get("securityInfo", {})

        ltp      = price_info.get("lastPrice")
        open_p   = price_info.get("open")
        pchange  = price_info.get("pChange")
        day_high = price_info.get("intraDayHighLow", {}).get("max")
        day_low  = price_info.get("intraDayHighLow", {}).get("min")
        week52_h = price_info.get("weekHighLow", {}).get("max")
        week52_l = price_info.get("weekHighLow", {}).get("min")
        vwap     = price_info.get("vwap")

        # ── Open-based % changes ───────────────────────────────────────────
        def pct_from_open(val):
            try:
                if open_p and float(open_p) != 0 and val is not None:
                    return ((float(val) - float(open_p)) / float(open_p)) * 100
            except (TypeError, ValueError):
                pass
            return None

        # ── Today's volume ─────────────────────────────────────────────────
        today_vol = data.get("totalTradedVolume") or sec_info.get("tradedVolume")

        # ── Avg daily volume via trade_info section ────────────────────────
        avg_vol = None
        try:
            t_resp = session.get(trade_url, impersonate="chrome120", timeout=10)
            if t_resp.status_code == 200:
                t_data     = t_resp.json()
                trade_sec  = t_data.get("tradeInfo", {})
                mkt_trade  = t_data.get("marketDeptOrderBook", {}).get("tradeInfo", {})
                # NSE uses different keys across endpoints — try all known locations
                avg_vol = (
                    trade_sec.get("cmAverageTradedVolume")
                    or trade_sec.get("averageTradedVolume")
                    or mkt_trade.get("cmAverageTradedVolume")
                    or t_data.get("cmAverageTradedVolume")
                )
        except Exception:
            pass  # avg vol stays None — shown as "—" in table

        return {
            "Symbol":        symbol,
            "Company":       WATCHLIST[symbol],
            "LTP":           ltp,
            "% Change":      pchange,
            "Open":          open_p,
            "Open→LTP %":    pct_from_open(ltp),
            "High→LTP %":    (((float(ltp) - float(day_high)) / float(day_high)) * 100) if day_high and ltp else None,
            "Low→LTP %":     (((float(ltp) - float(day_low))  / float(day_low))  * 100) if day_low  and ltp else None,
            "VWAP":          vwap,
            "High":          day_high,
            "Low":           day_low,
            "52W High":      week52_h,
            "52W Low":       week52_l,
        }

    except Exception as exc:
        st.warning(f"⚠️ Could not fetch {symbol}: {exc}")
        return None


def color_pchange(val):
    """Cell-level colour for % Change column."""
    if pd.isna(val):
        return ""
    color = "#1a7a1a" if val > 0 else "#c0392b" if val < 0 else "#555"
    return f"color: {color}; font-weight: bold"


def color_vol(val):
    """Cell-level colour for Vol Change %."""
    if pd.isna(val):
        return ""
    color = "#1a6faa" if val > 0 else "#888"
    return f"color: {color}; font-weight: bold"


def color_vs_52w_high(val):
    """Cell colour for vs 52W High % — closer to 0 means near the high (bullish)."""
    if pd.isna(val):
        return ""
    # val is negative (LTP below 52W high) or 0
    if val >= -5:
        return "background-color: #d4edda; color: #155724; font-weight: bold"
    elif val >= -15:
        return "background-color: #fff3cd; color: #856404; font-weight: bold"
    else:
        return "background-color: #f8d7da; color: #721c24; font-weight: bold"


def color_vs_52w_low(val):
    """Cell colour for vs 52W Low % — farther from 0 means well above the low (bullish)."""
    if pd.isna(val):
        return ""
    # val is positive (LTP above 52W low)
    if val >= 30:
        return "background-color: #d4edda; color: #155724; font-weight: bold"
    elif val >= 10:
        return "background-color: #fff3cd; color: #856404; font-weight: bold"
    else:
        return "background-color: #f8d7da; color: #721c24; font-weight: bold"


def dist_from_52w(row, col_ltp, col_ref, direction="high"):
    """Return % distance of LTP from 52W High or Low."""
    ltp = row[col_ltp]
    ref = row[col_ref]
    if pd.isna(ltp) or pd.isna(ref) or ref == 0:
        return None
    return ((ltp - ref) / ref) * 100


@st.fragment(run_every=30)
def watchlist_fragment():
    ist = pytz.timezone("Asia/Kolkata")
    current_time = datetime.now(ist).strftime("%H:%M:%S")
    st.caption(f"🔄 Last refreshed: **{current_time} IST**")

    # One shared session for all requests → fewer round-trips
    with st.spinner("Fetching quotes from NSE…"):
        session = make_session()
        rows = []
        for symbol in WATCHLIST:
            quote = fetch_quote(session, symbol)
            if quote:
                rows.append(quote)
            time.sleep(0.3)   # small delay between hits to be polite

    if not rows:
        st.error("❌ Could not fetch any data. NSE may be blocking requests or markets are closed.")
        return

    df = pd.DataFrame(rows)

    # ── Numeric coercion ──────────────────────────────────────────────────────
    numeric_cols = [
        "LTP", "% Change", "Open", "Open→LTP %", "High→LTP %", "Low→LTP %",
        "VWAP", "High", "Low", "52W High", "52W Low"
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # ── Derived columns ───────────────────────────────────────────────────────
    df["vs 52W High %"] = df.apply(
        lambda r: dist_from_52w(r, "LTP", "52W High", "high"), axis=1
    )
    df["vs 52W Low %"] = df.apply(
        lambda r: dist_from_52w(r, "LTP", "52W Low", "low"), axis=1
    )

    # ── Sort by % Change descending ───────────────────────────────────────────
    df = df.sort_values("% Change", ascending=False).reset_index(drop=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 1 – Compact snapshot cards (top of page)
    # ═══════════════════════════════════════════════════════════════════════════
    st.subheader("📌 Live Snapshot")
    card_cols = st.columns(len(df))
    for i, row in df.iterrows():
        pchg = row["% Change"]
        arrow = "▲" if pchg > 0 else "▼" if pchg < 0 else "■"
        bg    = "#d4edda" if pchg > 0 else "#f8d7da" if pchg < 0 else "#e9ecef"
        txt   = "#155724" if pchg > 0 else "#721c24" if pchg < 0 else "#495057"

        with card_cols[i]:
            st.markdown(
                f"""
                <div style="background:{bg};border-radius:10px;padding:14px 10px;text-align:center;">
                  <div style="font-size:13px;font-weight:700;color:#333;">{row['Symbol']}</div>
                  <div style="font-size:11px;color:#666;margin-bottom:6px;">{row['Company']}</div>
                  <div style="font-size:20px;font-weight:800;color:{txt};">₹{row['LTP']:,.2f}</div>
                  <div style="font-size:15px;font-weight:700;color:{txt};">{arrow} {pchg:+.2f}%</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 2 – Full detail table
    # ═══════════════════════════════════════════════════════════════════════════
    st.subheader("📋 Detailed Table  *(sorted by % Change)*")

    display_cols = [
        "Symbol", "Company",
        # ── Price block ──────────────────────────────────────────────────────
        "LTP", "% Change", "Open", "VWAP",
        # ── Open-based moves ─────────────────────────────────────────────────
        "Open→LTP %", "High→LTP %", "Low→LTP %",
        # ── Range ────────────────────────────────────────────────────────────
        "High", "Low",
        # ── Volume ───────────────────────────────────────────────────────────
        # ── 52-week context ───────────────────────────────────────────────────
        "52W High", "52W Low", "vs 52W High %", "vs 52W Low %",
    ]

    fmt = {
        "LTP":           "₹{:.2f}",
        "% Change":      "{:+.2f}%",
        "Open":          "₹{:.2f}",
        "VWAP":          "₹{:.2f}",
        "High":          "₹{:.2f}",
        "Low":           "₹{:.2f}",
        "Open→LTP %":    "{:+.2f}%",
        "High→LTP %":    "{:+.2f}%",
        "Low→LTP %":     "{:+.2f}%",
        "52W High":      "₹{:.2f}",
        "52W Low":       "₹{:.2f}",
        "vs 52W High %": "{:+.2f}%",
        "vs 52W Low %":  "{:+.2f}%",
    }

    def color_open_move(val):
        """Green positive / red negative for open-based % cols."""
        if pd.isna(val):
            return ""
        if val > 0:
            return "color: #1a7a1a; font-weight: bold"
        elif val < 0:
            return "color: #c0392b; font-weight: bold"
        return ""


    table_df = df[display_cols].copy()

    styled = (
        table_df
        .style
        .format(fmt, na_rep="—")
        .applymap(color_pchange,   subset=["% Change"])
        .applymap(color_open_move, subset=["Open→LTP %", "High→LTP %", "Low→LTP %"])
        .applymap(color_vs_52w_high, subset=["vs 52W High %"])
        .applymap(color_vs_52w_low,  subset=["vs 52W Low %"])
        .set_properties(**{"text-align": "center"})
    )

    st.dataframe(styled, use_container_width=True, hide_index=True, height=280)

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 3 – Range meter (High / Low / LTP bar)
    # ═══════════════════════════════════════════════════════════════════════════
    st.subheader("📏 Intraday Range Position")
    range_cols = st.columns(len(df))
    for i, row in df.iterrows():
        low, high, ltp = row["Low"], row["High"], row["LTP"]
        if pd.isna(low) or pd.isna(high) or high == low:
            with range_cols[i]:
                st.caption(f"{row['Symbol']}: range N/A")
            continue

        pct_pos = int(((ltp - low) / (high - low)) * 100)
        bar_color = "#28a745" if pct_pos >= 50 else "#dc3545"

        with range_cols[i]:
            st.markdown(f"**{row['Symbol']}** — {pct_pos}% of range")
            st.progress(pct_pos / 100)
            st.caption(f"L ₹{low:.1f}  |  ₹{ltp:.1f}  |  H ₹{high:.1f}")


# ── Entry point ────────────────────────────────────────────────────────────────
watchlist_fragment()
