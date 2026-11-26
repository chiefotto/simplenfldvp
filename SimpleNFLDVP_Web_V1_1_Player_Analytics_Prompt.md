# SimpleNFLDVP V1.1 — Player Matchup Analytics

## 1. Role and objective

Act as a senior Python software engineer, sports data engineer, and Streamlit developer working in the existing SimpleNFLDVP repository.

Implement a complete V1.1 upgrade in one coding-agent session. Inspect the current repository, establish baseline behavior, implement the changes, run tests and smoke checks, fix regressions, and update documentation. Do not stop at a plan, pseudocode, or scaffolding. Make ordinary implementation decisions independently, preserving the project's established architecture and avoiding unnecessary complexity.

V1 already provides CBS defense-vs-position (DVP) ingestion, nflreadpy schedule and roster ingestion, SQLite storage, shared analytics services, CLI and Discord interfaces, and a Streamlit web application with Weekly Overview, Schedule, Game Outlook, and Rankings pages. Treat the actual checked-out code as the source of truth; do not assume that all features or file names from the previous implementation prompt exist exactly as described.

V1.1 should answer the following questions for a selected NFL game and statistical category:

- Where is the defensive weakness or strength?
- Which offensive players are likely to be relevant, based on roster status, depth chart, and actual playing time?
- What has each relevant player averaged per game before the selected matchup?
- What is a simple, transparent matchup-adjusted estimate for that same statistic?

The immediate UX problem is that Game Outlook currently displays long lists of rostered players and headshots before showing the statistical opportunity. Users must scroll past reserves, developmental players, and backups to find the actual data. Fix this by making the statistic the primary element and placing a compact, relevant player list with averages and adjusted estimates alongside or directly below it.

The product progression is:

```text
Defensive weakness / strength
    -> Offensive positional opportunity
    -> Relevant players based on role and usage
    -> Historical per-game average
    -> Experimental matchup-adjusted estimate
```

The estimates are research indicators, not guarantees, probabilities, betting recommendations, or validated player projections. Label them accordingly throughout the application.

---

## 2. Repository inspection and regression protection

Before making changes:

1. Read repository instructions, README, requirements, the V1 implementation prompt if present, and any relevant configuration.
2. Inspect the existing `database/`, `scraper/`, `services/`, `interfaces/web/`, `interfaces/discord/`, and `tests/` modules.
3. Inspect the actual SQLite schema and representative existing data, including roster status codes, game IDs, position labels, metric aliases, and snapshot dates.
4. Inspect the current Game Outlook UI, the service payload it consumes, and existing navigation and URL handling.
5. Identify reusable ingestion, team abbreviation normalization, snapshot selection, flagging, ranking, and database functions.
6. Run the existing test suite before modifications and record baseline failures if any.
7. Verify the installed Python and nflreadpy versions, supported data-loading APIs, available seasons, and actual returned schemas. Use official nflverse/nflreadpy documentation and sample data where network access permits.
8. Preserve unrelated user changes. Use a dedicated branch such as `feature/player-matchup-analytics-v1-1` if appropriate. Do not push or deploy without explicit authorization.

Preserve existing commands, calculations, labels, data contracts, historical navigation, URLs, and functionality wherever possible. Do not replace working infrastructure simply to conform to this prompt.

---

## 3. Stack and architectural constraints

Continue using the existing technology stack:

| Layer | Technology |
|---|---|
| DVP data | Existing CBS scraper |
| Schedule, roster, team, player, depth chart, and usage data | nflreadpy / nflverse |
| Persistence | Existing SQLite database |
| Data processing | Python, existing Pandas/Polars conventions |
| Analytics | Shared Python services |
| Web UI | Streamlit |
| Discord | Existing discord.py implementation |
| Tests | Existing test framework, Streamlit AppTest where useful |

Maintain the existing separation between ingestion, persistence, analytics/services, and presentation. All player ranking, averages, and projection logic must live in shared Python modules, not Streamlit components or Discord adapters. The web application should read persisted data, never make live nflverse requests on user navigation or widget reruns.

Do not introduce React, another frontend framework, a new API server, a second database, a machine learning platform, an LLM, or an external paid service. Prefer native Streamlit widgets and compact dataframes over fragile CSS or large custom HTML components. Keep the deployment compatible with Streamlit Community Cloud and the existing entry point, currently `interfaces/web/app.py` if unchanged.

---

## 4. Extend nflreadpy ingestion

Extend the existing admin/scraper workflow to ingest depth charts, weekly player statistics, and participation/usage data in addition to the existing schedule, roster, and metadata datasets.

