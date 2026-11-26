# SimpleNFLDVP V1.1.1 — Player Data and Role Assignment Hotfix

## Objective

Act as a senior Python data engineer and software engineer working directly in the existing SimpleNFLDVP repository. Diagnose and fix the player-data ingestion, role assignment, and missing matchup-adjusted estimates introduced in V1.1.

Implement the fixes in one session: inspect, reproduce, identify root causes, modify code, refresh real data, test, and document. Do not stop at a plan or simply improve the appearance of missing values. Do not assume the suspected causes below are proven until you inspect the database and actual upstream payloads.

Preserve the existing Python, nflreadpy, SQLite, Streamlit, and discord.py architecture. Keep the existing DVP methodology, projection formulas, pages, links, CLI and Discord commands working. Do not add a new provider, frontend framework, or unrelated feature unless absolutely required and justified.

## 1. Known symptoms and repository context

The issue was observed on the hosted Streamlit Game Outlook page for season 2026, week 12, game `2026_12_PHI_DAL`, with defense snapshot week 11 and roster snapshot week 12.

- Player names and positional matchup statistics display correctly, but the displayed player rows have zero games, missing historical averages, missing adjusted estimates, and the note `Not enough data.`
- Cole Payton is displayed as QB1, Joe Milton III as QB2, and Tanner McKee as QB3, all with `Role uncertain`.
- Jaydon Blue is displayed as RB1, Saquon Barkley as RB2, and Will Shipley as RB3, all with `Role uncertain`.
- The user expects Joe Milton to be the relevant starting QB and Saquon Barkley to be RB1 for the selected Eagles matchup. Treat these as examples to investigate against the actual roster, pregame chart and usage data, not as hard-coded truths.
- The compact stat-first player tables are already implemented; retain them.

The inspected commit was `886944a2ac059b4db86c74b49a72c7a9a657b202` (`hotfix`). Inspect the current checkout rather than resetting to that commit. Preserve any subsequent or unrelated changes.

Relevant modules include:

- `scraper/nfl_data.py`, `scraper/main.py`, `scraper/schedule.py`
- `database/storage.py`, `database/schema.sql`, `database/player_stats.py`, `database/rosters.py`, `database/matchups.py`
- `services/player_service.py`, `services/projection_service.py`, `services/backtest.py`
- `interfaces/web/data.py`, `interfaces/web/state.py`, `interfaces/web/components.py`, `interfaces/web/views/game_outlook.py`, `interfaces/web/views/player_opportunities.py`
- `tests/test_ingestion.py`, `tests/test_players.py`, `tests/test_projection.py`, `tests/test_web.py`

Known code behavior at the inspected revision:

- `_order_players()` sorts by depth-chart rank, recent usage, season usage, then name, and assigns numbered roles even with no evidence. This produces alphabetical QB1/RB1 labels when the inputs are unavailable.
- `weekly_player_opportunities()` reads historical stats and snap counts, constructs player game logs, selects pregame charts, calculates averages, then calls the projection service.
- `estimate_ratio()` returns `Not enough data.` if the baseline is missing. The absence of estimates is therefore an upstream symptom, not evidence that the formula is broken.
- The reference-data ingestion catches failures independently. Some preparation functions return empty DataFrames if expected columns are missing, obscuring the difference between an unavailable dataset and an incompatible schema.
- The committed SQLite file grew by only 44 KiB between the original web implementation and the player-analytics implementation, suggesting the new tables may be largely empty. This is a hypothesis, not proof; inspect actual row counts.

## 2. Establish a baseline and reproduce the failure

Before changing code:

