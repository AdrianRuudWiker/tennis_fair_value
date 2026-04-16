"""
states.py
Defines tennis set states and helper functions for the Markov chain.

A state represents a moment in a set:
  - fav_games: games won by the favorite
  - und_games: games won by the underdog
  - server: who serves the next game, either "fav" or "und"
"""


def is_terminal(state):
    """
    Returns True if the set is over at this state.
    A set ends when:
      - A player has 6 games AND leads by 2+ games, OR
      - A player has 7 games (covers 7-5), OR
      - The score reaches 7-6 (tiebreak finished)
    """
    fav, und, _ = state

    # Someone reached 7 games -> set is over
    if fav == 7 or und == 7:
        return True

    # Someone reached 6 games with a 2+ game lead
    if fav == 6 and und <= 4:
        return True
    if und == 6 and fav <= 4:
        return True

    return False


def winner(state):
    """
    Returns 'fav' or 'und' for a terminal state.
    Raises an error if the state is not terminal.
    """
    if not is_terminal(state):
        raise ValueError(f"State {state} is not terminal")

    fav, und, _ = state
    return "fav" if fav > und else "und"


# Quick manual tests - run this file directly to check it works
if __name__ == "__main__":
    # Non-terminal states
    print(is_terminal((0, 0, "fav")))   # False
    print(is_terminal((3, 2, "und")))   # False
    print(is_terminal((6, 5, "fav")))   # False (need 2-game lead)

    # Terminal states
    print(is_terminal((6, 4, "fav")))   # True
    print(is_terminal((7, 5, "und")))   # True
    print(is_terminal((7, 6, "fav")))   # True (tiebreak finished)

    # Winners
    print(winner((6, 4, "fav")))        # fav
    print(winner((5, 7, "und")))        # und