"""
test_sanity.py
Sanity checks for the tennis fair value model.

Every test maps to a property the model must satisfy by construction.
Run with: pytest tests/ -v  (from the project root)
"""

import pytest
from markov import set_win_probability
from match import match_win_from_set_score
from main import run_model

TOLERANCE = 1e-9


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _neutral_set_win(fav_hold, und_hold):
    return set_win_probability(fav_hold, und_hold, (0, 0, "fav"))


def _rows(fav_hold=0.68, und_hold=0.62, prematch_odds=0.64):
    return run_model(fav_hold, und_hold, prematch_odds, first_server="fav")


# ---------------------------------------------------------------------------
# 1. Equal hold rates → 50 % set win
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("h", [0.55, 0.65, 0.75, 0.85])
def test_equal_holds_set_win_50pct(h):
    """Equal hold rates must yield exactly 0.5 set win probability."""
    p = _neutral_set_win(h, h)
    assert abs(p - 0.5) < TOLERANCE, f"Expected 0.5, got {p} (h={h})"


# ---------------------------------------------------------------------------
# 2. Pre-match row is anchored to site odds, not model output
# ---------------------------------------------------------------------------

def test_prematch_row_anchored_to_site_odds():
    """The pre-match row match_win_fav must equal prematch_odds exactly."""
    for odds in (0.50, 0.60, 0.64, 0.75):
        rows = _rows(prematch_odds=odds)
        assert abs(rows[0]["match_win_fav"] - odds) < TOLERANCE, (
            f"Pre-match row should show {odds:.2f}, got {rows[0]['match_win_fav']:.6f}"
        )


def test_prematch_row_delta_match_is_none():
    """Pre-match row has no delta_match (it IS the anchor)."""
    rows = _rows()
    assert rows[0]["delta_match"] is None


# ---------------------------------------------------------------------------
# 3. Monotonicity: up states > neutral > down states (set win level)
# ---------------------------------------------------------------------------

def test_up_states_above_neutral_set_win():
    """Set win: up_1 > neutral and up_2 > up_1."""
    fav_hold, und_hold = 0.68, 0.62

    neutral = _neutral_set_win(fav_hold, und_hold)
    up_1    = set_win_probability(fav_hold, und_hold, (1, 0, "und"))
    up_2    = set_win_probability(fav_hold, und_hold, (2, 0, "fav"))

    assert up_1 > neutral, f"up_1 ({up_1:.4f}) should exceed neutral ({neutral:.4f})"
    assert up_2 > up_1,    f"up_2 ({up_2:.4f}) should exceed up_1 ({up_1:.4f})"


def test_down_states_below_neutral_set_win():
    """Set win: down_1 < neutral and down_2 < down_1."""
    fav_hold, und_hold = 0.68, 0.62

    neutral = _neutral_set_win(fav_hold, und_hold)
    down_1  = set_win_probability(fav_hold, und_hold, (0, 1, "fav"))
    down_2  = set_win_probability(fav_hold, und_hold, (0, 2, "und"))

    assert down_1 < neutral, f"down_1 ({down_1:.4f}) should be below neutral ({neutral:.4f})"
    assert down_2 < down_1,  f"down_2 ({down_2:.4f}) should be below down_1 ({down_1:.4f})"


# ---------------------------------------------------------------------------
# 4. delta_match is positive for up states, negative for down states, and
#    monotone: 2br > 1br > 0 > -1br > -2br. Also holds for set-result rows.
# ---------------------------------------------------------------------------

def test_delta_match_signs_and_ordering():
    """delta_match must be ordered: won > up2 > up1 > 0 > down1 > down2 > lost."""
    rows = {r["state"]: r for r in _rows()}

    d_up1    = rows["Fav up 1 break"]["delta_match"]
    d_up2    = rows["Fav up 2 breaks"]["delta_match"]
    d_down1  = rows["Fav down 1 break"]["delta_match"]
    d_down2  = rows["Fav down 2 breaks"]["delta_match"]
    d_won    = rows["Fav WINS 1st set"]["delta_match"]
    d_lost   = rows["Fav LOSES 1st set"]["delta_match"]

    assert d_won > d_up2 > d_up1 > 0 > d_down1 > d_down2 > d_lost, (
        f"Ordering broken: won={d_won:.4f} up2={d_up2:.4f} up1={d_up1:.4f} "
        f"down1={d_down1:.4f} down2={d_down2:.4f} lost={d_lost:.4f}"
    )


