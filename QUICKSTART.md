# 🏀 Quick Start Guide

## Option 1: Run the Dashboard (Uses Existing Data)

```bash
python3 run_dashboard.py
```

This will:
1. ✅ Preprocess data if needed (uses existing `top_teams_minmax.csv`)
2. ✅ Start web server on an available port
3. ✅ Open dashboard in your browser

## Option 2: Generate Fresh Data + Dashboard

If you want to regenerate team combinations with custom parameters:

```bash
# Small sample for testing (fast)
python3 fantasy_draft_optimizer.py --sample 10000 --preprocess

# Or generate all combinations (can take hours)
python3 fantasy_draft_optimizer.py --preprocess
```

The `--preprocess` flag automatically creates dashboard data after optimization completes.

---

## Using the Dashboard

### Player States (Click to cycle)

1. **White** = Available
2. **Green ✓** = Selected (you drafted them)
3. **Red ✗** = Unavailable (others drafted them)

### Workflow

1. Look at **purple recommendation card** for best pick
2. **Click player** to draft them (turns green)
3. **Click "Next Round →"** to advance
4. Repeat for all 11 rounds

### Tips

- Search players using the search box
- Check "Best Remaining Team" card for team composition
- Use "Reset Draft" button (bottom-right) to start over
- Only current round players are clickable

---

## Understanding the Workflow

### Complete Process:

1. **Optimization** (`fantasy_draft_optimizer.py`)
   - Analyzes millions of team combinations
   - Outputs: `top_teams_minmax.csv` and/or `top_teams_zscore.csv`
   - Can take hours for full analysis

2. **Preprocessing** (`preprocess_data.py` or `--preprocess` flag)
   - Converts CSV → JSON for web dashboard
   - Outputs: `teams_data.json` + `players_data.json`
   - Takes ~2-3 minutes

3. **Dashboard** (`run_dashboard.py`)
   - Interactive web interface to explore results
   - Runs instantly

### Typical Workflow:

- **First time**: Run optimizer with `--preprocess` flag
- **After changes to config**: Re-run optimizer with `--preprocess`
- **Daily use**: Just run `run_dashboard.py`

---

## Files Generated

### Optimizer Output (CSV):
- `top_teams_minmax.csv` - Teams ranked by min-max normalization
- `top_teams_zscore.csv` - Teams ranked by z-score normalization

### Dashboard Data (JSON):
- `teams_data.json` (~57-82MB) - Preprocessed teams for web
- `players_data.json` (~7-8KB) - Player data for web

---

## Advanced Options

### Optimizer Parameters:

```bash
# Sample only 100,000 team combinations
python3 fantasy_draft_optimizer.py --sample 100000 --preprocess

# Keep sampling until 10,000 valid teams found
python3 fantasy_draft_optimizer.py --valid-teams 10000 --preprocess

# Use only z-score normalization
python3 fantasy_draft_optimizer.py --method zscore --preprocess

# Limit output to top 50,000 teams
python3 fantasy_draft_optimizer.py --max-output 50000 --preprocess
```

### Configuration:

Edit [config.py](config.py) to change:
- `NUM_PICKS` - Number of draft picks to analyze (default: 8)
- File paths, stat categories, and other settings

---

## Need Help?

See [DASHBOARD_README.md](DASHBOARD_README.md) for complete documentation.
