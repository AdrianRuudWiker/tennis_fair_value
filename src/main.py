"""
main.py
Tennis In-Game Fair Value Calculator.

Takes player hold rates, surface, gender, and who serves first as inputs.
Pre-match site odds are used as the anchor; the Markov chain computes how
each in-match game state shifts that probability.

Usage:
  python main.py          — print the pre-computed table and export CSV
  python main.py --live   — interactive live-update mode for in-match use
"""

import os
import sys
from datetime import datetime

import pandas as pd

from markov import set_win_probability
from match import match_win_from_set_score


# ---- SURFACE OPTIONS ----
SURFACES = ["Slow Clay", "Clay (Typical)", "Hard Court", "Grass/Fast Hard"]

# ---- GENDER OPTIONS ----
# Men hold serve more often than women, especially on fast surfaces.
# Typical ranges to guide your inputs:
#
#   Men:
#     Slow Clay:       72-76%    Hard Court:      80-85%
#     Clay (Typical):  75-80%    Grass/Fast Hard: 85-92%
#
#   Women:
#     Slow Clay:       55-60%    Hard Court:      60-66%
#     Clay (Typical):  58-63%    Grass/Fast Hard: 62-68%
GENDERS = ["Men", "Women"]

# ---- USER INPUTS: edit these before each match ----
SURFACE      = "Clay (Typical)"
GENDER       = "Men"
FIRST_SERVER = "fav"   # Who serves the first game: "fav" or "und"

# Hold rates per surface for each player.
# Source: service games won % from Tennis Abstract / ultimatetennisstatistics.com
FAV_HOLD_RATES = {
    "Slow Clay":       0.62,
    "Clay (Typical)":  0.68,
    "Hard Court":      0.72,
    "Grass/Fast Hard": 0.78,
}

UND_HOLD_RATES = {
    "Slow Clay":       0.58,
    "Clay (Typical)":  0.64,
    "Hard Court":      0.68,
    "Grass/Fast Hard": 0.72,
}


def validate_inputs(fav_hold, und_hold, surface, gender, prematch_odds, first_server):
    """
    Validate all model inputs before running.
    Raises ValueError with a clear message if anything is out of range.
    """
    if not (0.0 <= fav_hold <= 1.0):
        raise ValueError(f"fav_hold must be in [0, 1], got {fav_hold}")
    if not (0.0 <= und_hold <= 1.0):
        raise ValueError(f"und_hold must be in [0, 1], got {und_hold}")
    if surface not in SURFACES:
        raise ValueError(
            f"Unknown surface '{surface}'. Choose from: {SURFACES}"
        )
    if gender not in GENDERS:
        raise ValueError(
            f"Unknown gender '{gender}'. Choose from: {GENDERS}"
        )
    if not (0.0 < prematch_odds < 1.0):
        raise ValueError(
            f"prematch_odds must be in (0, 1), got {prematch_odds}"
        )
    if first_server not in ("fav", "und"):
        raise ValueError(
            f"first_server must be 'fav' or 'und', got '{first_server}'"
        )


def _other(server):
    """Return the other server."""
    return "und" if server == "fav" else "fav"