1. Read the repository instructions and README, check the working tree, and inspect the current implementations and dependency versions.
2. Run the existing test suite and record baseline failures.
3. Confirm the exact database path used by the scraper, services and Streamlit. Verify that the app is reading the intended committed database and not an accidentally initialized empty file.
4. Inspect the SQLite schema and report total and per-season row counts for `weekly_rosters`, `players`, `depth_charts`, `player_weekly_stats`, `player_snap_counts`, `schedule`, and `raw_dvp`. Report min/max weeks, latest depth observation, mapped snap IDs, and the coverage of eligible roster players by prior stats, snaps and chart records.
5. Inspect week 12 PHI and DAL QB/RB roster entries, their GSIS IDs, prior-week game histories, latest eligible charts, role outputs, and baseline results. Use the actual player IDs to join records, not display names.
6. Call the actual service function `weekly_player_opportunities` for 2026 week 12 with the season baseline and relevant-player scope. Record representative results before the fix.
7. Determine whether the issue is missing source files, failed downloads, schema mismatches, incorrect ID mapping, season/week filtering, database writes, stale deployed database, or a combination. Do not infer table contents from file size alone.

Example read-only diagnostic (adapt to the actual schema):

```python
import sqlite3
from database.storage import DB_PATH

with sqlite3.connect(DB_PATH) as conn:
    for table in (
        'weekly_rosters', 'players', 'depth_charts',
        'player_weekly_stats', 'player_snap_counts',
        'schedule', 'raw_dvp',
    ):
        print(table, conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0])
```

## 3. Diagnose and repair nflreadpy ingestion

Use the installed/pinned nflreadpy version and inspect its real function signatures and returned frames. Verify the actual requested season and the availability of the relevant upstream assets. Do not invent columns or assume a newer package has the same schema as the installed version.

Verify these loaders independently:

```python
import nflreadpy as nfl

season = 2026
nfl.load_rosters_weekly([season])
nfl.load_players()
nfl.load_teams()
nfl.load_depth_charts([season])
nfl.load_player_stats([season], summary_level='week')
nfl.load_snap_counts([season])
```

For each source, inspect raw shape, columns, dtypes, season/week coverage, representative rows, normalized shape and saved row count. Verify whether each call raises an error, returns no records, or returns records with unexpected fields. Check package caching, network errors, release availability and data freshness where relevant. If a dependency update is necessary, verify compatibility and update pinned requirements deliberately; avoid unrelated upgrades.

### Weekly stats

- Verify the actual team column, including `team` versus `recent_team` or another documented alias. The inspected `prepare_player_stats()` requires `team` and returns an empty frame if it is absent. This is a specific potential schema mismatch, not a confirmed diagnosis.
- Verify player ID, season, week, position, game type/season type and all required counting-stat fields. Normalize supported aliases explicitly. Preserve the distinction between legitimate zeros and missing columns/values.
- Reject incompatible schemas with actionable diagnostics instead of quietly returning an empty frame. Keep valid existing data on failures.
- Retain regular-season game-level/weekly records and validate unique player/week identities. Do not blindly sum duplicated records from repeated snapshots; consolidate only legitimate separate records as warranted by the source grain.
- Map existing DVP metric identifiers to the correct player stat columns and test every configured metric.

### Depth charts

- Inspect current timestamp-based charts and legacy week-based charts separately. Verify actual team, ID, position abbreviation, slot, rank and observation fields, including whether slot is a string or number.
- Verify that ranks and positions survive normalization and are not inadvertently discarded. Do not conflate fullbacks with primary running backs unless supported by the intended classification.
- Use the latest eligible pregame observation for the selected team and matchup, not a later snapshot. Prefer timezone-aware comparison with scheduled kickoff and the information cutoff; if only dates exist, use a conservative, documented rule. Where only a weekly chart exists, use same-week information only when its pregame availability is established; otherwise use the latest earlier eligible chart and label its age.
- Preserve distinct depth-chart slots; do not interpret multiple rank-1 WR slots as one official WR1 designation.

### Snap counts and player ID crosswalks

- Confirm the source PFR identifier column, offensive snaps and offensive snap percentage, season/week, and team.
- Join stats and roster entries on canonical GSIS IDs. Resolve chart ESPN IDs and snap PFR IDs via verified player metadata crosswalks. Preserve strings and leading zeros; reject null-like placeholder strings; ensure provider IDs are not confused with GSIS IDs.
- Normalize team abbreviations consistently across all sources.
- Report ID match rates and examples of unmapped IDs. Investigate low coverage instead of falling back silently to player names. Do not merge distinct players based on name similarity.