Candidate APIs (verify exact signatures against the installed version):

```python
import nflreadpy as nfl

nfl.load_depth_charts(season)
nfl.load_player_stats(season, summary_level="week")
nfl.load_snap_counts(season)
nfl.load_rosters_weekly(season)
```

If a listed API has a different signature, schema, or availability, adapt to the actual supported version and document the change. Never invent an endpoint or assume data exists simply because the loader is documented.

### 4.1 Depth charts

Persist enough information to resolve an expected player role for a selected team's game:

- Season, team, player identifier, position or position slot.
- Depth chart rank (`pos_rank` or the equivalent actual field).
- Source snapshot timestamp or historical week, as available.
- Source-specific identifiers and relevant metadata for joins.

Depth chart schemas change across seasons. In particular, modern nflverse depth charts may be timestamped rather than week-based, and ranks may refer to separate slots (e.g., multiple WR slots), not a single global positional ranking. Inspect the data and handle those differences deliberately. Do not interpret every rank-1 WR as the unique WR1.

Retain historical depth chart observations. For historical analysis, select only snapshots known to predate the matchup (prefer a common pre-week cutoff; if using a pre-kickoff cutoff, make that policy explicit and apply it consistently). Never use the latest depth chart to represent a previous week. If an eligible snapshot is unavailable, fall back to historical usage and indicate that the role is inferred.

### 4.2 Weekly player statistics

Ingest individual regular-season game statistics for the selected season and any already-supported historical seasons as appropriate. Retain game identifiers where available, team at the time of the game, season, week, position, stable player ID, and statistics needed for the existing matchup categories.

Map the existing canonical metric aliases to verified nflreadpy player-stat columns. The expected mapping is:

| Existing metric alias | Player-stat column |
|---|---|
| `passing_td` | `passing_tds` |
| `passing_yards` | `passing_yards` |
| `rushing_attempts` | `carries` |
| `rushing_yards` | `rushing_yards` |
| `rushing_td` | `rushing_tds` |
| `targets` | `targets` |
| `receptions` | `receptions` |
| `receiving_yards` | `receiving_yards` |
| `receiving_td` | `receiving_tds` |

The actual repository aliases and source columns take precedence. Centralize this mapping; do not duplicate it across pages. Do not expand V1.1 projection coverage to unrelated metrics (e.g., fantasy points, interceptions, fumbles) unless deliberately supported and tested. Keep those existing analytics available without a player estimate if unsupported.

Ingest additional usage fields needed for player selection: passing attempts, carries, targets, and offensive snaps or snap share where available.

### 4.3 Snap counts and actual participation

Use snap counts or another reliable existing participation field to identify offensive participation and distinguish legitimate zero-stat games from games the player missed. A weekly box-score dataset may omit players with zero recorded counting stats, so do not assume its rows alone capture every game played.

Join using stable identifiers. nflverse player statistics, depth charts, rosters, and snap counts may expose different ID systems (e.g., GSIS, PFR, or ESPN IDs). Use verified identifier crosswalks from existing metadata or nflverse player data. Never silently join by player name only. Unmatched players or missing participation data should be surfaced as data limitations, not silently fabricated.

### 4.4 Ingestion and storage behavior

- Extend the existing scraper/admin entry point rather than create an unrelated ingestion system.
- Store additional data in the existing SQLite file; add safe, non-destructive migrations and indexes.
- Use idempotent upserts with stable unique keys appropriate to the source grain. Prevent duplicates and preserve historical snapshots.
- Validate incoming frames and guard against overwriting good existing data with empty, malformed, or incomplete source responses.
- A failure to retrieve optional depth chart or player data must not destroy existing data or unnecessarily prevent schedule/DVP analysis. Report partial success and freshness clearly.
- Avoid downloading unnecessary historical datasets on every refresh. Support an explicit season/backfill path where practical.
- Track data source freshness and relevant observation dates. Avoid using ingestion time as a fabricated historical publication time.
- Keep the committed SQLite snapshot and existing database path workflow compatible with cloud deployment. Do not commit secrets, cache artifacts, or unbounded raw datasets.

Potential new tables: `depth_charts`, `player_weekly_stats`, and `player_snap_counts`. Adapt names, constraints, and access functions to existing conventions. Keep raw observed statistics separate from derived averages and estimates. Derive the latter on demand initially.

---

## 5. Preserve the defensive analytics engine

