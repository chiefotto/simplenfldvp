# Defense vs position

This app stores weekly NFL defense-vs-position tables and ranks the current slate from those numbers. The terminal reads the local database. It does not fetch new stats while you use it.

## Run it

Python 3.12. Install the packages in `.venv`, then:

```bash
pip install -r requirements.txt
python scraper/main.py
python cli.py
python -m interfaces.discord.bot
streamlit run interfaces/web/app.py
```

`python scraper/main.py` is the admin load. It downloads the CBS position-vs-defense pages for QB, RB, WR, and TE, downloads the regular-season schedule, weekly rosters, player ids, and team metadata through nflreadpy, and writes them into `data/nfl_stats.db`. Running it again updates the same rows in place. An empty roster, player, or team response does not erase the rows already stored. The database upgrade is `database.storage.initialize_database()`, which the scraper and the web app run themselves. Existing defense and schedule rows stay in place.

Tests:

```bash
python -m unittest discover -s tests
```

## Architecture

CBS pages and nflreadpy both land in SQLite. `database/analysis.py` scores a snapshot. Services in `services/` assemble matchups, fantasy boards, rosters, and outlooks. The CLI, Discord bot, and Streamlit app only present those results.

nflreadpy is the schedule, roster, player, and team client: `load_schedules`, `load_rosters_weekly`, `load_players`, and `load_teams`. The completed-week rule is still local. A week is complete only when every game in that week has both scores.

The web app reads the database. It does not call CBS or nflverse while you browse. Cached reads expire after five minutes, so a new scrape shows up without a restart. Discord `/outlook` commands link to that app. Set `WEB_APP_BASE_URL` in `.env` to the address where Streamlit is hosted. If it is empty, the bot says so instead of failing.

A hosted Streamlit process does not see a scrape that wrote a different SQLite file. Point the server, the bot, and the scraper at the same `data/nfl_stats.db`, or copy the file to the server after a refresh. This repo does not deploy the site.

## Rosters and players

Players are attached by season, game week, offensive team, and position. A Detroit wide-receiver matchup lists Detroit wide receivers. Names are display text. The stable id is the GSIS id. The list is alphabetical. It is not a usage ranking and it is not a start/sit recommendation. Roster status is shown as stored, including inactive and injured players.

If that week's roster is missing, the app uses the latest stored roster week at or before the game week and says so. It never uses a later roster for an earlier week. Matchup numbers still appear when the roster is missing.

Team abbreviations follow the CBS table already stored in `raw_dvp`. nflverse calls the Rams `LA`; the database stores `LAR`. Other unrecognized abbreviations are logged and kept.

## Web pages

`streamlit run interfaces/web/app.py` opens Weekly Overview. Schedule, Game Outlook, and Rankings are the other pages. The season and week stay in the URL:

```text
/?season=2026&week=12
/schedule?season=2026&week=12
/game?season=2026&week=12&game_id=...
/rankings?season=2026&week=12&position=WR
/?season=2026&week=12&metric=receiving_td&top=10
```

Kickoff times are labeled ET. HOT, WARM, NEUTRAL, COOL, and COLD are written as words. Rankings can be downloaded as CSV after filters. Filters do not recompute z-scores or league ranks.

Discord:

```text
/outlook weekly
/outlook game team:DET
/outlook rankings position:WR
```

Optional season, week, and metric arguments are accepted when they match a stored week and a configured stat.

`python cli.py` opens the menu. Type a command and press enter. `help` lists the forms. `quit` exits.

The stored season is the nflverse year, such as `2026`. The scraper labels the defense table as the last regular-season week in which every game has both scores. The current game week is the first schedule week that still has an unscored game. A Thursday game that already has a score does not finish the week.

Matchup and fantasy commands use the defense week immediately before the current game week when that snapshot exists. If it does not, they use the latest stored defense week and print a note. The schedule only decides which offense faces which defense. It never enters the z-score.

## How a z-score is computed

`database/analysis.py` scores one stored snapshot at a time. For each position and metric it keeps that column only when all 32 defenses have a real value. The mean and standard deviation are the population values for those 32 teams (`ddof=0`). A missing value is not replaced with zero. If the standard deviation is zero, every z-score is `0` and the label is NEUTRAL.

```text
z = (value - league mean) / league standard deviation
```

A positive z-score means the defense allows more than average, which is a weaker defense and a favorable spot for the opposing offense. Rank 1 is the largest z-score. Ties share a rank and the next rank skips.

Interceptions and fumbles are the exception. A higher count is a stronger defense, so those two z-scores are multiplied by `-1` before the rank and label.

Labels use the same cuts everywhere:

| z-score | label |
| --- | --- |
| 1.5 or higher | HOT |
| 1.0 up to but not including 1.5 | WARM |
| above -1.0 and below 1.0 | NEUTRAL |
| above -1.5 through -1.0 | COOL |
| -1.5 or lower | COLD |

`z == 1.0` is WARM. `z == -1.0` is COOL. `z == -1.5` is COLD.

These commands describe a position against a defense. They do not know snap share, target share, injuries, or which player to start.

## Commands

`schedule` lists the current week's games, including games that already have a score. It does not use the defense table.

`dvp` prints the latest stored defense table as CBS published it. Empty stat columns are hidden.

