import pandas as pd
import streamlit as st

from interfaces.web.components import flag_style, show_warning
from interfaces.web.data import cached_player_opportunities
from interfaces.web.state import choice, query_value
from services.outlook_service import metric_label
from services.player_service import filter_player_rows, sort_player_rows

BASELINES = {"Season": "season", "Last 3": "last3", "Last 5": "last5"}
SCOPES = {"Relevant": "relevant", "All eligible": "eligible", "All rostered": "all"}


def page():
    season, week, meta = st.session_state.get("slate", (None, None, {}))
    st.title("Player Opportunities")
    st.caption("Experimental player context for this week's defensive matchups. Not a betting board or a start/sit ranking.")
    if season is None or week is None:
        st.info("Load a schedule before viewing player opportunities.")
        return
    show_warning(meta)
    baseline_label = choice("baseline", "Baseline", list(BASELINES), "Season")
    scope_label = choice("roster", "Players", list(SCOPES), "Relevant")
    rows = cached_player_opportunities(str(season), int(week), BASELINES[baseline_label], SCOPES[scope_label])
    filtered = _filters(rows)
    frame = _frame(filtered)
    if frame.empty:
        st.info("No player rows match these filters.")
    else:
        st.dataframe(flag_style(frame, "Flag"), hide_index=True, width="stretch")
        _game_link(filtered, season, week)
    st.download_button(
        "Download CSV",
        data=_export(filtered).to_csv(index=False),
        file_name=f"player-opportunities-week-{week}.csv",
        mime="text/csv",
    )


def _filters(rows):
    positions = ["All", "QB", "RB", "WR", "TE"]
    metrics = ["All"]
    seen = set()
    for row in rows:
        label = metric_label(row["metric"]).title()
        if label not in seen:
            seen.add(label)
            metrics.append(label)
    columns = st.columns(4)
    with columns[0]:
        search = st.text_input("Search", value=query_value("search") or "")
    with columns[1]:
        position = st.selectbox("Position", positions, index=_index(positions, query_value("position")))
    with columns[2]:
        metric = st.selectbox("Stat", metrics)
    with columns[3]:
        flags = st.multiselect("Flags", ["HOT", "WARM", "NEUTRAL", "COOL", "COLD"], default=_flags())
    more = st.columns(3)
    with more[0]:
        minimum = st.number_input("Minimum games", min_value=0, max_value=20, value=0, step=1)
    with more[1]:
        sorts = ["Z-score"]
        if metric != "All":
            sorts.extend(["Adjustment", "Estimate"])
        order = st.selectbox("Sort", sorts)
    with more[2]:
        st.caption("Adjustment and estimate sorts stay inside one stat.")
    if st.button("Reset filters"):
        for name in ("search", "position", "metric", "flags", "baseline", "roster"):
            if name in st.query_params:
                del st.query_params[name]
        st.rerun()
    metric_value = None
    if metric != "All":
        metric_value = next((row["metric"] for row in rows if metric_label(row["metric"]).title() == metric), None)
    filtered = filter_player_rows(
        rows,
        search=search,
        position=None if position == "All" else position,
        metric=metric_value,
        flags=flags,
        minimum_games=int(minimum),
    )
    key = {"Z-score": "z_score", "Adjustment": "adjustment_pct", "Estimate": "adjusted"}[order]
    return sort_player_rows(filtered, key, best=True)


def _flags():
    raw = query_value("flags")
    if not raw:
        return ["HOT", "WARM"]
    return [flag.strip().upper() for flag in str(raw).split(",") if flag.strip()]


def _index(options, raw):
    if raw and raw.upper() in options:
        return options.index(raw.upper())
    return 0


def _text_number(value):
    if value is None:
        return "—"
    return f"{float(value):.2f}"


def _frame(rows):
    records = []
    for row in rows:
        records.append({
            "Player": row.get("player_name"),
            "Role": row.get("role") or "",
            "Offense": row.get("offense"),
            "Defense": row.get("defense"),
            "Position": (row.get("position") or "").upper(),
            "Stat": metric_label(row.get("metric")).title(),
            "Flag": row.get("label"),
            "Z-score": None if row.get("z_score") is None else round(float(row["z_score"]), 2),
            "Games": row.get("games") or 0,
            "Average": _text_number(row.get("player_avg")),
            "Adj. est.": _text_number(row.get("adjusted")),
            "Change": "—" if row.get("adjustment_pct") is None else f"{float(row['adjustment_pct']):+.0f}%",
            "Note": row.get("warning") or "",
        })
    return pd.DataFrame(records)


def _export(rows):
    columns = [
        "player_name", "player_id", "role", "role_source", "offense", "defense", "position", "metric",
        "label", "z_score", "window", "player_avg", "games", "adjusted", "adjustment_pct", "multiplier",
        "method", "capped", "defense_avg", "league_avg", "snapshot_week", "warning", "game_id", "season", "week",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows).reindex(columns=columns)


def _game_link(rows, season, week):
    from interfaces.web.components import game_link

    games = []
    seen = set()
    for row in rows:
        if row.get("game_id") in seen:
            continue
        seen.add(row.get("game_id"))
        games.append(row)
    if not games:
        return
    labels = [f"{row['offense']} vs {row['defense']}" for row in games]
    selected = st.selectbox("Open game outlook", labels)
    match = games[labels.index(selected)]
    game_link(f"Open {selected}", match["game_id"], season, week)
