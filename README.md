# Tennis In-Game Fair Value Calculator

A Markov chain model that computes how a favourite's match win probability changes at key first-set game states. The output is an edge table: compare the model's probabilities against live betting odds to spot mispricings.

---

## How it works

1. **Set-level chain** — from any game state `(fav_games, und_games, server)`, the model walks every possible game sequence recursively, weighting each branch by the server's hold probability. Results are memoised so each unique state is computed once.

2. **Tiebreak** (v1 approximation) — at 6-6, `P(fav wins TB) = fav_hold / (fav_hold + und_hold)`.

3. **Match layer** — set win probabilities are combined with best-of-3 formulas to produce match win percentages. For mid-first-set states, the model sums over both "win the set" and "lose the set" branches.

---

## Inputs

Edit the block at the top of `src/main.py` before each match:

| Variable | Description |
|----------|-------------|
| `SURFACE` | One of: `Slow Clay`, `Clay (Typical)`, `Hard Court`, `Grass/Fast Hard` |
| `PREMATCH_ODDS` | Betting-site pre-match win % for the favourite (e.g. `0.64`) — used for display only |
| `FAV_HOLD_RATES` | Dict mapping each surface to the favourite's serve-hold rate |
| `UND_HOLD_RATES` | Dict mapping each surface to the underdog's serve-hold rate |

Hold rates are fractions in `[0, 1]` (e.g. 68% hold rate → `0.68`).

---

## Output table

Seven rows covering the key first-set game states:

| Column | Description |
|--------|-------------|
| **Match State** | Game state label |
| **Set Win%** | Probability the favourite wins the current set from this state (`--` once the set is over) |
| **Match A** | Favourite's overall match win probability |
| **Match B** | Underdog's match win probability (`= 1 − Match A`) |
| **Delta** | Match A minus the model's own pre-match baseline |

**Using the delta for edges:** if the model says Match A = 55% (delta = +8%) at a given state but the live odds imply 48%, that gap is a potential edge to bet on the favourite.

---

## How to run

```bash
# 1. Create and activate a virtual environment (first time only)
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Edit src/main.py: set SURFACE, PREMATCH_ODDS, and hold rates

# 4. Run
cd src
python main.py
```

The model prints the table to the terminal and saves a CSV to `outputs/`.

---

## How to run tests

```bash
# From the project root
pytest tests/ -v
```

The test suite (`tests/test_sanity.py`) covers:

- Equal hold rates → exactly 50% set win and match win
- Monotonicity: up states > pre-match > down states; 2 breaks > 1 break
- Mirror symmetry: P(up 1 break) + P(down 1 break) = 1.0 with equal holds
- Match A + Match B = 100% on every row
- Edge cases: hold rates at 0.0 and 1.0 do not crash
- Delta is computed relative to the model's own pre-match, not the betting-site input

---

## Google Sheets workflow

1. Run the model and note the file path printed at the end, e.g.:
   ```
   CSV saved to: outputs/tennis_fv_Clay_Typical_20260416_143022.csv
   ```

2. Open the CSV in Excel or a text editor. The file contains a short metadata header (lines starting with `#`) followed by a standard CSV table.

3. In Google Sheets:
   - Open the supervisor's template sheet
   - Select the target cell (top-left of the output table area)
   - Paste the data rows (skip the `#` header lines)

The column order — `Match State`, `Set Win%`, `Match A`, `Match B`, `Delta` — matches the template layout.

---

## Model assumptions (v1)

- Best-of-3 match only
- The favourite always serves first
- All break-down positions at the same break count are treated as equivalent (e.g. "down 1 break" is always represented as `0-1 fav serves`)
- Hold rates are constant throughout the match (no momentum, fatigue, or score pressure)
- The tiebreak is modelled as a single Bernoulli trial, not point-by-point
- Future sets (after the first) are modelled from the neutral `(0-0, fav serves)` state

---

## Project structure

```
tennis_fair_value/
├── src/
│   ├── states.py     # Terminal state detection for set scores
│   ├── markov.py     # Set-level Markov chain with memoisation
│   ├── match.py      # Best-of-3 match win formulas
│   └── main.py       # Orchestration, config, output, CSV export
├── tests/
│   ├── conftest.py   # Adds src/ to sys.path for pytest
│   └── test_sanity.py
├── outputs/          # Generated CSV files (git-ignored)
├── requirements.txt
└── README.md
```
