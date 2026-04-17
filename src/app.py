"""
app.py
Streamlit UI for the Tennis In-Game Fair Value Calculator.

Layout:
  - Sidebar: all inputs (surface, hold rates, pre-match odds with auto-de-vig)
  - Main:    canonical first-set states table (mirrors the Sheets template)
             + live score lookup with model-vs-live edge metric
             + match-win-by-state bar chart

Run from the project root:
    streamlit run src/app.py
"""
import os
import sys

# Make src/ importable regardless of launch directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import streamlit as st

from main import run_model, SURFACES, GENDERS, FAV_HOLD_RATES, UND_HOLD_RATES
from markov import set_win_probability
from match import match_win_from_set_score
from states import is_terminal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def devig(fav_decimal: float, und_decimal: float) -> float:
    """Two decimal odds -> fair (margin-removed) favourite win probability."""
    p_fav_raw = 1.0 / fav_decimal
    p_und_raw = 1.0 / und_decimal
    return p_fav_raw / (p_fav_raw + p_und_raw)


def anchored_match_win(fav_hold, und_hold, state, first_server, prematch_odds):
    """Site-anchored match win % for an arbitrary mid-set state."""
    p_set_neutral = set_win_probability(fav_hold, und_hold, (0, 0, first_server))
    p_if_win  = match_win_from_set_score(1, 0, p_set_neutral)
    p_if_lose = match_win_from_set_score(0, 1, p_set_neutral)

    raw_pre  = p_set_neutral * p_if_win + (1 - p_set_neutral) * p_if_lose
    p_set    = set_win_probability(fav_hold, und_hold, state)
    raw_live = p_set * p_if_win + (1 - p_set) * p_if_lose

    return p_set, prematch_odds + (raw_live - raw_pre)


def color_delta(val):
    """Green for positive, red for negative, grey for blank."""
    if pd.isna(val):
        return "color: #888"
    if val > 0:
        return "color: #0a7d2f; font-weight: 600"
    if val < 0:
        return "color: #c0392b; font-weight: 600"
    return ""


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Tennis Fair Value",
    page_icon="🎾",
    layout="wide",
)

st.title("🎾 Tennis In-Game Fair Value Calculator")
st.caption(
    "Markov-chain model for best-of-3. Site-anchored match-win shifts "
    "for each first-set game state."
)


# ---------------------------------------------------------------------------
# Sidebar — inputs
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Inputs")

    surface = st.selectbox("Surface", SURFACES, index=1)
    gender = st.radio("Gender", GENDERS, horizontal=True)
    first_server = st.radio(
        "First server",
        options=["fav", "und"],
        horizontal=True,
        help="Who serves game 1, decided by the coin toss a few minutes before play.",
    )

    st.divider()
    st.subheader("Hold rates")
    fav_hold = st.slider(
        "Favourite hold %", 0.30, 0.99,
        FAV_HOLD_RATES.get(surface, 0.68), 0.01,
    )
    und_hold = st.slider(
        "Underdog hold %", 0.30, 0.99,
        UND_HOLD_RATES.get(surface, 0.62), 0.01,
    )

    st.divider()
    st.subheader("Pre-match odds")
    devig_mode = st.toggle(
        "Auto-de-vig from decimal pair",
        value=True,
        help="Paste the bookmaker's two decimal prices and the margin is removed automatically.",
    )
    if devig_mode:
        c_a, c_b = st.columns(2)
        fav_dec = c_a.number_input("Fav decimal", 1.01, 50.0, 1.56, 0.01)
        und_dec = c_b.number_input("Und decimal", 1.01, 50.0, 2.55, 0.01)
        prematch_odds = devig(fav_dec, und_dec)
        overround = (1.0 / fav_dec + 1.0 / und_dec) - 1.0
        st.caption(
            f"De-vigged fav win %: **{prematch_odds:.1%}** · "
            f"book overround: {overround:+.1%}"
        )
    else:
        prematch_odds = st.slider("Fav win % (fair)", 0.01, 0.99, 0.64, 0.01)


# ---------------------------------------------------------------------------
# Main — context strip + canonical table
# ---------------------------------------------------------------------------