### Persistence and refresh

- Validate prepared frames before saving, including key uniqueness and source coverage.
- Preserve historical records and non-destructive, idempotent writes. Avoid replacing good data with empty or invalid downloads.
- Ensure new tables and indexes are initialized/migrated correctly, and validate row counts after each write.
- Expose a documented reference-only refresh and validation command, preferably through a simple existing or new CLI entry point. The existing `ingest_reference_data(2026)` can be called independently of the CBS scrape. Do not require fetching CBS to repair player data.
- Print clear per-source statuses, including downloaded/prepared/written counts, actual exception type, missing columns and unmatched IDs. Treat a failed required dataset as a degraded/failed player refresh even if the DVP refresh succeeds.
- If upstream 2026 data genuinely cannot be obtained, do not invent game logs, roles or averages, and do not fill gaps using future or unrelated seasons. Continue implementing tested fixes and state exactly which live-data checks were blocked.

## 4. Fix player role assignment

Correct `_order_players()`, `_usage()`, and `_limit()` or their current equivalents.

### Eligibility

- Default to rostered players with eligible active status per the current source definitions. Keep reserve, developmental, inactive and other non-eligible players out of the default list; preserve the All rostered view.
- Unknown status must be identified as unknown, not represented as confirmed active. Active roster does not guarantee game-day availability.

### Ranking evidence

- QB: pregame starting depth chart and recent passing attempts/offensive snaps.
- RB: pregame chart, recent carries plus targets and offensive snaps.
- WR/TE: pregame chart, recent targets and offensive snaps.
- Measure recent usage over the team's last three completed games before the selected matchup, not just the last three games each player appeared in. Distinguish known non-participation from missing data; do not count unknown games as known zeros. Use team-season usage as a fallback and consider traded players' history explicitly.
- Fresh credible pregame starter information is valuable, particularly for QB injury replacements. When charts and recent usage disagree, distinguish confirmed chart evidence from inferred usage and stale data. Implement a documented deterministic policy: prefer a credible current starting designation; use recent usage to resolve unclear or stale charts and rotational roles; flag genuine conflicts. Do not let historical usage automatically override a credible newly announced starter.
- Differentiate source depth rank from an inferred display role (e.g. `RB1 · Recent usage`). Include source and freshness information where practical.
- Never assign QB1, RB1 or any numbered role based solely on alphabetical order or a deterministic ID tie-breaker. When no reliable evidence exists, display `Unranked` or `Role unknown` and an explanatory note. If credible evidence cannot distinguish tied players, avoid presenting arbitrary tie-breaking as verified depth order.
- Do not rank players solely by their highest touchdown average or projection. Small samples and backups can be misleading.

### Default presentation

- Relevant: up to one QB, two RBs, three WRs, two TEs supported by evidence. Permit fewer if evidence or eligible players are insufficient. If no roles can be resolved, explain the limitation and offer an unranked eligible-roster view instead of silently choosing the first alphabetical players.
- All eligible and All rostered: continue to expose the fuller list, with unsupported roles explicitly unranked.
- Do not hard-code Joe Milton, Saquon Barkley or any other player as a starter. Validate the examples using the available pregame records and recent usage; report disagreements if the source does not support the user's expectations.

## 5. Repair player averages and adjusted estimates

Inspect `_games_for()`, `_average()`, and `weekly_player_opportunities()` end to end.

