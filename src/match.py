"""
match.py
Match probability calculations for bo3.

Takes set win probabilities and computes match win probabilities.
"""


def match_win_probability(p_set):
    """
    Probability of winning a best-of-3 match, given probability p_set
    of winning any individual set.

    Formula: p^2 * (3 - 2p)
      - p^2        = win 2-0
      - 2*p^2*(1-p) = win 2-1 (two possible orderings: WLW or LWW)

    Parameters:
      p_set: float in [0, 1], probability of winning a single set

    Returns:
      float in [0, 1]
    """
    return p_set ** 2 * (3 - 2 * p_set)


def match_win_from_set_score(sets_fav, sets_und, p_set):
    """
    Probability of winning the match from a specific set score.

    Parameters:
      sets_fav: sets won by favorite (0, 1, or 2)
      sets_und: sets won by underdog (0, 1, or 2)
      p_set: probability favorite wins any individual set

    Returns:
      float in [0, 1]
    """
    # Terminal states
    if sets_fav == 2:
        return 1.0
    if sets_und == 2:
        return 0.0

    # From (0, 0): need to win 2 out of 3
    if sets_fav == 0 and sets_und == 0:
        return match_win_probability(p_set)

    # From (1, 0): need 1 more set win out of up to 2
    if sets_fav == 1 and sets_und == 0:
        # Win next set (done) OR lose next then win the third
        return p_set + (1 - p_set) * p_set

    # From (0, 1): need 2 straight set wins
    if sets_fav == 0 and sets_und == 1:
        return p_set * p_set

    # From (1, 1): winner takes the final set
    if sets_fav == 1 and sets_und == 1:
        return p_set

    raise ValueError(f"Invalid set score: ({sets_fav}, {sets_und})")


# Quick tests
if __name__ == "__main__":
    # Test 1: equal set win prob -> match should also be 0.5
    prob = match_win_probability(0.5)
    print(f"p_set = 0.50 -> match win: {prob:.4f}")

    # Test 2: 60% set win -> should amplify to > 60% match win
    prob = match_win_probability(0.6)
    print(f"p_set = 0.60 -> match win: {prob:.4f}")

    # Test 3: down a set (0-1), need to win 2 straight
    prob = match_win_from_set_score(0, 1, 0.6)
    print(f"Down 0-1, p_set=0.60 -> match win: {prob:.4f}")

    # Test 4: up a set (1-0)
    prob = match_win_from_set_score(1, 0, 0.6)
    print(f"Up 1-0, p_set=0.60 -> match win:   {prob:.4f}")

    # Test 5: symmetry check
    up = match_win_from_set_score(1, 0, 0.5)
    down = match_win_from_set_score(0, 1, 0.5)
    print(f"Up 1-0 at p=0.5:   {up:.4f}")
    print(f"Down 0-1 at p=0.5: {down:.4f}")
    print(f"Sum (should be 1.0): {up + down:.4f}")