top_a, top_b, top_c, top_d = st.columns(4)
top_a.metric("Surface", surface)
top_b.metric("Pre-match (anchor)", f"{prematch_odds:.1%}")
top_c.metric("Fav hold", f"{fav_hold:.1%}")
top_d.metric("Und hold", f"{und_hold:.1%}")

results = run_model(fav_hold, und_hold, prematch_odds, first_server)

num_df = pd.DataFrame([
    {
        "Match State":       r["state"],
        "Set Win %":         r["set_win"],
        "Match Win % (fav)": r["match_win_fav"],
        "Delta Match":       r["delta_match"],
    }
    for r in results
])

st.subheader("Canonical first-set states")

styled = (
    num_df.style
    .format({
        "Set Win %":         lambda v: "—" if pd.isna(v) else f"{v:.1%}",
        "Match Win % (fav)": "{:.1%}",
        "Delta Match":       lambda v: "—" if pd.isna(v) else f"{v:+.1%}",
    })
    .map(color_delta, subset=["Delta Match"])
)
st.dataframe(styled, hide_index=True, width="stretch")

# Copy-for-Sheets block — identical formatting to the visible table.
display_rows = [
    {
        "Match State":       r["state"],
        "Set Win %":         "—" if r["set_win"] is None else f"{r['set_win']:.1%}",
        "Match Win % (fav)": f"{r['match_win_fav']:.1%}",
        "Delta Match":       "—" if r["delta_match"] is None else f"{r['delta_match']:+.1%}",
    }
    for r in results
]
tsv = pd.DataFrame(display_rows).to_csv(sep="\t", index=False)
with st.expander("📋 Copy-for-Sheets (tab-separated — paste into the template)"):
    st.code(tsv, language="text")


# ---------------------------------------------------------------------------
# Live score lookup
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Live score lookup")
st.caption(
    "Enter any non-terminal score and the current live odds to see the model's "
    "match % and the signed edge against the de-vigged live price."
)

score_col1, score_col2, score_col3 = st.columns([1, 1, 1])
fav_g = score_col1.number_input("Fav games", 0, 7, 3, 1)
und_g = score_col2.number_input("Und games", 0, 7, 2, 1)
live_server = score_col3.radio(
    "Serving now",
    options=["fav", "und"],
    horizontal=True,
    key="live_server",
)

live_mode_devig = st.toggle(
    "Live odds as decimal pair (auto-de-vig)",
    value=True,
    key="live_devig",
)
if live_mode_devig:
    lc_a, lc_b = st.columns(2)
    live_fav_dec = lc_a.number_input("Live fav dec", 1.01, 50.0, 1.80, 0.01)
    live_und_dec = lc_b.number_input("Live und dec", 1.01, 50.0, 2.20, 0.01)
    live_match_odds = devig(live_fav_dec, live_und_dec)
else:
    live_match_odds = st.slider("Live fair match %", 0.01, 0.99, 0.60, 0.01)

state = (int(fav_g), int(und_g), live_server)
if is_terminal(state):
    st.warning(
        f"**{fav_g}-{und_g}** is a completed set. "
        "Use the *WINS/LOSES 1st set* row from the canonical table above."
    )
else:
    p_set_live, match_win_fav = anchored_match_win(
        fav_hold, und_hold, state, first_server, prematch_odds,
    )
    delta = match_win_fav - prematch_odds
    edge = match_win_fav - live_match_odds

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Set Win % (fav)",     f"{p_set_live:.1%}")
    m2.metric("Match Win % (fav)",   f"{match_win_fav:.1%}", delta=f"{delta:+.1%}")
    m3.metric("Live fair match %",   f"{live_match_odds:.1%}")
    m4.metric("Edge (model − live)", f"{edge:+.1%}")

    if abs(edge) < 0.03:
        st.info(f"Edge of {edge:+.1%} is inside model noise (~3 %). No actionable signal.")
    elif edge > 0:
        st.success(f"Model is {edge:+.1%} above live — potential value on the **favourite**.")
    else:
        st.success(f"Model is {edge:+.1%} below live — potential value on the **underdog**.")


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Match win % by first-set state")
chart_df = num_df.set_index("Match State")[["Match Win % (fav)"]]
st.bar_chart(chart_df, width="stretch", horizontal=True)
