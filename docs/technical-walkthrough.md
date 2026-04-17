# Technical walkthrough — the code, top to bottom

A plain-English tour of what each file does, why it's written that way, and which patterns transfer to other projects.

---

## The architecture in one picture

```
                       ┌────────────┐
                       │  app.py    │  ← Streamlit UI (user-facing)
                       └─────┬──────┘
                             │  imports run_model, set_win_probability, etc.
           ┌─────────────────┼─────────────────┐
           ▼                 ▼                 ▼
      ┌──────────┐    ┌──────────┐      ┌──────────┐
      │ main.py  │    │markov.py │      │ match.py │
      │ (CLI +   │    │(set chain│      │(bo3 close│
      │ orches-  │───▶│  with    │      │  -form   │
      │ tration) │    │ memoise) │      │ formulas)│
      └────┬─────┘    └────┬─────┘      └──────────┘
           │               │
           ▼               ▼
      ┌──────────────────────────┐
      │       states.py          │  ← smallest primitive
      │   (is_terminal, winner)  │
      └──────────────────────────┘
```

**Dependency rule**: each file only imports from files *below* it. No circular dependencies. This is why you can `import markov` in tests without pulling in Streamlit.

---

## Layer 1 — `states.py` (the primitive)

A **state** is a 3-tuple: `(fav_games, und_games, server)`. That's it. No class, no object.

```python
def is_terminal(state):
    fav, und, _ = state
    if fav == 7 or und == 7: return True     # covers 7-5, 7-6
    if fav == 6 and und <= 4: return True    # covers 6-0 … 6-4
    if und == 6 and fav <= 4: return True    # covers 0-6 … 4-6
    return False
```

**Why a tuple, not a class?** Tuples are **hashable** — they work as dictionary keys. We need that for memoisation in `markov.py`. A class would require implementing `__hash__` and `__eq__`. Simple beats fancy.

**Why is `server` part of the state?** Because `(5, 5, fav)` and `(5, 5, und)` are *different* states probabilistically — who serves next determines the branching odds. The state must carry everything that affects the future.

---

## Layer 2a — `markov.py` (the set-level chain)

The core recursion, annotated:

```python
def set_win_probability(fav_hold, und_hold, state):
    cache = {}                                      # (1)

    def recurse(s):
        if is_terminal(s):                          # (2)
            return 1.0 if winner(s) == "fav" else 0.0
        if s in cache:                              # (3)
            return cache[s]

        fav, und, server = s
        if fav == 6 and und == 6:                   # (4)
            total = fav_hold + und_hold
            p = fav_hold / total if total > 0 else 0.5
            cache[s] = p
            return p

        if server == "fav":                         # (5)
            p_hold = fav_hold
            state_if_hold  = (fav + 1, und, "und")
            state_if_break = (fav, und + 1, "und")
        else:
            p_hold = und_hold
            state_if_hold  = (fav, und + 1, "fav")
            state_if_break = (fav + 1, und, "fav")

        result = p_hold * recurse(state_if_hold) + (1 - p_hold) * recurse(state_if_break)
        cache[s] = result                           # (6)
        return result

    return recurse(state)
```

**What's happening, numbered:**

1. **Closure over a cache dict.** Every call to `set_win_probability` gets its own fresh cache. Prevents stale memoisation across different hold-rate inputs.
2. **Base case.** If the set is over, probability is 1 (fav wins) or 0 (und wins).
3. **Memoisation check.** Many paths through the recursion hit the same sub-state; computing `P((3, 2, fav))` once saves thousands of later re-computations. Without memoisation, runtime is exponential; with it, polynomial.
4. **Special case for tiebreak.** We don't recurse into the tiebreak — we approximate it with a closed-form.
5. **The branching.** Every non-terminal state has exactly two children: server holds or is broken. The server alternates on both branches — that's tennis.
6. **Cache and return.** The mathematical heart of this line:

   ```
   P(fav wins from s) = p_hold · P(fav wins if server holds)
                      + (1 − p_hold) · P(fav wins if server is broken)
   ```

   This is the **law of total probability** — you'll use it anywhere you decompose an outcome into disjoint cases.

---

## Layer 2b — `match.py` (the best-of-3 closed-form)

Where `markov.py` uses recursion, `match.py` uses **algebra** — because best-of-3 has only four non-terminal set-scores: `(0,0)`, `(1,0)`, `(0,1)`, `(1,1)`. Just enumerate them:

```python
def match_win_from_set_score(sets_fav, sets_und, p_set):
    if sets_fav == 2: return 1.0                          # already won
    if sets_und == 2: return 0.0                          # already lost
    if (sets_fav, sets_und) == (0, 0):
        return p_set ** 2 * (3 - 2 * p_set)               # bo3 closed-form
    if (sets_fav, sets_und) == (1, 0):
        return p_set + (1 - p_set) * p_set                # = 2p − p²
    if (sets_fav, sets_und) == (0, 1):
        return p_set ** 2                                 # must win both
    if (sets_fav, sets_und) == (1, 1):
        return p_set                                      # decider
```

