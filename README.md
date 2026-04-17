# Tennis In-Game Fair Value Calculator

A Markov-chain model for best-of-3 tennis that computes how a favourite's match-win probability shifts at key game states during the first set. Compare the model's numbers against live betting odds and the gap is an edge signal.

---

## What it does

For each first-set game state below, the model outputs the favourite's **set win %**, **match win %**, and **Delta Match** (shift from the pre-match anchor):

| State | Meaning |
|---|---|
| Pre-match (0-0) | Set has not started; shows the betting-site odds directly |
| Fav up 1 break | Favourite has one net break of serve |
| Fav down 1 break | Favourite is down one net break |
| Fav up 2 breaks | Favourite has two net breaks |
| Fav down 2 breaks | Favourite is down two net breaks |
| Fav WINS 1st set | First set completed for the favourite |
| Fav LOSES 1st set | First set lost by the favourite |

**Delta Match** answers "how should my view of the match change now that the first set has reached this state?" — a direct, signed shift from the pre-match anchor in match-win probability.

---

## How it works

1. **Set-level Markov chain** (`src/markov.py`): from `(fav_games, und_games, server)` the recursion walks every reachable future game, weighting each branch by the server's hold probability. Memoised, so each unique state is computed once.

2. **Tiebreak approximation** (v1): at 6-6, `P(fav wins TB) = fav_hold / (fav_hold + und_hold)`.

3. **Match layer** (`src/match.py`): `P(win bo3 | p_set) = p² · (3 − 2p)`. From any (sets_fav, sets_und) score the model returns the closed-form probability of going on to win the match.

4. **First-set game state → match win**: total probability on the first set's outcome:
   ```
   P(match) = P(win set) · P(match | 1-0 sets) + P(lose set) · P(match | 0-1 sets)
   ```

5. **Site-anchoring**: the betting site's pre-match price is the absolute level; the model only contributes the *shift*:
   ```
   match_win_fav(state) = prematch_odds + (model_at_state - model_pre_match)
   ```
   This keeps the model honest about levels (the market prices dozens of match-specific factors the model does not) while using the Markov chain purely for relative motion.

---

## Inputs

Edit the block at the top of `src/main.py` before each match:

| Variable | Description |
|---|---|
| `SURFACE` | One of: `Slow Clay`, `Clay (Typical)`, `Hard Court`, `Grass/Fast Hard` |
| `GENDER` | `Men` or `Women` (used for display + sanity guidance on hold-rate ranges) |
| `FIRST_SERVER` | `"fav"` or `"und"` — who serves game 1 |
| `FAV_HOLD_RATES` | Dict mapping each surface to the favourite's serve-hold rate |
| `UND_HOLD_RATES` | Dict mapping each surface to the underdog's serve-hold rate |

Hold rates are fractions in `[0, 1]` (68 % → `0.68`). Pre-match site odds are entered interactively at run time.

---

## How to run

```bash
# 1. Create and activate a virtual environment (first time only)
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Edit src/main.py: set SURFACE, GENDER, FIRST_SERVER, and hold rates

# 4. Run
cd src
python main.py                 # prints the table and exports a CSV
python main.py --live          # interactive score-by-score mode
```

---

## Output table

```
Match State             Set Win%   Match Win% (fav)   Delta Match
-----------------------------------------------------------------
Pre-match (0-0)            58.9%              64.0%            --
Fav up 1 break             63.7%              66.3%         +2.3%
Fav down 1 break           53.2%              61.2%         -2.8%
Fav up 2 breaks            86.1%              77.2%        +13.2%
Fav down 2 breaks          25.1%              47.6%        -16.4%
Fav WINS 1st set              --              83.9%        +19.9%
Fav LOSES 1st set             --              35.5%        -28.5%
```

**Using Delta Match for edges**: if the table says `Match Win % (fav) = 66.3 %` (+2.3 %) at up-1-break but the live odds imply 61 %, that gap is a potential edge on the favourite. The column order mirrors the Google Sheets template so rows can be pasted directly.

