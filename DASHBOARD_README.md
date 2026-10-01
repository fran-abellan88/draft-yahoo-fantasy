# 🏀 NBA Fantasy Draft Assistant Dashboard

An interactive web dashboard for live NBA fantasy draft assistance, helping you make optimal picks based on 100,000 pre-simulated teams.

## Features

✅ **Real-time Team Filtering** - Instantly filters 100k teams based on your draft picks
✅ **Smart Recommendations** - Suggests the best available player for each round
✅ **Round-by-Round Navigation** - Manual control over draft round progression
✅ **Player State Management** - Click to cycle through: Available → Selected → Unavailable
✅ **Best Team Display** - Always shows the top remaining team with full stats
✅ **Search & Filter** - Quick player search across all rounds
✅ **Professional UI** - Clean, responsive design with smooth interactions

## Setup Instructions

### Quick Start (Automated) ⚡

The easiest way to run the dashboard is using the automated launcher:

**Option 1: Python Launcher (Recommended - Cross-platform)**
```bash
python3 run_dashboard.py
```

**Option 2: Bash Script (macOS/Linux)**
```bash
./run_dashboard.sh
```

The launcher will:
- ✅ Automatically run preprocessing if needed (first time only)
- ✅ Find an available port
- ✅ Start the web server
- ✅ Open the dashboard in your browser

That's it! Just run one command and you're ready to draft.

---

### Manual Setup (Advanced)

If you prefer to run things manually:

#### 1. Preprocess the Data (One-time setup)

First, convert the large CSV files into optimized JSON format:

```bash
python3 preprocess_data.py
```

This will:
- Read `top_teams_minmax.csv` (224MB, 100k teams)
- Read `Draft NBA Yahoo Fantasy 2025 - Picks.csv`
- Generate `teams_data.json` (~82MB)
- Generate `players_data.json` (~8KB)

**Note:** This step takes about 2-3 minutes. You only need to do this once.

#### 2. Start a Local Web Server

Since the dashboard loads JSON files, you need to serve it through a web server (browsers block local file access).

**Option A: Using Python (simplest)**
```bash
python3 -m http.server 8000
```

**Option B: Using Node.js**
```bash
npx http-server -p 8000
```

**Option C: Using PHP**
```bash
php -S localhost:8000
```

#### 3. Open the Dashboard

Open your browser and navigate to:
```
http://localhost:8000/dashboard.html
```

The dashboard will load the data (may take 10-20 seconds for the 82MB file).

## How to Use

### Player Selection States

Click any player button to cycle through three states:

1. **Available** (default) - White background, black text
2. **Selected** (✓) - Green background, white text, with checkmark
   - Use this when YOU draft a player
3. **Unavailable** (✗) - Red background, white text, with X
   - Use this when someone else drafts a player or you don't want them

### Draft Workflow

1. **Start at Round 1** - Only Round 1 players are enabled
2. **Make your pick** - Click a player to mark them as selected
3. **Mark unavailable players** - Click again to mark as unavailable
4. **Review recommendation** - See the suggested player for current round
5. **Check best team** - View the top remaining team composition
6. **Advance to next round** - Click "Next Round →" button
7. **Repeat** - Continue through all 11 rounds

### Key UI Elements

**Sidebar (Left)**
- Round control with "Next Round" button
- Player search box
- Player buttons organized by round and position
- Visual state indicators (✓ for selected, ✗ for unavailable)

**Main Panel (Right)**
- **Stats Cards** - Remaining teams, players selected, players unavailable
- **Recommendation Card** (purple) - Best pick for current round with frequency data
- **Best Team Card** (white) - Top remaining team with full roster and stats

**Reset Button** (bottom-right)
- Red button to restart the entire draft

## Data Structure

### teams_data.json
```json
{
  "teams": [
    {
      "id": 1,
      "rank": 1,
      "score": 0.576,
      "pos_std": 1.166,
      "stats": {
        "fg%": 0.487,
        "ft%": 0.787,
        "3ptm": 1672,
        "pts": 14554,
        ...
      },
      "players": [
        {"name": "Giannis Antetokounmpo MIL", "pick": 1, "position": "PF,C"},
        ...
      ]
    }
  ],
  "player_index": {
    "Giannis Antetokounmpo MIL": [1, 45, 123, ...],
    ...
  }
}
```

### players_data.json
```json
[
  {
    "name": "Giannis Antetokounmpo MIL",
    "pick": 1,
    "position": "PF,C",
    "stats": { "fg%": 0.57, "ft%": 0.639, ... }
  },
  ...
]
```

## Performance Notes

- **Initial Load**: 10-20 seconds (loading 82MB JSON)
- **Filtering**: Instant (optimized JavaScript filtering)
- **UI Updates**: Real-time (< 100ms)

The dashboard filters 100,000 teams client-side, which is why initial load takes time. Once loaded, all operations are instant.

## Troubleshooting

### Dashboard shows "Loading data... Please wait" forever

**Cause**: JSON files not found or browser blocking file access

**Solutions**:
1. Make sure you ran `preprocess_data.py` first
2. Verify `teams_data.json` and `players_data.json` exist in the same folder
3. Make sure you're using a web server (not opening `file://` directly)
4. Check browser console (F12) for error messages

### "Failed to fetch" error

**Cause**: Not running through a web server

**Solution**: Use one of the web server options mentioned in Setup step 2

### Page is slow or unresponsive

**Cause**: Large JSON file taking time to parse

**Solution**: Wait 10-20 seconds after page load. Consider using a faster browser (Chrome/Edge recommended).

### Players are disabled (grayed out)

**Cause**: You're on a different round than the player's round

**Solution**: Click "Next Round →" to advance to that player's round

## Technical Details

**Built with**:
- Pure HTML, CSS, JavaScript (no frameworks)
- Vanilla JS for maximum performance
- Client-side filtering for instant updates
- Optimized JSON structure for fast lookups

**Browser Requirements**:
- Modern browser with ES6 support
- Chrome 70+, Firefox 65+, Safari 12+, Edge 79+

## Files

- `dashboard.html` - Main dashboard application
- `preprocess_data.py` - Data preprocessing script
- `teams_data.json` - Preprocessed teams (generated)
- `players_data.json` - Preprocessed players (generated)
- `top_teams_minmax.csv` - Source data (100k teams)
- `Draft NBA Yahoo Fantasy 2025 - Picks.csv` - Source data (53 players)

## License

Built for personal fantasy draft use.