**Why no Markov chain here too?** Because the search tree is tiny enough that writing the formulas out is faster to read, faster to verify, and harder to bug. A Markov chain is overkill for 6 states.

**Pattern:** use recursion when the state space is *huge* (can't enumerate); use closed-form when it's *small* (can enumerate). Don't confuse "can" with "should".

---

## Layer 3 — `main.py` (orchestration)

This is the only file with "business logic" — it combines the math pieces with user-facing concerns (input validation, CSV export, printing).

The key function is `run_model`:

```python
def run_model(fav_hold, und_hold, prematch_odds, first_server="fav"):
    p_set_neutral       = set_win_probability(fav_hold, und_hold, (0, 0, first_server))
    p_match_if_win_set  = match_win_from_set_score(1, 0, p_set_neutral)
    p_match_if_lose_set = match_win_from_set_score(0, 1, p_set_neutral)

    def model_match_win(state):
        p_set   = set_win_probability(fav_hold, und_hold, state)
        p_match = p_set * p_match_if_win_set + (1 - p_set) * p_match_if_lose_set
        return p_set, p_match
    ...
```

**The anchor move** — instead of returning `p_match` directly, we apply a *shift* to the market's pre-match price:

```python
def anchored(p_match_model):
    return prematch_odds + (p_match_model - p_match_model_pre)
```

This single line is the most important in the whole project, and it's not in the Markov code at all — it's in the orchestration. **The math is neutral; the interpretation lives in the orchestration.**

---

## Layer 4 — `app.py` (the UI)

Streamlit is **reactive**: the entire script re-runs every time you touch a widget. So there's no event handling — you just write Python top-to-bottom.

```python
surface  = st.selectbox("Surface", SURFACES)         # reads widget value
fav_hold = st.slider("Favourite hold %", ...)        # reads widget value
results  = run_model(fav_hold, und_hold, ...)        # recompute fresh
st.dataframe(results)                                # render
```

Every slider move = new script execution = new call to `run_model`. It's fast because `run_model` is fast (memoised Markov + closed-form match layer).

**Why `app.py` doesn't own any math.** It imports `run_model` from `main.py`. If we later build a REST API, a Discord bot, or another UI, they all import the same `run_model`. **One source of truth.**

---

## Layer 5 — `tests/test_sanity.py` (property tests)

Not "this input gives this output" tests (those are brittle). **Property tests** — things that must be true by the nature of the problem:

```python
def test_equal_holds_set_win_50pct(h):
    assert _neutral_set_win(h, h) == 0.5                    # symmetry

def test_mirror_symmetry_equal_holds(h):
    up_1   = set_win_probability(h, h, (1, 0, "und"))
    down_1 = set_win_probability(h, h, (0, 1, "fav"))
    assert up_1 + down_1 == 1.0                             # complementary events

def test_delta_match_signs_and_ordering():
    assert d_won > d_up2 > d_up1 > 0 > d_down1 > d_down2 > d_lost
```

These catch *structural* bugs (swapped signs, broken recursion) that unit tests miss. If the implementation is changed entirely, these still pass — they encode **what the model is**, not **how it computes**.

---

## Five transferable patterns

These are what you take to the next project, not tennis-specific:

1. **State as a hashable tuple.** Whenever a problem has a state space, represent each state as a tuple. You get hashability (for memoisation) and immutability (for safety) for free.

2. **Recursion + memoisation for exponential state spaces.** The whole Markov chain is one recursive function with a dict cache. Five lines of Python solves what could be thousands of matrix multiplications. The pattern works for *any* problem where (a) you can identify a base case, and (b) each state decomposes into a weighted sum of child states.

3. **Anchor external, compute relative.** Don't pretend your model knows better than a mature source (the market, a vendor API, historical data) at the *level*. Use the external source as the anchor, and use your model for the *shift*. This shows up in finance (benchmark + alpha), sports (ELO + adjustment), forecasting (baseline + seasonality) — everywhere.

4. **Small files with a dependency hierarchy.** `states.py` knows nothing about the math. `markov.py` knows about states but not about matches. `match.py` knows about neither. `main.py` knows about all three. This means any single layer can be tested, replaced, or re-used without touching the others.

5. **Property tests over example tests.** "Delta ordering is monotonic" survives every refactor. "At hold = 0.68 the result is 0.5898…" breaks the moment the tiebreak formula changes. Write properties, not examples, whenever the domain gives you laws.

---

## How this walkthrough maps to the code

| Section of this doc | File in the repo |
|---|---|
| Layer 1 — the primitive | [`src/states.py`](../src/states.py) |
| Layer 2a — set-level chain | [`src/markov.py`](../src/markov.py) |
| Layer 2b — match closed-form | [`src/match.py`](../src/match.py) |
| Layer 3 — orchestration | [`src/main.py`](../src/main.py) |
| Layer 4 — UI | [`src/app.py`](../src/app.py) |
| Layer 5 — property tests | [`tests/test_sanity.py`](../tests/test_sanity.py) |