# ---------------------------------------------------------------------------
# 5. Mirror symmetry with equal holds
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("h", [0.55, 0.65, 0.75])
def test_mirror_symmetry_equal_holds(h):
    """
    With equal hold rates:
      P(win | up 1 break) + P(win | down 1 break) == 1.0  (set level)
    """
    up_1   = set_win_probability(h, h, (1, 0, "und"))
    down_1 = set_win_probability(h, h, (0, 1, "fav"))
    total  = up_1 + down_1
    assert abs(total - 1.0) < TOLERANCE, (
        f"Mirror symmetry violated: up_1={up_1:.6f}, down_1={down_1:.6f}, "
        f"sum={total:.6f}"
    )


# ---------------------------------------------------------------------------
# 6. Site-anchoring: match_win_fav = prematch_odds + model_shift
# ---------------------------------------------------------------------------

def test_site_anchoring_is_correct():
    """
    For each non-pre-match row:
      match_win_fav == prematch_odds + (model_at_state - model_pre_match)
    """
    fav_hold, und_hold, prematch_odds = 0.68, 0.62, 0.64

    p_set_neutral      = set_win_probability(fav_hold, und_hold, (0, 0, "fav"))
    p_match_if_win_set  = match_win_from_set_score(1, 0, p_set_neutral)
    p_match_if_lose_set = match_win_from_set_score(0, 1, p_set_neutral)

    def raw_match(state):
        p = set_win_probability(fav_hold, und_hold, state)
        return p * p_match_if_win_set + (1 - p) * p_match_if_lose_set

    model_pre = raw_match((0, 0, "fav"))
    rows = run_model(fav_hold, und_hold, prematch_odds, first_server="fav")

    states_to_game_states = {
        "Fav up 1 break":    (1, 0, "und"),
        "Fav down 1 break":  (0, 1, "fav"),
        "Fav up 2 breaks":   (2, 0, "und"),
        "Fav down 2 breaks": (0, 2, "fav"),
    }

    for r in rows[1:5]:  # mid-set rows only
        state = states_to_game_states[r["state"]]
        expected = prematch_odds + (raw_match(state) - model_pre)
        assert abs(r["match_win_fav"] - expected) < TOLERANCE, (
            f"Row '{r['state']}': match_win_fav={r['match_win_fav']:.6f}, "
            f"expected={expected:.6f}"
        )


# ---------------------------------------------------------------------------
# 8. Edge cases: hold rates at extremes must not crash
# ---------------------------------------------------------------------------

def test_zero_hold_rates_no_crash():
    """Both hold rates = 0.0 should not raise (guards ZeroDivisionError)."""
    p = set_win_probability(0.0, 0.0, (0, 0, "fav"))
    assert 0.0 <= p <= 1.0, f"Expected probability in [0,1], got {p}"


def test_unit_hold_rates_no_crash():
    """Both hold rates = 1.0 (every game goes to tiebreak) should not crash."""
    p = set_win_probability(1.0, 1.0, (0, 0, "fav"))
    assert abs(p - 0.5) < TOLERANCE, (
        f"Equal unit hold rates should yield 0.5, got {p}"
    )


def test_extreme_favourite_no_crash():
    """Near-certain favourite should return a high probability without crashing."""
    p = set_win_probability(0.99, 0.01, (0, 0, "fav"))
    assert 0.9 < p <= 1.0, f"Expected p near 1.0, got {p}"


# ---------------------------------------------------------------------------
# 9. delta_match identity: delta_match == match_win_fav - prematch_odds
# ---------------------------------------------------------------------------

def test_delta_match_equals_anchored_shift():
    """For every non-pre-match row, delta_match must equal match_win_fav - prematch_odds."""
    odds = 0.64
    rows = _rows(prematch_odds=odds)
    for r in rows[1:]:  # skip the pre-match anchor row
        expected = r["match_win_fav"] - odds
        assert abs(r["delta_match"] - expected) < TOLERANCE, (
            f"Row '{r['state']}': delta_match={r['delta_match']:.6f}, "
            f"expected={expected:.6f}"
        )