The existing DVP methodology remains the authoritative matchup signal. Do not change population z-score calculations, position-specific standardization, missing-value rules, defensive rank direction, tie behavior, configured metrics, or completed-week logic.

Maintain existing flags exactly:

| Z-score interval | Flag |
|---|---|
| z >= 1.5 | HOT |
| 1.0 <= z < 1.5 | WARM |
| -1.0 < z < 1.0 | NEUTRAL |
| -1.5 < z <= -1.0 | COOL |
| z <= -1.5 | COLD |

A positive z-score for the supported counting statistics means the defense allows more than the positional league average, favorable to the opposing offense. Keep the distinction between the offensive team and its opposing defense. Never associate an opportunity with the wrong team's roster.

Maintain the existing aggregate positional scores and metric rankings. V1.1 adds player context and an experimental adjustment; it does not change the rank or flag derived from the defensive statistics.

Keep the selected game week, defensive snapshot week, player-stat cutoff, roster snapshot, and depth chart observation distinct. For a Week 12 game, the normal inputs are the prior completed Week 11 defensive snapshot, player games before Week 12, and an appropriate Week 12 roster/depth chart available before the game.

For historical player estimates and backtests, never substitute a defensive snapshot from the selected week or a later week. An older valid prior snapshot may be used if clearly identified, but if none exists, show no adjusted estimate. If an existing historical matchup view has a more permissive fallback, preserve unrelated behavior while preventing that fallback from entering V1.1 estimates or backtests. Do not label a retrospective result as a pregame forecast if the point-in-time availability of the inputs cannot be established.

---

## 6. Player eligibility, roles, and relevant-player selection

Implement a shared player selection service. It should return relevant offensive players for a season, game week, team, position, and optionally metric. Use the existing weekly roster service as the foundation.

### 6.1 Eligibility

- Select the offensive team's roster for the selected game week, using the existing documented fallback only when safe and visibly indicated.
- Interpret roster status codes using actual source definitions. In the current UI, codes such as `ACT`, `DEV`, and `RES` appear. Verify their meaning rather than hardcoding guessed semantics.
- Default to active/eligible players. Exclude reserve, developmental/practice squad, and other clearly unavailable statuses from default recommendations. Keep a collapsed or optional "Show all rostered players" view that clearly distinguishes status and does not imply availability.
- Do not claim an active-roster player is confirmed to start or play. If injury/game-day availability is not verified, label it unknown or expected, not confirmed.
- Preserve the selected team's roster identity for trades; do not attach a former team's roster membership to a new matchup.

### 6.2 Depth chart and recent usage

Use a deterministic hierarchy:

1. Eligible roster membership.
2. Applicable depth chart snapshot and slot rank, if available.
3. Recent actual offensive usage before the matchup.
4. Season usage as a fallback.
5. Stable deterministic tie-breakers.

Use the depth chart to identify expected starters and rotational players. Use usage to resolve ambiguous slots, distinguish meaningful contributors, and provide a fallback when depth charts are absent. For WR and other positions with multiple rank-1 slots, derive an ordered display role from starter slots and usage; clearly distinguish an inferred display role from an official depth chart slot.

Recommended usage indicators:

| Position | Primary indicators |
|---|---|
| QB | Passing attempts and offensive snaps |
| RB | Carries and targets; offensive snaps as supporting evidence |
| WR | Targets and offensive snaps |
| TE | Targets and offensive snaps |

Use metric-relevant usage as a secondary signal where sensible (e.g., targets for receiving opportunities, carries for rushing opportunities). Prefer the last three eligible games before the selected week for recent usage; fall back to season usage if recent evidence is sparse. Document deterministic ordering and tie-breaks.

Do not select the starting QB solely by highest passing TD average: a backup may have an inflated average from one appearance. A newly promoted starter may have little prior production; retain that role with a limited-sample or unavailable estimate instead of silently choosing a different player. If depth chart and recent usage materially disagree, surface the uncertainty rather than claiming certainty.

### 6.3 Display defaults

| Position | Default maximum shown |
|---|---:|
| QB | 1 |
| RB | 2 |
| WR | 3 |
| TE | 2 |

Make these simple configurable constants or a compact control. Allow users to reveal backups or all eligible players without making the default Game Outlook unnecessarily long. Do not pad a short list with unavailable players. Show QB2 when the user expands the list or when starter status is unresolved and the UI can clearly show both candidates.

Player role labels should include QB1, QB2, RB1, RB2, WR1, WR2, WR3, TE1, and TE2 as appropriate. Treat them as expected/inferred roles when not officially established. Display the source or reason, e.g. "Depth chart", "Recent usage", or "Role uncertain".

