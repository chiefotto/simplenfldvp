import streamlit as st

from database.storage import initialize_database
from services.outlook_service import resolve_slate, slate_meta
from database.queries import list_seasons_weeks

TOP_OPTIONS = (3, 5, 10, 15, 20)
ORDERS = ("best", "worst")


def query_value(name):
    if name not in st.query_params:
        return None
    value = st.query_params[name]
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _set_param(name, value):
    current = query_value(name)
    text = None if value is None or value == "" else str(value)
    if text is None:
        if name in st.query_params:
            del st.query_params[name]
        return
    if current != text:
        st.query_params[name] = text


def selected_slate():
    raw_season = query_value("season")
    raw_week = query_value("week")
    week = None
    warning = None
    if raw_week not in (None, ""):
        try:
            week = int(raw_week)
        except ValueError:
            warning = f"Week '{raw_week}' is not valid. Showing the current week."
    try:
        season, resolved_week, slate_warning = resolve_slate(raw_season or None, week)
    except Exception:
        season, resolved_week, slate_warning = resolve_slate(None, None)
        warning = warning or "The link pointed at a week that is not available."
    return season, resolved_week, warning or slate_warning


def render_sidebar():
    initialize_database()
    seasons = list_seasons_weeks()
    season, week, warning = selected_slate()
    st.sidebar.title("SimpleNFLDVP")
    st.sidebar.caption("Matchup research. Not a projection or a start/sit ranking.")
    if not seasons or season is None or week is None:
        st.sidebar.warning("No schedule is stored yet. Run the scraper to load a season.")
        meta = {"season": season, "week": week, "snapshot_week": None, "note": None, "roster_week": None, "roster_note": None, "warning": warning}
        return season, week, meta
    options = list(seasons)
    if season not in options:
        season = options[-1]
        warning = warning or f"Season {query_value('season')} is not stored. Showing {season}."
    chosen_season = st.sidebar.selectbox("Season", options, index=options.index(season))
    weeks = seasons[chosen_season]
    chosen_week_default = week if week in weeks else weeks[-1]
    if week not in weeks and query_value("week"):
        warning = warning or f"Week {week} is not on the {chosen_season} schedule. Showing week {chosen_week_default}."
    chosen_week = st.sidebar.selectbox("Week", weeks, index=weeks.index(chosen_week_default))
    _set_param("season", chosen_season)
    _set_param("week", chosen_week)
    meta = slate_meta(chosen_season, chosen_week, warning)
    snapshot = meta.get("snapshot_week")
    if snapshot is None:
        st.sidebar.info("No defense snapshot is available for this week.")
    else:
        line = f"Defense snapshot: week {snapshot}"
        if meta.get("note"):
            line = f"{line}. {meta['note']}"
        st.sidebar.caption(line)
    if meta.get("roster_note"):
        st.sidebar.caption(meta["roster_note"])
    elif meta.get("roster_week") is not None:
        st.sidebar.caption(f"Roster snapshot: week {meta['roster_week']}")
    return chosen_season, chosen_week, meta


def choice(name, label, options, default):
    raw = query_value(name)
    selected_default = default
    if raw is not None:
        match = next((option for option in options if option.lower() == str(raw).lower()), None)
        selected_default = match or default
    selected = st.selectbox(label, options, index=options.index(selected_default))
    _set_param(name, None if selected == default else selected)
    return selected


def integer_choice(name, label, options, default):
    raw = query_value(name)
    try:
        current = int(raw) if raw is not None else default
    except ValueError:
        current = default
    if current not in options:
        current = default
    selected = st.selectbox(label, options, index=options.index(current))
    _set_param(name, None if selected == default else selected)
    return selected
