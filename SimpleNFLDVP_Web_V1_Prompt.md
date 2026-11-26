# SimpleNFLDVP — Web V1 Implementation

## Role and objective

Act as a senior Python software engineer, data engineer, and frontend developer. You are working within the existing SimpleNFLDVP repository.

Your task is to implement a complete, functional V1 web application for SimpleNFLDVP, extend its NFL data ingestion capabilities, and integrate the web application with the existing Discord bot.

Implement the entire feature set in this session. Do not stop at planning, scaffolding, or providing implementation examples. Inspect the existing repository, implement the changes, test them, fix discovered issues, and update the documentation.

Prioritize simplicity, maintainability, correctness, and practical functionality over architectural sophistication.

---

## 1. Project context

SimpleNFLDVP is an NFL fantasy football matchup analysis application that currently:

- Scrapes defense-vs-position statistics from CBS.
- Retrieves NFL schedule data from nflverse.
- Stores weekly statistical snapshots in SQLite.
- Calculates population-based z-scores for defensive statistics by position.
- Assigns HOT, WARM, NEUTRAL, COOL, and COLD labels.
- Identifies favorable and unfavorable offensive matchups.
- Ranks statistical opportunities across teams and positions.
- Exposes its functionality through a CLI and Discord bot.
- Separates its core analytics and business logic from its interfaces.

The existing application identifies defensive weaknesses and translates those weaknesses into offensive positional opportunities.

The next evolution of the project is to associate those opportunities with actual rostered NFL players and expose the data through an interactive, shareable web application.

The core product philosophy is:

**Identify defensive weaknesses → identify favorable offensive positional matchups → identify relevant players.**

This is a matchup research tool, not a player projection engine.

---

## 2. Repository inspection

Before modifying anything:

- Inspect the repository structure.
- Read the README and any repository-specific instructions.
- Understand the current scraper implementation.
- Understand the SQLite schema and database access patterns.
- Inspect the existing analysis and service modules.
- Understand how the CLI and Discord bot consume services.
- Identify reusable functionality.
- Review the existing tests and run the baseline test suite.
- Inspect the current dependency and Python version requirements.

Use the actual repository implementation as the source of truth. Do not assume that file names, service signatures, or database schemas match this specification exactly.

Work on a dedicated feature branch if possible. Preserve unrelated existing changes.

---

## 3. Technology stack

Use the following technologies:

| Component | Technology |
|---|---|
| Language | Python |
| Database | Existing SQLite database |
| Defense-vs-position statistics | Existing CBS scraper |
| NFL schedules | nflreadpy |
| NFL rosters | nflreadpy |
| Player metadata | nflreadpy |
| Team metadata | nflreadpy |
| Data manipulation | Existing utilities, Polars or Pandas as appropriate |
| Web frontend | Streamlit |
| Discord integration | Existing discord.py implementation |
| Testing | Existing test framework |

Use native Streamlit components wherever practical.

Do not introduce React, Next.js, Node.js, FastAPI, Flask, PostgreSQL, Redis, or other infrastructure that is unnecessary for V1.

Charts are optional. Prefer well-designed tables and clear data presentation over decorative visualizations.

---

## 4. Architectural requirements

Preserve the existing separation between data ingestion, persistence, analytics, services, and interfaces.

The desired architecture is:

```text
CBS Scraper           nflreadpy
     |                    |
     |           Schedules, Rosters,
     |           Players, Teams
     |                    |
     +---------+----------+
               |
             SQLite
               |
       Shared Python Services
               |
       +-------+-------+
       |       |       |
      CLI   Discord  Streamlit
```

Requirements:

- SQLite remains the local source of truth.
- The scraper is responsible for retrieving external data.
- The database layer is responsible for persistence and retrieval.
- The service layer is responsible for assembling analytical results.
- Interfaces are responsible for presenting results.
- Streamlit must not independently implement the statistical methodology.
- Discord must not independently implement the statistical methodology.
- Reuse existing analysis and service functions wherever possible.
- Do not duplicate business logic across interfaces.
- Avoid unnecessary abstractions, excessive class hierarchies, and architectural rewrites.
- Do not break existing CLI or Discord commands.

Introduce new modules only where they provide a clear separation of responsibilities.

---

## 5. NFL data ingestion migration