Return stable player IDs, names, team, position, roster status, headshot URL (optional), role, relevant usage summary, and role-source metadata. Ensure each player appears at most once within a specific opportunity.

---

## 7. Player per-game averages

Implement a shared service to calculate per-game averages for supported metrics using only games before the selected matchup week.

Provide these windows:

- **Season:** All eligible regular-season games played in the selected season before the selected matchup.
- **Last 3:** The player's three most recent eligible games before the matchup.
- **Last 5:** The player's five most recent eligible games before the matchup.

Use season average as the default baseline. Allow users to select the baseline window; do not automatically cherry-pick whichever average is highest.

### Rules

- Sort games chronologically using the schedule/game identifiers and exclude the selected game and future games. Use a consistent pre-week cutoff for historical reproducibility.
- Only include completed games known before the cutoff. Preserve season/week and source game identity to avoid double-counting.
- Exclude missed games and byes. Include actual offensive appearances with legitimate zero production in the requested category (e.g., a participating QB who threw zero touchdowns).
- Do not treat an absent row or missing metric value as zero unless the source and participation evidence justify a real zero. Report incomplete coverage and use a defensible denominator.
- If participation data is unavailable, use documented available box-score evidence as a fallback, identify the limitation, and do not silently claim a complete games-played average.
- For traded players, season averages may include prior-team games from that same season; retain the current roster team for the matchup and surface a trade/role-context note where practical. No future-team data.
- Distinguish `None`/unavailable from a valid 0.0 average. Never divide by zero.
- Return the number of contributing games, requested and actual window, last contributing game date/week, and any data quality notes.
- Mark samples of fewer than three eligible games as limited (configurable threshold). For no valid sample, display an em dash or "Not enough data" and do not generate a numeric estimate.
- Do not silently incorporate previous-season games into a current-season average. For early-season games with insufficient history, show the limitation rather than fabricate a baseline.

Example (illustrative only):

```text
Player: QB1
Metric: Passing TDs
Season average: 1.90 (10 games)
Last 3: 2.33 (3 games)
Last 5: 2.00 (5 games)
Baseline window: Season
```

---

## 8. Experimental matchup-adjusted estimate

Implement one small, pure, independently testable projection/estimate service. Reuse the existing defensive matchup row, including the raw allowed value, league average, z-score, and position. Do not calculate a new defensive z-score or reinterpret HOT/WARM thresholds.

### 8.1 Default formula: shrunk relative defensive allowance

Use the relative allowance formula as the initial default because it ties the adjustment to the actual magnitude of the defensive statistic instead of assuming that a z-score represents a fixed percentage change.

Definitions:

- `player_avg`: The selected historical per-game player average for the exact metric.
- `defense_avg`: The opposing defense's positional allowed statistic from the eligible pregame DVP snapshot.
- `league_avg`: The league average of that same defensive statistic for the same position and snapshot.
- `weight`: Shrinkage toward the player's baseline, initially 0.50.
- `min_multiplier`: Initially 0.50.
- `max_multiplier`: Initially 1.50.

```python
ratio = defense_avg / league_avg
raw_multiplier = 1 + weight * (ratio - 1)
multiplier = max(min_multiplier, min(max_multiplier, raw_multiplier))
adjusted = player_avg * multiplier
```

For example, using synthetic numbers:

```text
Player average passing TDs:        2.10
Defense passing TDs allowed:       2.10
League average passing TDs allowed: 1.50
Defense/league ratio:               1.40
Shrinkage weight:                  0.50
Applied multiplier:                1.20
Adjusted estimate:                 2.52 passing TDs
```

The DVP z-score and flag continue to determine how the opportunity is ranked and displayed. The allowance ratio determines the adjustment magnitude. Do not apply both adjustments simultaneously, as this would double-count the same defensive signal.

### 8.2 Optional comparison formula: z-score adjustment

Implement a simple alternate z-score method for backtesting and model comparison:

```python
alpha = 0.15
multiplier = max(0.50, min(1.50, 1 + alpha * matchup_z))
adjusted = player_avg * multiplier
```

Example: baseline 1.90 passing TDs, z-score +2.00, multiplier 1.30, adjusted estimate 2.47 passing TDs.

A z-score of +2 does NOT inherently imply a 30% increase in player production. Both default coefficients (0.50 and 0.15) and the caps are experimental starting assumptions, not trained or validated statistical parameters.

