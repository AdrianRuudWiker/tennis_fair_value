"""
markov.py
Set-level Markov chain for tennis.

Given two hold rates and a starting state, computes the probability
that the favorite wins the set. The chain walks through every possible
future state recursively, weighting each by its transition probability.
"""

from states import is_terminal, winner


def set_win_probability(fav_hold, und_hold, state):
    """
    Probability that the favorite wins the set from the given state.

    Parameters:
      fav_hold: float in [0, 1], favorite's hold probability
      und_hold: float in [0, 1], underdog's hold probability
      state: tuple (fav_games, und_games, server)

    Returns:
      float in [0, 1]
    """
    cache = {}

    def recurse(s):
        # Base case: set is over
        if is_terminal(s):
            return 1.0 if winner(s) == "fav" else 0.0

        # Return cached result if we've computed this state before
        if s in cache:
            return cache[s]

        fav, und, server = s

        # Special case: tiebreak at 6-6 (v1 approximation)
        if fav == 6 and und == 6:
            total = fav_hold + und_hold
            p_fav_wins_tb = (fav_hold / total) if total > 0 else 0.5
            cache[s] = p_fav_wins_tb
            return p_fav_wins_tb

        # Figure out who's serving and build the two next states
        if server == "fav":
            p_hold = fav_hold
            state_if_hold = (fav + 1, und, "und")
            state_if_break = (fav, und + 1, "und")
        else:
            p_hold = und_hold
            state_if_hold = (fav, und + 1, "fav")
            state_if_break = (fav + 1, und, "fav")

        # Core Markov equation: weighted sum of the two branches
        result = (
            p_hold * recurse(state_if_hold)
            + (1 - p_hold) * recurse(state_if_break)
        )
        cache[s] = result
        return result

    return recurse(state)


# Quick tests - run this file directly to check it works
if __name__ == "__main__":
    # Test 1: equal hold rates should give ~0.5
    prob = set_win_probability(0.65, 0.65, (0, 0, "fav"))
    print(f"Equal holds (0.65, 0.65), fav serves first: {prob:.4f}")

    # Test 2: strong favorite should give high probability
    prob = set_win_probability(0.85, 0.65, (0, 0, "fav"))
    print(f"Strong fav (0.85 vs 0.65), fav serves:     {prob:.4f}")

    # Test 3: weak favorite should give low probability
    prob = set_win_probability(0.55, 0.80, (0, 0, "fav"))
    print(f"Weak fav (0.55 vs 0.80), fav serves:       {prob:.4f}")

    # Test 4: down a break vs up a break should mirror (sum to ~1.0)
    down_break = set_win_probability(0.75, 0.75, (0, 1, "fav"))
    up_break = set_win_probability(0.75, 0.75, (1, 0, "und"))
    print(f"Down 1 break from (0,1,fav) w/ equal holds: {down_break:.4f}")
    print(f"Up 1 break from (1,0,und) w/ equal holds:   {up_break:.4f}")
    print(f"Sum (should be 1.0):                        {down_break + up_break:.4f}")