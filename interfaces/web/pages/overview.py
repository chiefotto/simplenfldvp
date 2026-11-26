import pandas as pd
import streamlit as st

from interfaces.web.components import flag_style, game_link, show_result_error, show_warning, signed
from interfaces.web.data import cached_leaderboards
from interfaces.web.state import _set_param, choice, integer_choice, query_value, TOP_OPTIONS
from services.outlook_service import metric_label

POSITIONS = ("All", "QB", "RB", "WR", "TE")
ORDERS = ("Best", "Worst")


def _metric_options():
    from database.matchups import METRIC_ALIASES

    options = ["All"]
    labels = {}
    for alias, metric in sorted(METRIC_ALIASES.items(), key=lambda item: metric_label(item[1])):
        label = f"{metric_label(metric).title()} ({alias})"
        options.append(label)
        labels[label] = alias
    labels["All"] = None
    return options, labels


def page():
    season, week, meta = st.session_state.get("slate", (None, None, {}))
    st.title("Weekly Overview")
    if season is None or week is None:
        st.info("Load a schedule before viewing the weekly outlook.")
        return
    st.caption(f"Season {season}, week {week}")
    show_warning(meta)
    options, labels = _metric_options()
    raw_metric = query_value("metric")
    selected_label = "All"
    if raw_metric:
        matched = [label for label, alias in labels.items() if alias == raw_metric]
        if matched:
            selected_label = matched[0]
        else:
            st.info(f"Stat '{raw_metric}' is not a leaderboard filter. Showing every stat.")
    controls = st.columns(4)
    with controls[0]:
        top = integer_choice("top", "Results", TOP_OPTIONS, 5)
    with controls[1]:
        position = choice("position", "Position", POSITIONS, "All")
    with controls[2]:
        metric_choice = st.selectbox("Stat", options, index=options.index(selected_label))
        _set_param("metric", labels[metric_choice])
    with controls[3]:
        order = choice("order", "Order", ORDERS, "Best")
    flags = st.multiselect("Flags", ["HOT", "WARM", "NEUTRAL", "COOL", "COLD"], default=_flag_default())
    _remember_flags(flags)
    result = cached_leaderboards(
        str(season),
        int(week),
        int(top),
        None if position == "All" else position.lower(),
        labels[metric_choice],
        tuple(flags),
        order == "Best",
    )
    if not result.get("success"):
        show_result_error(result)
        return
    data = result["data"]
    games = {row["game_id"] for category in data["categories"] for row in category["rows"]}
    favorable = sum(row["label"] in {"HOT", "WARM"} for category in data["categories"] for row in category["rows"])
    st.caption(f"{len(games)} games in view · {favorable} HOT or WARM rows in the current filter")
    _leaderboards(data["categories"], season, week)
    st.subheader("Positional matchup scores")
    st.caption("Flag counts describe the configured stats for that position. They are not a ranking across positions.")
    _positional(data["positional"])


def _flag_default():
    raw = query_value("flags")
    if not raw:
        return []
    chosen = [flag.strip().upper() for flag in str(raw).split(",") if flag.strip()]
    allowed = {"HOT", "WARM", "NEUTRAL", "COOL", "COLD"}
    return [flag for flag in chosen if flag in allowed]


def _remember_flags(flags):
    text = ",".join(flags)
    current = query_value("flags") or ""
    if text != current:
        if text:
            st.query_params["flags"] = text
        elif "flags" in st.query_params:
            del st.query_params["flags"]


def _leaderboards(categories, season, week):
    left, right = st.columns(2)
    for index, category in enumerate(categories):
        column = left if index % 2 == 0 else right
        with column:
            positions = ", ".join(position.upper() for position in category["positions"])
            st.markdown(f"**{category['label'].upper()}**")
            st.caption(positions)
            rows = category["rows"]
            if not rows:
                st.caption("No matchups.")
                continue
            frame = pd.DataFrame([
                {
                    "Rank": row["display_rank"],
                    "Offense": row["offense"],
                    "Defense": row["defense"],
                    "Pos": row["position"].upper(),
                    "Z": signed(row["z_score"]),
                    "Flag": row["label"],
                }
                for row in rows
            ])
            st.dataframe(flag_style(frame, "Flag"), hide_index=True, width="stretch")
            for row in rows:
                game_link(
                    f"{row['offense']} vs {row['defense']}",
                    row.get("game_id"),
                    season,
                    week,
                )


def _positional(rows):
    if not rows:
        st.caption("No positional scores.")
        return
    frame = pd.DataFrame([
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
    ])
    st.dataframe(frame, hide_index=True, width="stretch")