Keep the production default as the relative allowance model unless a documented, leakage-safe validation supports changing it and the user later approves. The alternate method can be exposed in an advanced comparison control if it remains simple, but do not clutter the default interface with model-building tools.

### 8.3 Validation and guardrails

- Only calculate an adjusted estimate for supported counting metrics with comparable definitions and units between the player baseline, defensive allowed statistic, and positional league average. Verify that CBS data is a per-game positional allowance and the league average uses the same basis. Do not confuse aggregate position-group output with an individual player statistic; the ratio is a heuristic multiplier, not a direct estimate of the player's share.
- Handle missing, nonnumeric, nonfinite, or invalid values explicitly. If the player baseline is unavailable, return no estimate. If league average is zero/nonpositive, the ratio is unavailable; show the baseline unadjusted with a reason, not a fabricated matchup factor. The same applies to missing or incompatible defensive values.
- For supported nonnegative volume/count metrics, avoid negative estimates. Some yardage statistics can legitimately be negative in actual games; handle that case deliberately rather than silently altering historical averages. Do not invent a meaningful relative multiplier for an invalid negative baseline or allowance.
- A legitimate zero baseline remains zero under this multiplicative heuristic; flag sparse samples and do not imply the player cannot score.
- Apply caps consistently and indicate when a cap was applied.
- Keep full precision internally and round only for display (typically two decimals). Fractional TDs represent a numerical expectation-like estimate, not a possible integer game outcome or a probability.
- Do not automatically turn an unavailable adjustment into a numeric projected result without clearly marking it as baseline-only.
- Estimates are independent per metric/player. Check for obvious inconsistencies (e.g., receptions exceeding targets when both estimates are shown, or total displayed position estimates diverging sharply from a reasonable baseline). Do not silently rescale players or invent a team production budget; document limitations and, where practical, warn on obvious conflicts. A coherent team-level allocation model is outside V1.1.
- No betting lines, odds, wagers, or individual start/sit recommendations in this feature.

Return a structured result containing player baseline, contributing games, window, adjusted estimate or unavailable status, signed percentage adjustment, multiplier, method, z-score/flag, defense allowance, league average, applied cap, snapshot identifiers, and warning/reason fields.

---

## 9. Redesign Game Outlook: stat-first, compact player context

The existing page must no longer force users to scroll through a tall roster/headshot list before seeing the actual statistical categories. Make this the primary UI change.

Preserve the game header, team logos, kickoff information, both offensive sections, positional summary scores, and HOT/WARM, COOL/COLD, All stats, and positional views if already implemented.

### 9.1 Opportunity-first layout

Within each offense, display opportunities ordered by the existing z-score ranking (strongest favorable first, strongest unfavorable first in the negative view). Group by position or metric if useful, but always make the category and flag visible before any player information. Keep the complete original statistical breakdown accessible.

Preferred desktop layout concept (synthetic values):

```text
DALLAS OFFENSE vs PHILADELPHIA DEFENSE

QB — Passing Touchdowns                        HOT  +2.00
Defense allowed: 2.10  |  League avg: 1.50  |  DEF rank: 2

Player             Role    Games    Season avg    Adj. est.    Change
QB A               QB1       10         2.10          2.52      +20%
[Show QB2 / more players]

RB — Rushing Attempts                         WARM +1.23
Defense allowed: 25.40 | League avg: 22.25 | DEF rank: 3

Player             Role    Games    Season avg    Adj. est.    Change
RB A               RB1       10        16.40         17.56       +7%
RB B               RB2        9         5.80          6.21       +7%
```

This example illustrates the layout, not actual NFL results. Never include synthetic player names or values as production fallback data.

Use either a compact two-column card (stat details left, player data right) or a stat header with a small player table immediately underneath. On narrow/mobile layouts, stack the stat header first. Avoid wide blank gaps between images and names. Player headshots should be optional, small (approximately 24–36 px), aligned with names, and never drive row height; default to compact rows or a dataframe. No large portrait lists, no repeated image-heavy roster sections. When several flags share the same position, compact repeated player rows are acceptable if each metric's averages are distinct; avoid repeating large biography/roster blocks.

### 9.2 Player row information

Display, at minimum:

- Player name and expected/inferred role.
- Baseline average for the selected metric and window.
- Number of contributing games.
- Matchup-adjusted estimate, when available.
- Signed adjustment percentage.
- Roster status or a concise status warning where relevant.

Recent averages can be shown in an optional expanded view or tooltip. Use concise source labels for depth chart/usage roles. Do not imply projected stats are certain. Make unavailable data visibly distinct from zero.