- For the selected game week, use only prior eligible games from that season and information available before the matchup. Never leak the selected game or future results into the baseline or historical backtest.
- Preserve Season, Last 3 and Last 5 games as baseline choices. These average windows refer to actual games played, unlike the recent team-game window used for role ranking.
- Include real zero-stat games when participation and metric availability are established. Do not infer zero from a failed source, a missing metric column, an unmatched ID, or an absent box score unless the source's documented grain and coverage justify that inference.
- Use offensive snap participation and verified box-score records as appropriate. Distinguish no participation, unknown participation, missing metric values and true zero production.
- Preserve the limited-sample warning for fewer than three usable games. A known starter with no sample may still be shown but without a fabricated estimate.
- Verify correct game counts, units, and per-game averages for passing TDs, passing yards, rushing attempts, rushing yards, rushing TDs, targets, receptions, receiving yards and receiving TDs.
- Provide specific missing-data reasons, such as `Player stats not ingested`, `No matching player ID`, `No prior games`, `Metric unavailable`, or `Defense snapshot unavailable`, when distinguishable. Reserve a general unavailable reason for cases that cannot be classified.
- Do not treat a missing estimate as zero or confuse a zero baseline with missing data.

### Preserve projection methodology

Keep the current default relative-allowance estimate:

```text
multiplier = clamp(1 + 0.50 * (defense_allowed / league_average - 1), 0.50, 1.50)
adjusted = player_average * multiplier
```

Keep the existing comparison estimate:

```text
multiplier = clamp(1 + 0.15 * z_score, 0.50, 1.50)
adjusted = player_average * multiplier
```

Do not change coefficients, caps, flag thresholds, DVP z-scores, or ranking definitions as a shortcut to resolving missing inputs. Preserve existing handling of invalid matchup factors, negative/zero baselines and warnings unless a specific demonstrated correctness bug requires a documented fix. Estimates remain experimental, not validated player forecasts.

For a test fixture with a 2.10 player average, 2.10 defense allowance and 1.50 league average, the default estimate is 2.52. For a 1.90 average and +2.00 z-score, the comparison estimate is 2.47. These are test examples, not real player statistics.

## 6. Add practical data-health diagnostics

Add a compact expandable Streamlit sidebar section or similarly unobtrusive status view, backed by a shared read-only diagnostic service rather than UI-only guesses.

For the selected season/week, show:

- Defense snapshot and schedule availability.
- Roster snapshot used and age/fallback note.
- Depth-chart availability and latest eligible observation.
- Weekly player-stat coverage and latest available prior week.
- Snap-count coverage and mapped ID rate.
- Count or proportion of relevant players with usable historical baselines, where meaningful.
- Missing or degraded sources and why adjusted estimates or roles are unavailable.

Distinguish `Missing`, `Stale`, `Partial`, and `Available` based on actual coverage; a nonzero table count alone does not imply adequate coverage for the selected slate. Avoid marking historical weeks as stale relative to today when their as-of data is appropriate. Show a helpful warning in the game outlook when player data is unavailable, while retaining DVP analysis and normal navigation.

Add a local diagnostic command with more detailed counts and coverage. Do not expose administrative scrape actions, sensitive paths, credentials, raw stack traces or unnecessary internal errors to public users. Keep existing cache behavior reasonable and ensure repaired database snapshots are visible after refresh/reboot; consider including a snapshot version in cache keys if necessary.

## 7. Tests and verification

Add regression tests using deterministic fixtures representing the actual observed upstream schemas (sanitized or minimal, with no fabricated production rows). Preserve all existing tests.

Required coverage:

- Each actual upstream schema and supported aliases, including missing/incompatible required columns and season/type filtering.
- Empty/failed downloads preserve previously valid data and emit actionable diagnostics.
- Non-destructive migration, idempotent refresh and correct stored row counts.
- Stable GSIS/ESPN/PFR ID matching, missing IDs and team abbreviation normalization.
- Timestamp and week-based depth-chart selection with no future leakage, including same-day pregame vs postgame observations when timestamps are available.
- No source evidence yields unranked players, never alphabetical QB1/RB1.
- Usage-based ordering selects the higher-usage RB over an alphabetically earlier backup; test a current QB starter taking over from a former starter, stale chart vs recent usage, tied roles, and roster eligibility.
- Team-last-three-games ranking versus player-last-three-games averaging, including bye weeks, inactive games, trades, and missing participation data.
- All configured player metric mappings, legitimate zeros, missing stats, small samples, and historical cutoff.
- Known average + valid defensive factor produces a numeric adjusted estimate; missing baseline remains unavailable with accurate reason.
- Game Outlook and Player Opportunities render both populated and degraded-data states; relevant-player limits and full roster toggles work.
- Existing DVP, weekly overview, schedule, rankings, Discord links and CLI tests remain passing.

