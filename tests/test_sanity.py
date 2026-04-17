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
    """The pre-match row match_win_a must equal prematch_odds exactly."""
    for odds in (0.50, 0.60, 0.64, 0.75):
        rows = _rows(prematch_odds=odds)
        assert abs(rows[0]["match_win_a"] - odds) < TOLERANCE, (
            f"Pre-match row should show {odds:.2f}, got {rows[0]['match_win_a']:.6f}"
        )


def test_prematch_row_delta_set_is_none():
    """Pre-match row has no delta_set (it IS the neutral state)."""
    rows = _rows()
    assert rows[0]["delta_set"] is None


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
# 4. delta_set is positive for up states, negative for down states
# ---------------------------------------------------------------------------

def test_delta_set_signs():
    """delta_set > 0 for break-up states, < 0 for break-down states."""
    rows = {r["state"]: r for r in _rows()}

    assert rows["Fav up 1 break"]["delta_set"]    > 0
    assert rows["Fav up 2 breaks"]["delta_set"]   > 0
    assert rows["Fav down 1 break"]["delta_set"]  < 0
    assert rows["Fav down 2 breaks"]["delta_set"] < 0


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
# 6. Match A + Match B = 100 % on every row
# ---------------------------------------------------------------------------

def test_match_ab_sum_to_one():
    """Every row in the results table must have match_a + match_b == 1.0."""
    rows = _rows()
    for r in rows:
        total = r["match_win_a"] + r["match_win_b"]
        assert abs(total - 1.0) < TOLERANCE, (
            f"Row '{r['state']}': match_a + match_b = {total:.8f} (not 1.0)"
        )


# ---------------------------------------------------------------------------
# 7. Site-anchoring: match_win_a = prematch_odds + model_shift
# ---------------------------------------------------------------------------

def test_site_anchoring_is_correct():
    """
    For each non-pre-match row:
      match_win_a == prematch_odds + (model_at_state - model_pre_match)
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
        "Fav up 2 breaks":   (2, 0, "fav"),
        "Fav down 2 breaks": (0, 2, "und"),
    }

    for r in rows[1:5]:  # mid-set rows only
        state = states_to_game_states[r["state"]]
        expected = prematch_odds + (raw_match(state) - model_pre)
        assert abs(r["match_win_a"] - expected) < TOLERANCE, (
            f"Row '{r['state']}': match_win_a={r['match_win_a']:.6f}, "
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