### 9.3 Controls and readability

- Add a shared baseline selector: Season / Last 3 / Last 5.
- Default to relevant players only. Provide a "Show more players" / "Show all rostered players" option without disrupting the overall layout.
- Keep the existing position and flag views usable. Avoid introducing many redundant controls.
- Preserve textual HOT/WARM/NEUTRAL/COOL/COLD labels and the existing theme. Use existing flag colors and accessible contrast; signed estimate changes should be visually distinct but not overemphasized.
- Add a concise explanation of the estimate formula and sample-size warning, preferably once per page or in an expander rather than repeated on every row.
- Keep both teams' sections symmetrical and retain the full data view for power users.
- Ensure the page still works when depth charts, stats, or roster data are missing. A valid DVP opportunity should render even if no player estimate can be computed.
- Preserve existing season/week and direct game URL behavior. Add baseline query parameters only if supported cleanly; no breaking route changes.

---

## 10. Add a Weekly Player Opportunities page

Add a fifth, lightweight Streamlit page named "Player Opportunities" (or a clear equivalent consistent with the existing navigation). It should reuse the exact same selection, averages, and estimate services used by Game Outlook.

Purpose: allow users to explore the week's player-level matchup-adjusted statistics without opening every game individually. It is a research table, not a betting or recommendation engine.

Default to the strongest HOT/WARM opportunities and relevant players. Use one row per unique `(game_id, player_id, metric)` (include season/week as needed). Do not mix offensive teams or duplicate rows from multiple depth chart slots.

Columns:

- Player and expected role.
- Offensive team and opposing defense.
- Position and metric.
- DVP z-score and flag.
- Selected baseline window and per-game average.
- Contributing games.
- Adjusted estimate.
- Percentage change.
- Data/role warning if relevant.
- Game navigation where supported.

Controls:

- Existing shared season/week context.
- Search by player or team.
- Position, metric, and multi-flag filters.
- Baseline window selector (Season, Last 3, Last 5).
- Relevant players only / expanded player list.
- Minimum contributing-games filter or clear limited-sample option.
- Sort by matchup z-score, percentage adjustment, or estimate when comparing the same metric; never rank raw passing yards against raw touchdowns as if units were comparable. Default to z-score ranking.
- Reset filters and CSV export of filtered rows, including relevant model and data provenance fields.

Use compact tables with consistent numerical formatting. Provide links to individual Game Outlook pages. Preserve existing Overview, Schedule, Rankings, and Game Outlook features; do not replace or conflate them with the new page. Do not add new Discord commands unless trivial and consistent with the existing architecture; existing `/outlook` links must keep working.

---

## 11. Backtesting and model validation

Implement a small reproducible offline evaluation command/module that can compare the baseline average with the two experimental adjustment methods. Do not require historical data to be fabricated or a live API to be available during tests.

Suggested command (adapt to repository conventions):

```bash
python -m services.backtest --season 2026 --metric passing_td
```

### Evaluation protocol

1. Select completed historical games with valid player actuals and a matching earlier DVP snapshot. Require defensible historical roster/depth chart or usage selection, baseline cutoff, and participation information. Never use current roster/depth charts to infer past starters.
2. Construct each estimate strictly from data available before the target game/week. Exclude the target game's stats from averages, recent usage, and player selection.
3. Use historical DVP snapshots already stored by the scraper. Do not run today's CBS scraper and label its season-to-date output as a prior-week defensive snapshot.
4. Compare the same eligible player-game-metric examples across the unadjusted average, shrunk defensive ratio, and z-score methods. Keep baseline windows consistent.
5. Report per-metric sample counts and coverage, MAE, RMSE, and signed mean error (bias). Include comparison against the unadjusted baseline and optionally split by flag or position when sample sizes permit. Do not aggregate incompatible metric units into one misleading overall error.
6. Separate projection accuracy conditional on participation from availability/selection outcomes. For example, if an expected starter did not play, report that separately; do not silently delete such cases and claim unconditional forecast accuracy. Only use players who actually participated for the conditional stat-production error if clearly labeled. Disclose how zero/missing actuals are handled.
7. If historical coverage is insufficient, report what is missing and the number of usable cases, and exit gracefully. A historical archive built retrospectively may not prove what was known pregame; label that limitation. No invented performance metrics.
8. Keep coefficients fixed for the initial evaluation. Any tuning must use chronological training/validation separation and an untouched later evaluation set; do not tune on the same examples used to report final performance. Do not claim predictive improvement without evidence.

