import streamlit as st

FLAG_COLORS = {
    "HOT": "background-color: #15803d; color: #ffffff",
    "WARM": "background-color: #d97706; color: #111827",
    "NEUTRAL": "background-color: #4b5563; color: #f9fafb",
    "COOL": "background-color: #7dd3fc; color: #0f172a",
    "COLD": "background-color: #1d4ed8; color: #ffffff",
}


def signed(value):
    if value is None:
        return "n/a"
    return f"{float(value):+.2f}"


def flag_style(frame, column="label"):
    if column not in frame.columns:
        return frame

    def paint(value):
        style = FLAG_COLORS.get(value)
        return style or ""

    return frame.style.map(paint, subset=[column])


def show_result_error(result):
    error = result.get("error") or {}
    st.error(error.get("message") or "The outlook could not be loaded.")


def show_warning(meta):
    if meta and meta.get("warning"):
        st.warning(meta["warning"])


def page_for(path):
    pages = st.session_state.get("pages") or {}
    return pages.get(path)


def game_link(label, game_id, season, week):
    page = page_for("game")
    if page is None or not game_id:
        st.caption(label)
        return
    st.page_link(
        page,
        label=label,
        query_params={"season": str(season), "week": str(week), "game_id": str(game_id)},
    )


def team_logo(url, abbr):
    if url:
        st.image(url, width=56)
    else:
        st.markdown(f"**{abbr}**")


def player_rows(players):
    if not players:
        st.caption("Roster information is unavailable for this position.")
        return
    for player in players:
        columns = st.columns([1, 4])
        with columns[0]:
            if player.get("headshot_url"):
                st.image(player["headshot_url"], width=48)
        with columns[1]:
            jersey = player.get("jersey_number")
            number = f"#{jersey} " if jersey else ""
            status = player.get("roster_status") or "status unavailable"
            st.markdown(f"**{number}{player['player_name']}**")
            st.caption(f"{player['position'].upper()} · {status}")


def _number_text(value):
    if value is None:
        return "—"
    try:
        if value != value:
            return "—"
    except TypeError:
        return "—"
    return f"{float(value):.2f}"


def _percent_text(value):
    if value is None:
        return "—"
    return f"{float(value):+.0f}%"


def player_estimate_table(rows, show_z=False):
    import pandas as pd

    if not rows:
        st.caption("No relevant players for this stat.")
        return
    records = []
    for row in rows:
        status = row.get("roster_status") or ""
        record = {
            "Player": row.get("player_name") or row.get("player_id"),
            "Role": " · ".join(part for part in (row.get("role"), row.get("role_source")) if part),
            "Games": row.get("games") or 0,
            "Average": _number_text(row.get("player_avg")),
            "Adj. est.": _number_text(row.get("adjusted")),
            "Change": _percent_text(row.get("adjustment_pct")),
        }
        if show_z:
            record["Z est."] = _number_text(row.get("z_adjusted"))
        if status and status not in {"ACT", "ACTIVE"}:
            record["Status"] = status
        if row.get("warning"):
            record["Note"] = row["warning"]
        records.append(record)
    st.dataframe(pd.DataFrame(records), hide_index=True, width="stretch")


def spot_block(spot):
    from services.outlook_service import metric_label

    st.markdown(f"**{spot['position'].upper()} — {metric_label(spot['metric']).title()}**")
    st.markdown(
        f"{spot['label']} | Z-score: {signed(spot['z_score'])} | "
        f"Value: {spot['metric_value']:.2f} | League average: {spot['league_mean']:.2f} | "
        f"Defensive rank: {spot['defensive_metric_rank']}"
    )
    st.caption(spot["description"])
