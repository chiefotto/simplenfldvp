from collections import defaultdict

import streamlit as st

from interfaces.web.components import game_link, show_result_error, show_warning, team_logo
from interfaces.web.data import cached_schedule


def page():
    season, week, meta = st.session_state.get("slate", (None, None, {}))
    st.title("Schedule")
    if season is None or week is None:
        st.info("Load a schedule before viewing games.")
        return
    st.caption(f"Season {season}, week {week}. Kickoff times are Eastern.")
    show_warning(meta)
    result = cached_schedule(str(season), int(week))
    if not result.get("success"):
        show_result_error(result)
        return
    games = result["data"]
    if not games:
        st.info("No games are stored for this week.")
        return
    grouped = defaultdict(list)
    for game in games:
        grouped[game.get("gameday") or "Date unavailable"].append(game)
    for day in sorted(grouped):
        st.subheader(str(day))
        for game in grouped[day]:
            _card(game, season, week)


def _card(game, season, week):
    with st.container(border=True):
        away, info, home = st.columns([2, 2, 2])
        with away:
            team_logo(game.get("away_logo"), game["away_team"])
            st.markdown(f"**{game['away_name']}**")
            st.caption(game["away_team"])
        with info:
            kick = game.get("gametime") or "Time unavailable"
            st.markdown(f"**{kick} ET**")
            if game.get("away_score") is not None and game.get("home_score") is not None:
                st.markdown(f"{int(game['away_score'])} – {int(game['home_score'])}")
            else:
                st.caption("No final score")
            st.caption(f"HOT {game['hot']} · WARM {game['warm']}")
            game_link("Open game outlook", game.get("game_id"), season, week)
        with home:
            team_logo(game.get("home_logo"), game["home_team"])
            st.markdown(f"**{game['home_name']}**")
            st.caption(game["home_team"])