The initial model does not need to outperform the baseline to satisfy implementation acceptance. The purpose is to expose evidence and limitations. Keep estimates labeled experimental even if a small sample performs well.

---

## 12. Performance, deployment, and compatibility

- Continue using the same SQLite snapshot and Streamlit Community Cloud deployment workflow. The existing `interfaces/web/app.py` entry point must remain usable unless a migration is explicitly documented.
- Update `requirements.txt` only as necessary. Verify compatible Python versions and dependency resolution; keep changes minimal.
- Use existing database initialization and caching patterns. Add suitable indexed queries and batch lookups; avoid N+1 database queries per player/metric in the weekly view.
- Cache player averages, relevant-player selections, and weekly estimates appropriately; include season, week, position/team, metric, baseline window, and data freshness or TTL in cache behavior. Ensure newly ingested snapshots eventually become visible.
- Keep the app read-oriented. External requests happen in the ingestion/admin path, not on every UI rerun. Do not expose scraper actions to public web users.
- Make deployment and database update behavior explicit: a local scraper run does not update a separately hosted SQLite file. Document how to refresh and publish the data snapshot safely using the repository's current workflow. If database growth becomes material, report it; do not introduce a new database server.
- Preserve existing Discord configuration and shareable links. Never include bot tokens, local `.env` contents, or secrets in logs or commits.
- Do not deploy, push to remote, or change production settings as part of this task unless explicitly authorized.

---

## 13. Suggested module organization

Adapt the following to the actual codebase rather than creating every file mechanically:

```text
simplenfldvp/
├── database/
│   ├── storage.py                 # extend migrations/upserts
│   ├── schema.sql                 # new persisted datasets
│   ├── rosters.py                 # reuse
│   ├── depth_charts.py            # historical depth chart access
│   └── player_stats.py            # weekly stat/participation access
├── scraper/
│   └── nfl_data.py                # extend nflreadpy ingestion
├── services/
│   ├── roster_service.py          # extend or reuse
│   ├── player_service.py          # eligibility, role, usage, averages
│   ├── projection_service.py      # pure estimate functions
│   ├── outlook_service.py         # assemble player-enhanced opportunities
│   └── backtest.py                # optional module name; offline evaluation
├── interfaces/web/
│   ├── app.py                     # register new page
│   ├── components.py              # compact stat/player presentation
│   ├── data.py                    # cache wrappers
│   └── pages/
│       ├── game_outlook.py        # stat-first redesign
│       └── player_opportunities.py
├── interfaces/discord/            # preserve existing behavior
├── tests/                         # regression + feature coverage
├── requirements.txt
└── README.md
```

Prefer cohesive functions over extra wrappers, empty modules, or unnecessary class hierarchies.

---

## 14. Tests and acceptance criteria

Add deterministic tests using fixtures, temporary SQLite files, and mocked external loaders. Synthetic data is acceptable for tests, never production output. Run the full baseline and new test suite, not only the newly added tests. Use Streamlit AppTest and/or practical smoke checks for page rendering and navigation. If a live dependency/data source cannot be tested, explicitly document the limitation and exercise the relevant fallback path.

### Ingestion and persistence

- Verified mappings for depth charts, weekly player stats, and snap counts.
- Correct identifier crosswalks and canonical team/position abbreviations.
- Modern timestamped and supported legacy weekly depth chart handling.
- Idempotent refreshes, no duplicate rows, preservation of older observations, and safe migration of an existing database.
- Empty/malformed optional data does not destroy existing good snapshots.
- Current web app can open the resulting database, even if new datasets are unavailable.

### Player selection and averaging

- Default QB1, RB1/RB2, WR and TE limits work; reserve/developmental players are excluded from defaults.
- Multiple WR depth chart slots are handled without duplicate players or false claims of official global rank.
- A backup with one high-scoring game does not automatically outrank a starter with reliable role/usage evidence.
- Missing or conflicting depth chart/usage data is handled and labeled correctly; newly promoted starters can have unavailable estimates.
- Correct offensive team, roster week, trade handling, and player identity joins.
- Season/last-three/last-five averages are correct, including played games with zero production, missed games, byes, small samples, missing stats, and cross-team season history.
- Target-game and future data cannot enter historical averages, role selection, or projections.

### Projection and backtest logic