def run_model(fav_hold, und_hold, prematch_odds, first_server="fav"):
    """
    Run the full model for all first-set game states.
    Returns a list of result rows, with the pre-match row always first.

    Match win probabilities are site-anchored:
      match_win_a = prematch_odds + (model_at_state - model_pre_match)

    This uses the market's pre-match assessment as the absolute level,
    and the Markov chain only to compute relative shifts from that anchor.
    """
    # Neutral set win — used for future sets and as the set-win baseline.
    p_set_neutral      = set_win_probability(fav_hold, und_hold, (0, 0, first_server))
    p_match_if_win_set  = match_win_from_set_score(1, 0, p_set_neutral)
    p_match_if_lose_set = match_win_from_set_score(0, 1, p_set_neutral)

    def model_match_win(game_state):
        """Model's raw (un-anchored) match win from a game state."""
        p_set = set_win_probability(fav_hold, und_hold, game_state)
        p_match = (
            p_set         * p_match_if_win_set
            + (1 - p_set) * p_match_if_lose_set
        )
        return p_set, p_match

    # Model's own pre-match baseline — used only to compute shifts.
    _, p_match_model_pre = model_match_win((0, 0, first_server))

    def anchored(p_match_model):
        """Shift model's match win by the same amount from the site's anchor."""
        return prematch_odds + (p_match_model - p_match_model_pre)

    # Mid-set states. Break states reflect serve alternation from first_server.
    mid_set_states = {
        "Pre-match (0-0)":   (0, 0, first_server),
        "Fav up 1 break":    (1, 0, _other(first_server)),
        "Fav down 1 break":  (0, 1, first_server),
        "Fav up 2 breaks":   (2, 0, first_server),
        "Fav down 2 breaks": (0, 2, _other(first_server)),
    }

    results = []
    for label, state in mid_set_states.items():
        p_set, p_match_model = model_match_win(state)

        if label == "Pre-match (0-0)":
            # Pre-match row: show site's odds directly, delta is n/a.
            delta_set  = None
            match_win_a = prematch_odds
        else:
            delta_set   = p_set - p_set_neutral
            match_win_a = anchored(p_match_model)

        results.append({
            "state":       label,
            "set_win":     p_set,
            "delta_set":   delta_set,
            "match_win_a": match_win_a,
            "match_win_b": 1 - match_win_a,
        })

    # Won / lost first set — set is over so set_win and delta_set are n/a.
    match_win_won  = anchored(p_match_if_win_set)
    match_win_lost = anchored(p_match_if_lose_set)

    results.append({
        "state":       "Fav WINS 1st set",
        "set_win":     None,
        "delta_set":   None,
        "match_win_a": match_win_won,
        "match_win_b": 1 - match_win_won,
    })
    results.append({
        "state":       "Fav LOSES 1st set",
        "set_win":     None,
        "delta_set":   None,
        "match_win_a": match_win_lost,
        "match_win_b": 1 - match_win_lost,
    })

    return results


def print_results(results, fav_hold, und_hold, surface, gender,
                  prematch_odds, first_server):
    """Print formatted output table matching the supervisor's layout."""
    model_pre = results[0]["set_win"]

    print()
    print("=" * 75)
    print("  TENNIS IN-GAME FAIR VALUE CALCULATOR")
    print("=" * 75)
    print(f"  Surface:          {surface}  ({gender})")
    print(f"  First server:     {first_server}")
    print(f"  Fav hold rate:    {fav_hold:.1%}")
    print(f"  Und hold rate:    {und_hold:.1%}")
    print(f"  Pre-match odds:   {prematch_odds:.1%} (betting site, anchor)")
    print(f"  Model set win:    {model_pre:.1%} (neutral 0-0 set win from hold rates)")
    print("=" * 75)
    print()
    print(f"  {'Match State':<22} {'Set Win%(A)':>11} {'Delta Set':>10} "
          f"{'Match Win%(A)':>14} {'Match Win%(B)':>14}")
    print("  " + "-" * 73)

    for r in results:
        set_str   = f"{r['set_win']:.1%}"  if r["set_win"]   is not None else "--"
        dset_str  = f"{r['delta_set']:+.1%}" if r["delta_set"] is not None else "--"
        print(f"  {r['state']:<22} {set_str:>11} {dset_str:>10} "
              f"{r['match_win_a']:>14.1%} {r['match_win_b']:>14.1%}")

    print()