Run the complete test suite (verify the current test command, historically `python -m unittest discover -s tests`). Run Streamlit smoke tests and a local app launch. If possible, execute a live reference-data refresh and verify the actual PHI/DAL week 12 output through the service and rendered page. Record the real commands and results. Do not claim live tests passed if network/data access was blocked. Backtest as a regression check when adequate historical DVP and player data exist; report insufficient coverage honestly and do not tune coefficients in this hotfix.

## 8. Deployment and database publishing

The live application is hosted on Streamlit Community Cloud and reads `data/nfl_stats.db` from its deployed repository. Repairing Python code alone will not populate that database.

- After a successful real-data ingestion, ensure the correct SQLite file is updated and passes `PRAGMA integrity_check` plus coverage checks. Ensure connections are closed and any WAL data has been safely checkpointed before publishing a self-contained snapshot; do not commit transient journal/WAL files.
- Preserve existing historical defense snapshots, roster records and schedules. Do not replace the production database with a test fixture or an empty/partial new database.
- Inspect the database diff/size and confirm player stats, depth charts and snap counts were populated where the provider supports them. If data are partially unavailable, clearly report which datasets remain missing rather than presenting deployment as fully fixed.
- Include the validated updated SQLite snapshot among the deliverables if permitted by the repository's data policy. If it cannot be safely refreshed, provide exact local refresh/validation commands and mark the deployment blocker.
- Do not push to main, deploy, alter secrets or overwrite remote production data unless explicitly authorized. Work on a hotfix branch if appropriate and preserve the user's unrelated working-tree changes.
- Document the steps to publish the updated database and restart/reboot the Streamlit app, and ensure the Discord host uses a compatible refreshed snapshot if necessary.

## 9. Acceptance criteria

The hotfix is complete when:

- The actual root cause(s) of the zero-game results and missing estimates are identified with evidence from the installed loader, normalized data, database or query path.
- The scraper produces actionable source-specific diagnostics rather than silently hiding incompatible schemas.
- Real player history is persisted and correctly joined to rostered players wherever upstream data are available.
- Established players with usable prior game data display correct game counts, averages and numeric adjusted estimates for supported metrics.
- No player is presented as QB1/RB1 solely because their name sorts first.
- Default relevant-player ordering is supported by credible pregame depth-chart or usage evidence, with uncertainty visible when necessary.
- The original reported matchup is rechecked, and the roles and baseline calculations for representative QB/RB players are explained using source records, without hard-coding player names.
- Missing data is handled explicitly; existing DVP outputs remain available.
- Historical data integrity and no-future-leakage guarantees are maintained.
- All feasible tests pass and remaining external blockers are identified precisely.
- The application remains compatible with Streamlit Community Cloud, with a clear database refresh/publishing workflow.

## 10. Final engineering report

Return a concise report containing:

1. Confirmed root causes, distinguishing them from initial hypotheses.
2. Before/after counts and source coverage for relevant tables and ID joins.
3. Upstream columns/schema issues found, and how they were corrected.
4. Before/after role, game count, baseline and adjusted estimate examples from the reported matchup, where real data are available, with the basis for role decisions.
5. Files modified and any dependency/schema changes.
6. Tests and live validation commands actually executed and their results.
7. Exact refresh, database publishing and Streamlit reboot instructions.
8. Any unresolved provider/data availability issues, assumptions or limitations.

Do not claim that adding a fallback label fixes missing player history. Do not manufacture roles, statistics or estimates to satisfy the acceptance criteria. Focus on resolving the upstream data problem first, then role assignment and clear presentation.

Begin by inspecting the current repository and database, reproducing the issue, and proceeding through the complete hotfix.