Replace the existing direct nflverse schedule retrieval implementation with nflreadpy.

The underlying provider remains nflverse, but nflreadpy should become the standard interface for accessing its datasets.

Use the appropriate supported functions, including:

```python
import nflreadpy as nfl

nfl.load_schedules(...)
nfl.load_rosters_weekly(...)
nfl.load_players()
nfl.load_teams()
```

Verify the actual package signatures, returned schemas, data types, and compatibility with the repository's Python version before implementation.

### Schedule ingestion

Replace the existing schedule downloader while preserving the behavior expected by existing services.

Retain the relevant schedule fields, including:

- Game identifier.
- Season.
- Week.
- Game type.
- Home team.
- Away team.
- Game date.
- Kickoff time.
- Home score.
- Away score.
- Other existing required fields.

Preserve the application's existing regular-season filtering and completed-week detection logic.

In particular, a partially completed week must not be considered a fully completed week merely because one or more games have finished.

Do not replace reliable existing week-detection logic with an approximate current-week utility.

### Weekly roster ingestion

Implement ingestion of weekly NFL rosters.

Store the relevant fields, where available:

- Season.
- Week.
- Stable player identifier.
- Player name.
- Team.
- Position.
- Roster status.
- Jersey number.
- Headshot URL.

Support QB, RB, WR, and TE for matchup analysis.

Preserve roster status information rather than assuming that all rostered players are available to play.

### Player metadata

Ingest only the player metadata necessary for the V1 interface.

Use stable identifiers to associate player records with weekly roster entries.

Avoid relying on player names as unique identifiers.

### Team metadata

Retrieve and persist relevant NFL team metadata:

- Team abbreviation.
- Team name.
- Team logo URL.
- Primary and secondary team colors, where available.

Normalize team abbreviations across CBS, nflreadpy, and the existing database.

Explicitly handle abbreviation differences rather than silently dropping unmatched teams.

### Ingestion behavior

- External requests should occur during data ingestion, not on every web page visit.
- Integrate the new ingestion functionality into the existing administrative scraper workflow.
- Make repeated ingestion safe and idempotent.
- Preserve existing weekly snapshots.
- Avoid destructive database migrations.
- Handle network failures gracefully.
- Do not overwrite valid existing data with empty or invalid responses.
- Provide useful ingestion logs.
- Do not introduce fabricated production data.

If the upcoming week's roster has not yet been published, display an explicit unavailable state or use a clearly identified earlier roster snapshot. Never silently use a future roster for a historical matchup.

---

## 6. Database changes

Extend the existing SQLite schema as needed to support weekly roster snapshots, player metadata, and team metadata.

A conceptual schema would include:

```text
Existing:
    defense statistics
    schedules

New:
    weekly rosters
    players
    teams
```

Adapt the implementation to the repository's existing database conventions.

Requirements:

- Use stable identifiers and appropriate unique constraints.
- Add indexes for common season, week, team, and position lookups.
- Preserve existing stored data.
- Support historical weekly lookups.
- Ensure ingestion can update existing records without generating duplicates.
- Keep database paths configurable and compatible with the existing application.
- Ensure the scraper, CLI, Discord bot, and web application can use the same database.

Do not require users to delete and recreate their database to upgrade the application.

---

## 7. Preserve existing statistical methodology

This is a critical requirement.

Do not redesign or replace the existing analytical engine.

Preserve the current:

- Population-based z-score calculations.
- Position-specific league comparisons.
- Existing treatment of missing metrics.
- Existing treatment of zero standard deviations.
- Directional handling of interceptions and fumbles.
- Defensive rankings and tie behavior.
- Offensive matchup rankings.
- Fantasy-points matchup rankings.
- Configured positional metric definitions.
- Historical snapshot selection behavior.

Preserve the existing flag thresholds:

| Z-score | Label |
|---|---|
| Greater than or equal to 1.5 | HOT |
| Greater than or equal to 1.0 and below 1.5 | WARM |
| Greater than -1.0 and below 1.0 | NEUTRAL |
| Greater than -1.5 and less than or equal to -1.0 | COOL |
| Less than or equal to -1.5 | COLD |

A positive matchup z-score represents a favorable opportunity for the offense.

Keep defense snapshot week and matchup game week conceptually distinct.