A CSV is written to `outputs/` with a `#` metadata header (surface, gender, hold rates, anchor, timestamp) followed by the table.

---

## Live mode

```
  Score > 3 2 fav 0.71
  3-2 fav srv  |  set: 58.9%  match A: 63.1% (-0.9%)  match B: 36.9%   edge: -7.9%
```

Enter `fav_games und_games server [optional live_odds]`. Terminal scores (e.g. `6 4 fav`) are rejected because those belong on the "WINS 1st set" row of the main table, not as an intra-set state.

---

## Assumptions & simplifications (v1)

- **Best-of-3 only.** No best-of-5 support yet.
- **Favourite serves first** (configurable via `FIRST_SERVER`, but the canonical states below assume `"fav"`).
- **Canonical "down 1 break" state** is `(0, 1, fav)` — *favourite serving, down one game* — regardless of the actual scoreline. Similarly `(1, 0, und)` for up 1 break, `(0, 2, fav)` for down 2 breaks, `(2, 0, und)` for up 2 breaks. These are simplifications; a real "just broken in game 1" state would be `(0, 1, und)` and gives a noticeably more negative number, especially on high-hold surfaces. For v1, we follow the canonical choice and accept that high-hold surfaces under-emphasise the sting of an early break.
- **Hold rates are constant.** No momentum, fatigue, or pressure adjustment.
- **Tiebreak is a single Bernoulli trial** (`fav_hold / (fav_hold + und_hold)`), not a point-by-point mini-chain.
- **Future sets reset to neutral** `(0, 0, fav)` — after the first set, we re-use the neutral set-win probability as the probability for sets 2 and 3.
- **Pre-match row shows the site's odds exactly.** Only the deltas come from the Markov chain.

---

## Sanity checks (run automatically by the test suite)

| Property | Test |
|---|---|
| Equal hold rates → exactly 50 % set win | `test_equal_holds_set_win_50pct` |
| Pre-match row of table == site odds | `test_prematch_row_anchored_to_site_odds` |
| Pre-match delta is `None` (nothing to compare against) | `test_prematch_row_delta_match_is_none` |
| Up-break states > neutral; down-break states < neutral | `test_{up,down}_states_above/below_neutral_set_win` |
| Delta ordering: `won > up2 > up1 > 0 > down1 > down2 > lost` | `test_delta_match_signs_and_ordering` |
| Mirror symmetry with equal holds: `P(up 1 break) + P(down 1 break) = 1` | `test_mirror_symmetry_equal_holds` |
| Anchoring identity holds for every row | `test_site_anchoring_is_correct` |
| `delta_match` == `match_win_fav − prematch_odds` | `test_delta_match_equals_anchored_shift` |
| Extreme hold rates (0, 1, 0.99/0.01) do not crash | `test_{zero,unit}_hold_rates_no_crash`, `test_extreme_favourite_no_crash` |

Run locally with:
```bash
pytest tests/ -v
```

---

## Google Sheets workflow

1. Run `python main.py` and note the CSV path printed at the end.
2. Open the CSV in Excel or a text editor. A `#`-prefixed header holds the metadata; the rows below are a plain CSV table.
3. In the supervisor's Sheets template, select the top-left cell of the output area and paste the data rows. Column order matches.

---

## Project structure

```
tennis_fair_value/
├── src/
│   ├── states.py     # Terminal-state detection for set scores
│   ├── markov.py     # Set-level Markov chain with memoisation
│   ├── match.py      # Best-of-3 match-win formulas
│   └── main.py       # Orchestration, config, output, CSV export
├── tests/
│   ├── conftest.py   # Adds src/ to sys.path for pytest
│   └── test_sanity.py
├── outputs/          # Generated CSV files (git-ignored)
├── requirements.txt
└── README.md
```