- Ratio example: baseline 2.10, defense 2.10, league 1.50, weight 0.50 -> 2.52.
- Z-score example: baseline 1.90, z=2.00, alpha=0.15 -> 2.47.
- Neutral/equal allowance leaves baseline unchanged; stronger/weaker valid allowances adjust in the expected direction.
- Both caps, negative/zero/missing/nonfinite inputs, unsupported metrics, no sample, legitimate zero average, and unavailable league average are handled.
- Exactly one adjustment method is applied; original DVP score/flag remains unchanged.
- Historical estimates never use later defensive snapshots or current depth charts as past inputs.
- Backtest compares identical eligible cases, reports coverage/error metrics and participation policy, and handles insufficient historical snapshots without fabrication.

### Web and regression behavior

- Existing CLI and Discord commands continue to work.
- Existing DVP calculations, flags, rankings, and completed-week behavior are unchanged on equivalent inputs.
- All existing web pages launch and retain navigation, filters, season/week selections, and direct URL behavior.
- Game Outlook renders both offensive sections with the metric and flag above/beside compact relevant-player rows; no mandatory long roster image block before categories.
- Player averages and adjusted estimates correspond to the exact displayed statistical category.
- Baseline window and show-more controls work; missing data is displayed explicitly without crashing.
- Weekly Player Opportunities renders, filters, sorts, links to Game Outlook, and exports the filtered rows correctly.
- No synthetic production data, no hidden API calls on UI reruns, no secret leakage, and no unnecessary infrastructure.

---

## 15. Implementation sequence

Execute in this order, but adapt ordinary details to the repository:

1. Inspect repository and establish baseline tests/schema/data availability.
2. Verify nflreadpy source schemas and identifier mappings.
3. Extend ingestion and SQLite migrations for depth charts, stats, and participation.
4. Implement role/usage selection and player averaging services with tests.
5. Implement pure estimate functions and historical snapshot guardrails.
6. Extend existing outlook service payloads without breaking existing consumers.
7. Redesign Game Outlook to be stat-first and compact.
8. Implement Weekly Player Opportunities with shared services.
9. Add offline backtest evaluation and tests.
10. Run all regression and feature tests; perform application smoke tests and, where available, validate a real ingestion/sample matchup end to end.
11. Fix discovered failures and review performance, data consistency, and deployability.
12. Update README, configuration, and usage documentation.

If optional source data is unavailable or a historical backtest cannot be run due to missing snapshots, implement and test the appropriate fallback and continue completing the remaining work. Do not silently substitute fake data or claim that blocked tests passed. Do not stop to request routine user approval.

---

## 16. Scope boundaries

V1.1 includes player roles/usage, compact game presentation, player per-game averages, the experimental adjustment, a player opportunities research page, and offline model evaluation. It does not include:

- A trained or calibrated production prediction model.
- Betting odds, player prop lines, wager suggestions, or probability estimates.
- Individual start/sit guarantees or confirmed starter claims without authoritative evidence.
- Live injury prediction or guaranteed game-day availability.
- A coherent team-level play allocation or simulation model.
- Personalized fantasy league integration, user accounts, authentication, or payments.
- Changes to the existing DVP methodology or a replacement CBS scraper.
- A new backend/frontend stack or actual cloud deployment.

Keep the implementation focused on transparent, useful player context and a small experimental estimate. Do not turn the task into a full fantasy forecasting platform.

---

## 17. Documentation and final deliverables

Update the README with:

- The V1.1 architecture and data sources, including verified package APIs and supported schema/season limitations.
- Database migration and refresh/backfill instructions, and how the updated SQLite snapshot is made available to the hosted app.
- How to run the Streamlit app and navigate the new page.
- How starters/relevant players are selected, the status and role-source labels, baseline windows, participation denominator policy, and missing-data behavior.
- The exact estimate formulas, default constants, guardrails, sample-size limitations, and the distinction between the DVP flag and an experimental adjusted estimate.
- How to run the backtest, interpret its output, and run automated tests.

At completion, report:

1. What was implemented, including the new stat-first layout.
2. Files and database changes, ingestion functions, and dependencies.
3. The final role-selection and average policies, model constants, and any material assumptions.
4. How to refresh player/depth chart data and run the app.
5. Actual test/smoke/backtest commands run and results; distinguish real data checks from fixture tests.
6. Any unverified source schemas, missing historical data, runtime limitations, or residual issues.
7. Any deviations from this prompt and why they were necessary.

Do not claim deployment, predictive accuracy, or full functionality unless actually validated. The expected deliverable is a working, maintainable V1.1 implementation integrated into the existing application, not a standalone prototype.

**Begin by inspecting the current repository, then execute the complete implementation.**