For example, Week 12 matchup analysis would normally use the completed Week 11 defensive snapshot and Week 12 roster information.

Preserve existing fallback behavior, but display the actual snapshot being used.

Do not introduce future data into historical matchup analysis.

---

## 8. Shared outlook and roster services

Extend the existing service layer to support the new web application.

Reuse existing functions where possible rather than recreating them.

Introduce shared functionality for:

### Weekly outlook

Return the complete analytical outlook for a selected season and game week.

Include relevant fields such as:

- Game ID.
- Offensive team.
- Opposing defense.
- Position.
- Metric.
- Raw defensive statistic.
- League average.
- Z-score.
- Defensive league rank.
- Weekly matchup rank where applicable.
- Flag.
- Defense snapshot week.
- Game information.

### Stat category rankings

Support retrieving the best and worst matchups for each configured metric.

For example:

- Passing yards.
- Passing touchdowns.
- Rushing attempts.
- Rushing yards.
- Rushing touchdowns.
- Targets.
- Receptions.
- Receiving yards.
- Receiving touchdowns.

Use the existing configured position-to-metric relationships.

Receiving touchdowns, for example, can include RB, WR, and TE opportunities where applicable.

Use standardized z-scores rather than comparing incompatible raw positional statistics.

### Positional outlooks

Support retrieving the existing aggregate positional matchup scores.

Also provide descriptive flag counts:

- HOT count.
- WARM count.
- NEUTRAL count.
- COOL count.
- COLD count.

These counts should complement the existing scores rather than replace them.

Do not introduce arbitrary weighted recommendation formulas.

Positions have different numbers of configured metrics, and correlated statistics can represent overlapping defensive weaknesses. Avoid presenting raw flag counts as a statistically validated cross-position ranking.

### Game outlook

Return the complete matchup analysis for both offenses in a selected game.

For each offense, analyze the opposing team's defense.

Provide:

- Favorable opportunities.
- Unfavorable opportunities.
- Positional matchup scores.
- Ranked statistical categories.
- Relevant rostered players.
- Full statistical breakdown.

### Player associations

Associate positional matchup opportunities with players using:

```text
Season + Game Week + Offensive Team + Position
```

For example:

```text
Offense: Detroit
Opponent: Chicago
Position: WR
Metric: Receiving touchdowns
Flag: HOT
```

The relevant player list should contain Detroit wide receivers, not Chicago wide receivers.

Player associations must be derived from both the position and offensive team of the matchup.

For V1:

- List relevant rostered players.
- Show their roster status when available.
- Highlight unavailable or non-active players appropriately.
- Use player headshots where available.
- Avoid duplicate player records.
- Use neutral ordering, such as alphabetical ordering, unless an existing reliable ordering is available.

Do not rank players by predicted performance.

Do not claim that roster association constitutes an individual start/sit recommendation.

---

## 9. Streamlit application

Implement a multipage Streamlit application inside the existing repository.

The application should have three primary navigation pages and one game detail page:

1. Weekly Overview.
2. Schedule.
3. Rankings.
4. Game Outlook.

Weekly Overview should be the default landing page.

Game Outlook should be accessible through links and selections from the other pages without requiring a separate application.

### Shared navigation

Provide consistent navigation throughout the application.

Include:

- SimpleNFLDVP branding.
- Weekly Overview.
- Schedule.
- Rankings.
- Season selector.
- Week selector.
- Data freshness information.
- Defense snapshot information.

Default to the application's current game week when possible.

Preserve the selected season and week during navigation.

Support direct links to specific weeks and games.

Use supported Streamlit navigation and query parameter functionality. Verify how query parameters behave during multipage navigation and browser refreshes.

---

## 10. Page 1 — Weekly Overview

### Purpose

Provide an immediate, league-wide view of the best statistical matchup opportunities for the selected week.

This should be the primary landing page.

### Layout

Display:

- Selected season and week.
- Defensive data snapshot being analyzed.
- Optional summary counts of games and favorable matchup flags.
- A responsive collection of stat-specific leaderboard tables.

Each configured statistical category should have its own table.

Example:

```text
PASSING TOUCHDOWNS       RUSHING YARDS

1. Team A QB +2.31       1. Team D RB +2.52
2. Team B QB +1.92       2. Team E RB +2.12
3. Team C QB +1.71       3. Team F QB +1.82

RECEIVING TOUCHDOWNS      RECEPTIONS

1. Team G WR +2.41       1. Team J TE +2.60
2. Team H TE +2.01       2. Team K WR +2.11
3. Team I RB +1.72       3. Team L RB +1.70
```

This is an illustrative layout, not production data.

### Leaderboard requirements

Each table should contain:

- Rank.
- Offensive team.
- Opposing defense.
- Position.
- Z-score.
- Flag.
- Game outlook navigation where practical.

Use existing metric rankings and z-score methodology.

By default, display the top five matchups in every category.

### Interactive controls

Support:

- Adjustable number of results per category.
- Top 3, 5, 10, 15, 20, or a reasonable custom value.
- Position filtering.
- Metric category filtering.
- Flag filtering.
- Best versus worst matchup toggle.

The result count should apply consistently across all leaderboard tables.

Do not create artificial rows when fewer results are available.

Mixed-position metrics should support all applicable positions.

For example, the receiving touchdowns table may contain wide receivers, tight ends, and running backs.

Include an additional positional summary section using the existing positional matchup scores, with access to QB, RB, WR, and TE rankings.

Keep the layout compact, readable, and useful on both desktop and mobile.

---

## 11. Page 2 — Schedule

### Purpose

Allow users to browse the NFL schedule and select individual games for deeper matchup analysis.

### Layout

Display all games for the selected season and week, grouped by game date.

Each game should appear as a clearly identifiable game card or equivalent interactive row.

Display:

- Away team name and logo.
- Home team name and logo.
- Game date.
- Kickoff time with a clearly identified timezone.
- Game score when available.
- HOT flag count.
- WARM flag count.
- An action to open the game outlook.

Flag counts should be derived from the shared matchup service.

Do not independently calculate or infer matchup flags in the schedule UI.

The schedule should remain useful even if matchup statistics or roster data are unavailable.

### Interaction

Selecting a game should navigate to Game Outlook using the selected game's stable identifier.

Users must be able to return to the schedule without losing their selected season and week.

---

## 12. Page 3 — Game Outlook

### Purpose

Provide a comprehensive view of an individual game's statistical matchup opportunities and the players associated with them.

### Game header

Display:

- Both teams and logos.
- Season and week.
- Game date and kickoff time.
- Game score when applicable.
- Defense snapshot week.

### Offensive breakdown

Create distinct sections for each team's offense.

Each team's offensive section should analyze the opposing defense.

Provide a summary of the existing aggregate positional matchup scores for:

- QB.
- RB.
- WR.
- TE.

Display the strongest statistical opportunities first.

### Opportunity presentation

For each favorable opportunity, display:

- Position.
- Statistical category.
- Z-score.
- Flag.
- Relevant raw defensive statistic.
- League average.
- Defensive rank, if available.
- Relevant offensive players.

Example:

```text
DETROIT OFFENSIVE OUTLOOK

WR — Receiving Touchdowns

HOT | Z-score: +2.34

Chicago allows an above-average number
of receiving touchdowns to wide receivers.

Relevant Detroit wide receivers:
    Player A
    Player B
    Player C
```

Use deterministic descriptions or templates rather than introducing an LLM dependency.

### Player presentation

Where data is available, display:

- Player name.
- Position.
- Headshot.
- Roster status.
- Jersey number.

Avoid repeatedly displaying identical large player lists. Group opportunities by position, use compact player rows, or provide expandable sections where appropriate.

### Additional views

Include:

- Strongest HOT and WARM opportunities.
- Unfavorable COOL and COLD opportunities.
- Full statistical breakdown, including NEUTRAL metrics.
- Overall positional matchup rankings.
- Flag counts by position.

Use expandable sections or tabs to prevent the page from becoming excessively long.

Both offenses must receive equivalent treatment.

Do not display one team's defensive weakness as an opportunity for that same team's offense.

Provide an understandable fallback when roster or statistical data is unavailable.

---

## 13. Page 4 — Rankings

### Purpose

Provide a comprehensive, interactive table for exploring the complete analytical dataset.

This is the advanced research page for users who want access to more than the summarized weekly outlook.

### Ranking modes

Support the following views, using existing service functionality:

