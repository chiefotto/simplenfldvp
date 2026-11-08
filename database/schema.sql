CREATE TABLE IF NOT EXISTS raw_dvp (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    season TEXT NOT NULL,
    week INTEGER NOT NULL,
    team TEXT NOT NULL,
    team_abbr TEXT NOT NULL,
    position TEXT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    Passing_Att        REAL,
    Passing_Cmp        REAL,
    Passing_Yd         REAL,
    Passing_TD         REAL,
    Passing_Int        REAL,
    Passing_Rate       REAL,
    Rushing_Att        REAL,
    Rushing_Yd         REAL,
    Rushing_Avg        REAL,
    Rushing_TD         REAL,
    FL                 REAL,
    FPTS               REAL,
    Receiving_Targt    REAL,
    Receiving_Recpt    REAL,
    Receiving_Yd       REAL,
    Receiving_Avg      REAL,
    Receiving_TD       REAL,

    UNIQUE(season, week, team, position)
);

CREATE INDEX IF NOT EXISTS idx_raw_dvp_team_position
    ON raw_dvp (team, position);

CREATE INDEX IF NOT EXISTS idx_raw_dvp_season_week_position
    ON raw_dvp (season, week, position);

CREATE INDEX IF NOT EXISTS idx_raw_dvp_season_week_team_position
    ON raw_dvp (season, week, team, position);

CREATE INDEX IF NOT EXISTS idx_raw_dvp_season_week_team_abbr
    ON raw_dvp (season, week, team_abbr);

CREATE TABLE IF NOT EXISTS schedule (
    game_id TEXT PRIMARY KEY,
    season TEXT NOT NULL,
    week INTEGER NOT NULL,
    game_type TEXT NOT NULL,
    gameday TEXT,
    gametime TEXT,
    away_team TEXT NOT NULL,
    home_team TEXT NOT NULL,
    away_score REAL,
    home_score REAL
);