def live_mode(fav_hold, und_hold, surface, gender, first_server, prematch_odds):
    """
    Interactive loop: after each game, enter the current score and
    the model prints updated site-anchored probabilities immediately.
    Optionally append the live betting odds to see the edge.

    Input format:  fav_games und_games server [live_odds_a]
    Examples:      3 2 fav       5 4 und 0.71
    """
    p_set_neutral      = set_win_probability(fav_hold, und_hold, (0, 0, first_server))
    p_match_if_win_set  = match_win_from_set_score(1, 0, p_set_neutral)
    p_match_if_lose_set = match_win_from_set_score(0, 1, p_set_neutral)

    # Model's own pre-match — needed to compute shifts.
    p_set_pre_raw = p_set_neutral
    p_match_model_pre = (
        p_set_pre_raw         * p_match_if_win_set
        + (1 - p_set_pre_raw) * p_match_if_lose_set
    )

    print()
    print("=" * 60)
    print("  LIVE MODE")
    print(f"  Surface: {surface} ({gender})  |  First server: {first_server}")
    print(f"  Fav hold: {fav_hold:.1%}  |  Und hold: {und_hold:.1%}")
    print(f"  Site anchor: {prematch_odds:.1%}")
    print("=" * 60)
    print("  Format:  fav_games und_games server [live_odds_a]")
    print("  Example: 3 2 fav        or        3 2 fav 0.71")
    print("  Type 'q' to quit.")
    print()

    while True:
        try:
            raw = input("  Score > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if raw in ("q", "quit", "exit"):
            break

        parts = raw.split()
        if len(parts) not in (3, 4):
            print("  Expected: fav_games und_games server [live_odds_a]")
            continue

        try:
            fav_g       = int(parts[0])
            und_g       = int(parts[1])
            server      = parts[2]
            live_odds_a = float(parts[3]) if len(parts) == 4 else None
        except ValueError:
            print("  Could not parse. Try: 3 2 fav  or  3 2 fav 0.71")
            continue

        if server not in ("fav", "und"):
            print("  Server must be 'fav' or 'und'")
            continue

        if not (0 <= fav_g <= 7 and 0 <= und_g <= 7):
            print("  Game counts must be 0-7")
            continue

        p_set = set_win_probability(fav_hold, und_hold, (fav_g, und_g, server))
        p_match_model = (
            p_set         * p_match_if_win_set
            + (1 - p_set) * p_match_if_lose_set
        )
        p_match = prematch_odds + (p_match_model - p_match_model_pre)
        delta_set = p_set - p_set_neutral

        edge_str = ""
        if live_odds_a is not None:
            edge_str = f"   edge: {p_match - live_odds_a:+.1%}"

        print(f"  {fav_g}-{und_g} {server} srv  |  "
              f"set: {p_set:.1%} ({delta_set:+.1%})  "
              f"match A: {p_match:.1%}  match B: {1 - p_match:.1%}{edge_str}")


def export_csv(results, surface, gender, fav_hold, und_hold,
               prematch_odds, first_server):
    """
    Export the results table to a timestamped CSV in the outputs/ directory.
    Column layout matches the supervisor's Google Sheets template.
    """
    outputs_dir = os.path.join(os.path.dirname(__file__), "..", "outputs")
    os.makedirs(outputs_dir, exist_ok=True)

    timestamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_surface = (surface.replace(" ", "_").replace("/", "-")
                           .replace("(", "").replace(")", ""))
    filepath = os.path.join(outputs_dir,
                            f"tennis_fv_{safe_surface}_{timestamp}.csv")

    rows = []
    for r in results:
        rows.append({
            "Match State":    r["state"],
            "Set Win % (A)":  f"{r['set_win']:.1%}"   if r["set_win"]   is not None else "--",
            "Delta Set Win":  f"{r['delta_set']:+.1%}" if r["delta_set"] is not None else "--",
            "Match Win % (A)": f"{r['match_win_a']:.1%}",
            "Match Win % (B)": f"{r['match_win_b']:.1%}",
        })

    df = pd.DataFrame(rows)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        f.write(f"# Surface,{surface}\n")
        f.write(f"# Gender,{gender}\n")
        f.write(f"# First server,{first_server}\n")
        f.write(f"# Fav hold rate,{fav_hold:.1%}\n")
        f.write(f"# Und hold rate,{und_hold:.1%}\n")
        f.write(f"# Betting-site pre-match (anchor),{prematch_odds:.1%}\n")
        f.write(f"# Generated,{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("#\n")
        df.to_csv(f, index=False)

    print(f"  CSV saved to: {os.path.abspath(filepath)}")
    print()
    return filepath


if __name__ == "__main__":
    fav_hold = FAV_HOLD_RATES[SURFACE]
    und_hold = UND_HOLD_RATES[SURFACE]

    raw = input("  Betting-site pre-match odds for favourite (e.g. 0.64): ").strip()
    prematch_odds = float(raw)

    validate_inputs(fav_hold, und_hold, SURFACE, GENDER, prematch_odds, FIRST_SERVER)

    if "--live" in sys.argv:
        live_mode(fav_hold, und_hold, SURFACE, GENDER, FIRST_SERVER, prematch_odds)
    else:
        results = run_model(fav_hold, und_hold, prematch_odds, FIRST_SERVER)
        print_results(results, fav_hold, und_hold, SURFACE, GENDER,
                      prematch_odds, FIRST_SERVER)
        export_csv(results, SURFACE, GENDER, fav_hold, und_hold,
                   prematch_odds, FIRST_SERVER)