`defense` ranks a defense against all 32 teams. `defense det` is Detroit's own defense. `defense wr` is every defense at wide receiver. `defense det wr` is one team and one position. Each row is one metric, with the raw value, league mean, z-score, league rank, and label. Passing stats are skipped for RB, WR, and TE when they are not populated for all 32 defenses. Receiving stats are skipped for QB the same way. Add `raw` for the original CBS numbers: `defense raw`, `defense det raw`.

`matchups` is the same labeled table from the offense's side. The Bears row in a Packers game is the Packers defense. `matchups det` is Detroit's opponent. `matchups wr` is every offense at wide receiver. `matchups det wr` is both. A team with no game prints a bye message. Add `raw` for the CBS numbers. This is the full table. It is not the ranked `matchup` command.

`matchup best` scans every scheduled offense and every configured counting stat, then sorts by that one stat's existing z-score. The top row is the largest single outlier on the slate. `weekly_rank` is that slate order. `DEF RANK` is the defense's league rank for that stat. `matchup best 10` changes how many rows are shown. Fantasy points are not in this list.

`matchup best receptions` keeps only that stat and includes every position configured for it. Receptions, targets, receiving yards, and receiving touchdowns include RB, WR, and TE. Rushing yards and rushing touchdowns include QB and RB. Passing yards and passing touchdowns are QB only. Rushing attempts are RB only. Each row still uses that position's own z-score, so a tight end at +2.90 can rank ahead of a wide receiver at +1.72 without comparing their raw receptions. `DEF RANK` stays the rank inside that position. `weekly_rank` is redone for the filtered list. `matchup best receptions 10` changes the count. The same form works for every alias.

The configured stats are:

- QB: passing yards, passing touchdowns, rushing yards, rushing touchdowns
- RB: rushing attempts, rushing yards, rushing touchdowns, targets, receptions, receiving yards, receiving touchdowns
- WR and TE: targets, receptions, receiving yards, receiving touchdowns

`matchup best wr` makes one row per offense. The score is the average of that position's configured z-scores. A missing stat is left out of the average. The result is not standardized again. The same form works for qb, rb, and te. The breakdown under the table is rank 1.

`matchup best wr receptions` ranks one stat for one position. Aliases are `receptions`, `targets`, `receiving_yards`, `receiving_td`, `rushing_yards`, `rushing_td`, `rushing_attempts`, `passing_yards`, and `passing_td`. An alias that does not belong to the position is rejected.

`matchup defense det wr` prints Detroit's wide-receiver profile for the stored snapshot, including fantasy points, with no opponent. `matchup offense mia wr` finds Miami's opponent and prints the wide-receiver average plus the component stats.

`matchup game mia` finds Miami's game and lists the HOT and WARM spots for both offenses. HOT is a major defensive weakness and WARM is an above-average weakness, both already labeled on that position's own z-score. Miami's rows are the opponent's defense. The other section is the opponent's offense against Miami's defense. A side with neither label prints `No HOT or WARM spots.`

`matchup chi` ranks every configured stat for Chicago's offense against its opponent, from the highest z-score to the lowest. The top rows are the spots where that defense is weakest for a Chicago skill group. `matchups chi` remains the full labeled table.

`fantasy best` ranks every scheduled QB, RB, WR, and TE spot by the defense's fantasy points allowed. The score is the existing FPTS z-score for that position. Quarterback points are not compared with wide-receiver points until both have been standardized against their own 32-team group. The top 5 are the best fantasy matchups. `fantasy worst` reverses the sort, so rank 1 is the most difficult positional matchup and its defensive rank is usually near 32. `fantasy position wr` lists every scheduled offense at that position, from most favorable to least favorable. `fantasy offense det wr` finds Detroit's opponent and prints that defense's wide-receiver fantasy-points profile.

`fantasy_score`, `matchup_score`, and `opportunity_score` are normalized defensive signals. They are not projections, probabilities, or player start/sit advice.

## Discord bot

The bot is a thin client over the same services. It does not calculate matchup scores.

1. Create an application in the Discord Developer Portal and add a bot user.
2. Copy the bot token into a local `.env` file. Start from `.env.example`.
3. Set `DISCORD_BOT_TOKEN`. Leave `DISCORD_GUILD_ID` empty to sync commands globally, or set it to a development server ID so commands show up faster.
4. `DISCORD_ADMIN_ROLE_ID` is optional. When it is set, members with that role are treated as admins. The role ID stays in the Discord adapter. `WEB_APP_BASE_URL` is the public Streamlit address used by `/outlook`. Leave it empty until the site has an address.
5. Invite the bot with the `bot` and `applications.commands` scopes. It does not need administrator permission.
6. Install the Discord packages and start the bot from the project root:

```bash
pip install -r requirements.txt
python -m interfaces.discord.bot
```

7. In the server, run `/system ping`. The reply is `Bot is online.`
8. Run `/matchup best` and choose a position. The bot defers, calls the existing matchup service, and replies with the current slate. `/matchup opportunities` is the mixed board. `/matchup opportunities metric:receptions top:10` keeps receptions and includes every position configured for that stat. `/matchup game team:MIA` lists the HOT and WARM spots for both offenses in Miami's game. `/matchup slate` lists those spots for every game. `/matchup stats team:CHI` ranks every configured stat for Chicago's offense. `/outlook weekly`, `/outlook game team:DET`, and `/outlook rankings position:WR` return links to the web app.

If `DISCORD_BOT_TOKEN` is missing, the process stops with `DISCORD_BOT_TOKEN is not configured.` The token is not written to the log.
