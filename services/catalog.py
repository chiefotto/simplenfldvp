from database.matchups import METRIC_ALIASES, POSITION_METRICS
from database.queries import known_team_abbrs
from services.errors import AppError

POSITIONS = ("qb", "rb", "wr", "te")
DEFAULT_TOP_N = 5
MAX_TOP_N = 32

COMMANDS = [
    {
        "name": "matchup best",
        "description": "Rank the strongest individual defensive vulnerabilities on the slate. matchup best 10 changes the count.",
        "parameters": [
            {"name": "top", "required": False, "default": DEFAULT_TOP_N, "description": "How many rows to show, from 1 to 32."},
        ],
        "example": "matchup best",
        "access": "PUBLIC",
    },
    {
        "name": "matchup best position",
        "description": "Rank offenses by the average z-score of that position's configured stats.",
        "parameters": [
            {"name": "position", "required": True, "description": "qb, rb, wr, or te."},
        ],
        "example": "matchup best wr",
        "access": "PUBLIC",
    },
    {
        "name": "matchup best metric",
        "description": "Rank offenses by one stat's league z-score.",
        "parameters": [
            {"name": "position", "required": True, "description": "qb, rb, wr, or te."},
            {"name": "metric", "required": True, "description": "A stat alias that belongs to that position."},
        ],
        "example": "matchup best wr receptions",
        "access": "PUBLIC",
    },
    {
        "name": "matchup defense",
        "description": "Show how a defense performs against a position.",
        "parameters": [
            {"name": "team", "required": True, "description": "Defense abbreviation."},
            {"name": "position", "required": True, "description": "qb, rb, wr, or te."},
        ],
        "example": "matchup defense det wr",
        "access": "PUBLIC",
    },
    {
        "name": "matchup offense",
        "description": "Show an offense's matchup against its opponent defense.",
        "parameters": [
            {"name": "team", "required": True, "description": "Offense abbreviation."},
            {"name": "position", "required": True, "description": "qb, rb, wr, or te."},
        ],
        "example": "matchup offense mia wr",
        "access": "PUBLIC",
    },
    {
        "name": "fantasy best",
        "description": "Show the most favorable FPTS-based positional matchups.",
        "parameters": [],
        "example": "fantasy best",
        "access": "PUBLIC",
    },
    {
        "name": "fantasy worst",
        "description": "Show the least favorable FPTS-based positional matchups.",
        "parameters": [],
        "example": "fantasy worst",
        "access": "PUBLIC",
    },
    {
        "name": "fantasy position",
        "description": "Rank scheduled offenses for one fantasy position.",
        "parameters": [
            {"name": "position", "required": True, "description": "qb, rb, wr, or te."},
        ],
        "example": "fantasy position wr",
        "access": "PUBLIC",
    },
    {
        "name": "fantasy offense",
        "description": "Show an offense's FPTS matchup against its opponent defense.",
        "parameters": [
            {"name": "team", "required": True, "description": "Offense abbreviation."},
            {"name": "position", "required": True, "description": "qb, rb, wr, or te."},
        ],
        "example": "fantasy offense det wr",
        "access": "PUBLIC",
    },
    {
        "name": "admin update",
        "description": "Download the latest completed defense snapshot and schedule.",
        "parameters": [],
        "example": "python scraper/main.py",
        "access": "ADMIN",
    },
]


def metric_options(position):
    aliases_for = {}
    for alias, metric in METRIC_ALIASES.items():
        aliases_for.setdefault(metric, []).append(alias)
    options = []
    for metric in POSITION_METRICS[position]:
        names = sorted(aliases_for.get(metric, []))
        options.extend(names or [metric.lower()])
    return options


def normalize_position(position):
    key = str(position).lower()
    if key not in POSITIONS:
        allowed = [name.upper() for name in POSITIONS]
        raise AppError(
            "INVALID_POSITION",
            f"Position '{str(position).upper()}' is not valid. Supported positions: {', '.join(allowed)}.",
            {"allowed": allowed},
        )
    return key


def normalize_team(team):
    abbr = str(team).upper()
    known = known_team_abbrs()
    if abbr not in known:
        raise AppError(
            "INVALID_TEAM",
            f"Team '{abbr}' was not recognized.",
            {"allowed": sorted(known)},
        )
    return abbr


def normalize_metric(position, metric):
    key = str(metric).lower()
    options = metric_options(position)
    columns = {
        name.lower(): name
        for names in POSITION_METRICS.values()
        for name in names
    }
    canonical = METRIC_ALIASES.get(key) or columns.get(key)
    if canonical is None:
        raise AppError(
            "INVALID_METRIC",
            f"Metric '{metric}' is not recognized.",
            {"allowed": options},
        )
    if canonical not in POSITION_METRICS[position]:
        raise AppError(
            "INVALID_METRIC_FOR_POSITION",
            (
                f"Metric '{metric}' is not supported for {position.upper()}. "
                f"Available {position.upper()} metrics: {', '.join(options)}."
            ),
            {"position": position, "allowed": options},
        )
    return canonical


def normalize_top_n(value):
    if value is None:
        return DEFAULT_TOP_N
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > MAX_TOP_N:
        raise AppError(
            "INVALID_TOP_N",
            f"top must be an integer from 1 to {MAX_TOP_N}.",
            {"min": 1, "max": MAX_TOP_N, "default": DEFAULT_TOP_N},
        )
    return value