1. Offensive matchup rankings.
2. Defensive rankings.
3. Aggregate positional matchup rankings.
4. Fantasy-points matchup rankings.

### Table fields

Display relevant fields depending on the selected ranking mode:

- Team.
- Opponent, where applicable.
- Position.
- Metric.
- Raw value.
- League average.
- Z-score.
- Defensive league rank.
- Weekly matchup rank.
- Flag.

### Interactive functionality

Provide:

- Team search.
- Offensive team filtering.
- Opposing defense filtering where applicable.
- Position filtering.
- Metric filtering.
- Multiple flag selection.
- Ascending and descending sorting.
- Best and worst rankings.
- Reset filters.
- CSV download of the filtered results.

Use appropriate native Streamlit dataframe functionality.

Apply consistent conditional styling to HOT, WARM, NEUTRAL, COOL, and COLD values.

The table should include all available valid records rather than being limited to favorable matchups.

Preserve the distinction between defense rankings, offense matchup rankings, and filtered display order.

Filtering must not silently recalculate the underlying league ranking or z-scores.

---

## 14. UI and design requirements

The application should look like a clean, modern sports analytics dashboard.

Prioritize data density, readability, and ease of exploration.

Design direction:

- Professional sports analytics aesthetic.
- Clear page hierarchy.
- Compact tables.
- Consistent spacing.
- Strong typography.
- Minimal visual clutter.
- Team logos where appropriate.
- Responsive layouts.
- Consistent navigation.
- Accessible color contrast.
- Readable numerical formatting.

Use the following general flag styling:

| Flag | Visual treatment |
|---|---|
| HOT | Strong green |
| WARM | Amber or lighter green |
| NEUTRAL | Muted gray |
| COOL | Light blue |
| COLD | Strong blue |

Always include the textual label. Do not rely solely on color.

Display z-scores consistently, preferably to two decimal places with explicit positive and negative signs.

Use team colors sparingly so they do not interfere with flag styling.

Use Streamlit configuration and native components where possible.

Avoid fragile CSS selectors, excessive custom HTML, and unnecessary third-party UI components.

Handle missing logos and player headshots gracefully.

Do not introduce large charts or decorative graphics at the expense of usability.

---

## 15. Shareable URLs

The web application should support direct, shareable links to relevant analytical views.

Conceptual examples:

```text
/?season=2026&week=12

/schedule?season=2026&week=12

/game?season=2026&week=12&game_id=...

/rankings?season=2026&week=12&position=WR

/?season=2026&week=12&metric=receiving_td&top=10
```

These are conceptual URLs. Implement the actual supported routing structure for the selected Streamlit version.

Requirements:

- Direct links should open the correct page and selected context.
- Browser refreshes should retain the relevant context.
- Game-specific links should resolve the correct game.
- Invalid query parameters should be handled gracefully.
- Unsupported filters should fall back to reasonable defaults.
- Season and week context should be preserved during navigation.
- Links should not contain credentials or sensitive information.

A new website or report file must not be generated for each Discord command.

The existing web application should render the requested analytical view based on URL parameters.

---

## 16. Discord bot integration

Extend the existing Discord bot with an outlook command or command group that follows its current command conventions.

Support at minimum the equivalent of:

```text
/outlook weekly

/outlook game team:DET

/outlook rankings position:WR
```

Where practical, support optional season, week, and metric parameters.

The weekly command should return a link to the Weekly Overview page.

The game command should resolve the selected team's game and return a direct Game Outlook link.

The rankings command should return a link with the relevant position or metric filters.

Use clean Discord embeds and link buttons where supported.

Example response:

```text
NFL Weekly Outlook — Week 12

Explore this week's best statistical
opportunities, positional matchups,
and relevant NFL players.

[View Weekly Outlook]
```

Add a configurable web application base URL, such as:

```text
WEB_APP_BASE_URL=
```

Update the example environment configuration.

If the base URL is missing, provide a helpful response rather than crashing the bot.

Preserve all existing commands and permission behavior.

Do not introduce secrets into source control.

---

## 17. Performance and caching

The application operates on a relatively small analytical dataset.

Favor simple and predictable implementations.

Requirements:

