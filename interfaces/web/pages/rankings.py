import pandas as pd
import streamlit as st

from interfaces.web.components import flag_style, show_result_error, show_warning, signed
from interfaces.web.data import cached_rankings
from interfaces.web.state import query_value
from services.outlook_service import filter_ranking_rows, metric_label

MODES = {
    "Offensive matchups": "offense",
    "Defensive rankings": "defense",
    "Positional scores": "positional",
    "Fantasy points": "fantasy",
}
MODE_BY_VALUE = {value: label for label, value in MODES.items()}


def page():
    season, week, meta = st.session_state.get("slate", (None, None, {}))
    st.title("Rankings")
    if season is None or week is None:
        st.info("Load a schedule before viewing rankings.")
        return
    show_warning(meta)
    raw_mode = query_value("mode")
    labels = list(MODES)
    if raw_mode and raw_mode not in MODE_BY_VALUE:
        st.info(f"Ranking mode '{raw_mode}' is not available. Showing offensive matchups.")
        raw_mode = "offense"
    default_label = MODE_BY_VALUE.get(raw_mode, labels[0])
    mode_label = st.selectbox("Ranking", labels, index=labels.index(default_label))
    if MODES[mode_label] != (raw_mode or "offense"):
        st.query_params["mode"] = MODES[mode_label]
    result = cached_rankings(MODES[mode_label], str(season), int(week))
    if not result.get("success"):
        show_result_error(result)
        return
    rows = result["data"]
    filtered = _filters(rows, MODES[mode_label])
    frame = _frame(filtered, MODES[mode_label])
    if frame.empty:
        st.info("No rows match these filters.")
    else:
        styled = flag_style(frame) if "Flag" in frame.columns else frame
        st.dataframe(styled, hide_index=True, width="stretch")
    st.download_button(
        "Download CSV",
        data=frame.to_csv(index=False),
        file_name=f"rankings-{MODES[mode_label]}-week-{week}.csv",
        mime="text/csv",
    )


def _filters(rows, mode):
    positions = ["All", "QB", "RB", "WR", "TE"]
    metrics = ["All"]
    seen = set()
    for row in rows:
        metric = row.get("metric")
        if metric and metric not in seen:
            seen.add(metric)
            metrics.append(metric_label(metric).title())
    teams = sorted({row.get("offense") or row.get("team") for row in rows if row.get("offense") or row.get("team")})
    defenses = sorted({row["defense"] for row in rows if row.get("defense")})
    columns = st.columns(4)
    with columns[0]:
        search = st.text_input("Search", value=query_value("search") or "")
    with columns[1]:
        offense = st.selectbox("Offense", ["All", *teams])
    with columns[2]:
        defense = st.selectbox("Defense", ["All", *defenses]) if defenses else "All"
    with columns[3]:
        position = st.selectbox("Position", positions, index=_index(positions, query_value("position")))
    more = st.columns(3)
    with more[0]:
        metric = st.selectbox("Stat", metrics or ["All"])
    with more[1]:
        flags = st.multiselect("Flags", ["HOT", "WARM", "NEUTRAL", "COOL", "COLD"], default=_flags())
    with more[2]:
        order = st.selectbox("Sort", ["Best first", "Worst first"])
    if st.button("Reset filters"):
        for name in ("search", "position", "metric", "flags", "mode"):
            if name in st.query_params:
                del st.query_params[name]
        st.rerun()
    metric_value = None
    if metric != "All":
        metric_value = next((row.get("metric") for row in rows if metric_label(row.get("metric", "")).title() == metric), None)
    try:
        filtered = filter_ranking_rows(
            rows,
            search=search,
            offense=None if offense == "All" else offense,
            defense=None if defense == "All" else defense,
            position=None if position == "All" else position,
            metric=metric_value,
            flags=flags,
        )
    except Exception as error:
        st.warning(str(error))
        filtered = []
    score_key = _score_key(mode)
    filtered = sorted(filtered, key=lambda row: _score(row, score_key), reverse=order == "Best first")
    return filtered


def _flags():
    raw = query_value("flags")
    if not raw:
        return []
    return [flag.strip().upper() for flag in str(raw).split(",") if flag.strip()]


def _index(options, raw):
    if raw and raw.upper() in options:
        return options.index(raw.upper())
    return 0


def _score_key(mode):
    if mode == "positional":
        return "matchup_score"
    if mode == "fantasy":
        return "fpts_z_score"
    return "z_score"


def _score(row, key):
    value = row.get(key)
    if value is None:
        return float("-inf")
    return float(value)


def _frame(rows, mode):
    if mode == "defense":
        records = [
            {
                "Team": row["team"],
                "Pos": row["position"].upper(),
                "Stat": metric_label(row["metric"]).title(),
                "Value": row["metric_value"],
                "League average": row["league_mean"],
                "Z": signed(row["z_score"]),
                "League rank": row["defensive_metric_rank"],
                "Flag": row["label"],
            }
            for row in rows
        ]
    elif mode == "positional":
        records = [
            {
                "Rank": row["matchup_rank"],
                "Offense": row["offense"],
                "Defense": row["defense"],
                "Pos": row["position"].upper(),
                "Score": signed(row["matchup_score"]),
                "HOT": row["flag_counts"]["hot"],
                "WARM": row["flag_counts"]["warm"],
                "NEUTRAL": row["flag_counts"]["neutral"],
                "COOL": row["flag_counts"]["cool"],
                "COLD": row["flag_counts"]["cold"],
            }
            for row in rows
        ]
    elif mode == "fantasy":
        records = [
            {
                "Rank": row["weekly_rank"],
                "Offense": row["offense"],
                "Defense": row["defense"],
                "Pos": row["position"].upper(),
                "FPTS": row["fpts_allowed"],
                "League average": row["league_mean"],
                "Z": signed(row["fpts_z_score"]),
                "League rank": row["defensive_fpts_rank"],
                "Flag": row["label"],
            }
            for row in rows
        ]
    else:
        records = [
            {
                "Rank": row.get("weekly_rank"),
                "Offense": row["offense"],
                "Defense": row["defense"],
                "Pos": row["position"].upper(),
                "Stat": metric_label(row["metric"]).title(),
                "Value": row["metric_value"],
                "League average": row["league_mean"],
                "Z": signed(row["z_score"]),
                "League rank": row["defensive_metric_rank"],
                "Flag": row["label"],
            }
            for row in rows
        ]
    return pd.DataFrame(records)
