import logging

logger = logging.getLogger("database.abbreviations")

# nflverse uses LA for the Rams. CBS and raw_dvp use LAR.
ABBR_TO_CANONICAL = {"LA": "LAR"}

CANONICAL_TEAMS = {
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN",
    "DET", "GB", "HOU", "IND", "JAX", "KC", "LAC", "LAR", "LV", "MIA",
    "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT", "SEA", "SF", "TB",
    "TEN", "WAS",
}


def canonical_abbr(value):
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text or text in {"NAN", "NONE", "<NA>"}:
        return None
    return ABBR_TO_CANONICAL.get(text, text)


def stored_abbrs(value):
    key = canonical_abbr(value)
    if key is None:
        return []
    sources = [source for source, target in ABBR_TO_CANONICAL.items() if target == key]
    return [key, *sources]


def unknown_abbreviations(values):
    unknown = set()
    for value in values:
        raw = None if value is None else str(value).strip().upper()
        if not raw or raw in {"NAN", "NONE", "<NA>"}:
            continue
        if raw not in ABBR_TO_CANONICAL and raw not in CANONICAL_TEAMS:
            unknown.add(raw)
    return sorted(unknown)


def log_unknown_abbreviations(values):
    unknown = unknown_abbreviations(values)
    for abbr in unknown:
        logger.warning("unrecognized team abbreviation %s", abbr)
    return unknown