- Cache appropriate database query results using Streamlit's supported caching functionality.
- Do not fetch external data on every Streamlit rerun.
- Avoid repeated calculations when existing analytical results can be reused.
- Ensure cache invalidation or expiration allows newly ingested data to become visible.
- Avoid loading unnecessary historical datasets.
- Use efficient joins and database lookups.
- Ensure SQLite connections are managed safely across Streamlit sessions.

The web application should remain primarily read-only.

Do not expose administrative scraper actions to public users.

---

## 18. Suggested repository organization

Adapt this structure to the actual existing repository:

```text
simplenfldvp/
├── database/
│   └── existing database modules
├── scraper/
│   ├── existing CBS scraper
│   └── nfl_data.py
├── services/
│   ├── existing analytical services
│   ├── roster_service.py
│   └── outlook_service.py
├── interfaces/
│   ├── discord/
│   └── web/
│       ├── app.py
│       ├── pages/
│       │   ├── overview.py
│       │   ├── schedule.py
│       │   ├── rankings.py
│       │   └── game_outlook.py
│       ├── components/
│       │   ├── game_card.py
│       │   ├── flag_table.py
│       │   ├── player_card.py
│       │   └── leaderboard.py
│       └── utils.py
├── .streamlit/
│   └── config.toml
├── data/
├── tests/
├── cli.py
├── requirements.txt
└── README.md
```

This structure is guidance, not a requirement to create every listed file.

Avoid empty modules, trivial wrappers, and premature abstractions.

---

## 19. Error handling and edge cases

Explicitly account for:

- Empty database.
- Missing defensive snapshots.
- Missing current-week rosters.
- Missing individual player metadata.
- Missing team logos.
- Team abbreviation inconsistencies.
- Bye weeks.
- Traded players.
- Duplicate roster records.
- Inactive or injured players.
- Completed and partially completed games.
- Invalid game identifiers.
- Unsupported seasons or weeks.
- Missing statistical values.
- Empty filter results.
- External data retrieval failures.
- Historical roster and defense snapshot mismatches.

Display helpful user-facing messages rather than raw Python tracebacks.

Do not silently substitute zeros for unavailable statistics.

The absence of roster information should not prevent matchup analysis from being displayed.

---

## 20. Testing requirements

Preserve and run all existing tests.

Add meaningful tests covering the new functionality.

### Data ingestion tests

- Schedule ingestion from nflreadpy.
- Weekly roster ingestion.
- Team abbreviation normalization.
- Idempotent database updates.
- Preservation of historical records.
- Handling missing and malformed data.
- Database migration behavior.

### Analytical regression tests

Verify that existing statistical results remain unchanged for equivalent inputs.

Test:

- Z-score calculations.
- Flag thresholds.
- Ranking direction.
- Tie behavior.
- Missing metric behavior.
- Snapshot selection.
- Partially completed weeks.

### Outlook service tests

Test:

- Weekly outlook generation.
- Stat-specific leaderboard ordering.
- Adjustable top-N results.
- Best and worst matchup ordering.
- Position filtering.
- Game outlook generation for both offenses.
- Correct offense-to-opposing-defense relationships.
- Correct player association by season, week, team, and position.
- Missing roster behavior.
- Prevention of historical future-data leakage.

### Discord tests

Test:

- Weekly outlook URL generation.
- Game-specific URL generation.
- Position-specific rankings URL generation.
- Missing base URL configuration.
- Invalid team and bye-week handling.

### Web application tests

Use Streamlit's supported application testing functionality where practical.

Verify:

- All four pages can render.
- Navigation works.
- Season and week selections work.
- Filters function correctly.
- Adjustable leaderboard counts work.
- Game selection resolves the correct matchup.
- Direct URLs preserve the intended context.
- Empty-data states render without crashing.
- CSV exports respect active filters.

Use deterministic test fixtures and mock external requests where necessary.

Synthetic data is acceptable for tests only. Do not silently use mock data in production.

Run the actual test suite and application smoke tests. Fix failures before considering implementation complete.

---

## 21. Documentation and configuration

Update the README to explain:

- The updated application architecture.
- Dependencies and supported Python versions.
- How nflreadpy is used.
- How to initialize or migrate the database.
- How to refresh NFL statistics and rosters.
- How to launch the CLI.
- How to launch the Discord bot.
- How to launch the Streamlit application.
- How to configure Discord-generated links.
- How the season, game week, and defense snapshot week relate.
- How player associations work.
- How to run tests.
- Known limitations.

Provide working commands appropriate to the final implementation, conceptually:

```bash
pip install -r requirements.txt

python scraper/main.py

python cli.py

python -m interfaces.discord.bot

streamlit run interfaces/web/app.py
```

Document any deviations from these commands.

Document how the hosted web application will access refreshed data. If the scraper, Discord bot, and Streamlit application run in different environments, explain how the database must be shared or published safely.

Do not assume that writing to a local SQLite file automatically updates a separately hosted Streamlit application.

Provide deployment guidance, but actual cloud deployment is outside the scope of this task.

---

## 22. Explicitly out of scope for V1

Do not implement:

- User authentication.
- User accounts.
- Personalized fantasy leagues.
- Sleeper league integration.
- Individual player projections.
- Individual player performance prediction.
- AI-generated recommendations.
- Betting recommendations.
- Live play-by-play tracking.
- Advanced injury prediction.
- Player usage-based rankings.
- Custom scoring model builders.
- Payments or subscriptions.
- A replacement for the existing CBS scraper.
- Additional frontend frameworks.
- Separate API infrastructure.
- Unnecessary cloud services.

Design the application so these features can be introduced later without requiring an immediate rewrite, but do not implement them now.

---

## 23. Implementation sequence

Complete the work in the following logical order:

1. Inspect the repository and establish baseline behavior.
2. Migrate schedule ingestion to nflreadpy.
3. Implement weekly roster, player, and team metadata ingestion.
4. Extend and migrate the SQLite database.
5. Implement shared roster and outlook services.
6. Validate existing analytical behavior.
7. Build the Streamlit application and shared navigation.
8. Implement Weekly Overview.
9. Implement Schedule.
10. Implement Game Outlook.
11. Implement Rankings.
12. Implement shareable URL handling.
13. Integrate the Discord outlook commands.
14. Add and run tests.
15. Perform application smoke tests and fix discovered issues.
16. Update the README and configuration examples.
17. Review the final changes for correctness and unnecessary complexity.

Maintain the full product context throughout implementation.

Do not treat each phase as an isolated application.

Continue through all phases without requiring additional user approval for ordinary implementation decisions.

If a nonessential issue cannot be resolved, document it and continue with the remaining implementation.

---

## 24. Acceptance criteria

The implementation is complete when:

- Existing CLI functionality continues to work.
- Existing Discord functionality continues to work.
- Schedule ingestion uses nflreadpy.
- Weekly roster data is ingested and persisted.
- Player and team metadata is available where supported.
- Existing databases can be upgraded without losing data.
- Existing analytical methodology remains unchanged.
- The Streamlit application launches successfully.
- Weekly Overview displays multiple stat-specific leaderboards.
- Users can change the number of results shown.
- Users can filter opportunities by position and metric.
- Schedule displays the selected week's games.
- Selecting a game opens its Game Outlook.
- Game Outlook displays both offensive matchup profiles.
- Favorable positional opportunities display relevant offensive players.
- Rankings provides interactive access to the complete dataset.
- HOT, WARM, NEUTRAL, COOL, and COLD labels appear consistently.
- Users can navigate between pages while preserving season and week.
- Direct links open the intended analytical context.
- Discord can generate weekly and game-specific links.
- Missing data is handled gracefully.
- No fabricated production data is introduced.
- Existing and new automated tests pass, except for any clearly documented pre-existing or environment-related blockers.
- Documentation contains complete setup and usage instructions.

---

## 25. Final deliverables

After implementation, provide a concise engineering summary containing:

1. What was implemented.
2. The resulting architecture.
3. Important files created or modified.
4. Database schema changes.
5. Dependency changes.
6. New Discord commands.
7. How to run the web application.
8. How to refresh the data.
9. Test results, including actual commands executed.
10. Any remaining limitations or deployment considerations.
11. Any material assumptions or deviations from this specification.

Be transparent about features that could not be tested against live NFL data.

Do not claim that a feature works unless it was implemented and reasonably validated.

The final result should be a working, maintainable extension of SimpleNFLDVP, not a proof-of-concept disconnected from the existing application.

**Begin by inspecting the repository, then proceed with the complete implementation.**
