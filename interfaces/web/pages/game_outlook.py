import streamlit as st

from interfaces.web.components import player_rows, show_result_error, show_warning, signed, spot_block, team_logo
from interfaces.web.data import cached_game
from interfaces.web.state import query_value


def page():
    season, week, meta = st.session_state.get("slate", (None, None, {}))
    st.title("Game Outlook")
    game_id = query_value("game_id")
    if not game_id:
        st.info("Open a game from the schedule or weekly overview.")
        return
    show_warning(meta)
    result = cached_game(str(game_id), None if season is None else str(season), None if week is None else int(week))
    if not result.get("success"):
        show_result_error(result)
        return
    game = result["data"]
    teams = game.get("teams") or {}
    _header(game, teams)
    if game.get("roster_note"):
        st.caption(game["roster_note"])
    elif not game.get("roster_week"):
        st.caption("Roster information is unavailable. Matchup scores are still shown.")
    for side in game["sides"]:
        _offense(side, teams)


def _header(game, teams):
    away, info, home = st.columns([2, 2, 2])
    with away:
        team_logo(teams.get(game["away_team"], {}).get("team_logo_url"), game["away_team"])
        name = teams.get(game["away_team"], {}).get("team_name") or game["away_team"]
        st.markdown(f"**{name}**")
    with info:
        st.markdown(f"**Week {game['week']}**")
        kick = game.get("gametime") or "Time unavailable"
        st.caption(f"{game.get('gameday') or 'Date unavailable'} · {kick} ET")
        if game.get("away_score") is not None and game.get("home_score") is not None:
            st.markdown(f"{int(game['away_score'])} – {int(game['home_score'])}")
        snapshot = game.get("snapshot_week")
        if snapshot is None:
            st.caption("Defense snapshot unavailable")
        else:
            note = f" ({game['note']})" if game.get("note") else ""
            st.caption(f"Defense snapshot: week {snapshot}{note}")
    with home:
        team_logo(teams.get(game["home_team"], {}).get("team_logo_url"), game["home_team"])
        name = teams.get(game["home_team"], {}).get("team_name") or game["home_team"]
        st.markdown(f"**{name}**")


def _offense(side, teams):
    name = teams.get(side["offense"], {}).get("team_name") or side["offense"]
    st.header(f"{name} offensive outlook")
    st.caption(f"Against the {side['defense']} defense. These are defensive matchup signals, not player projections.")
    scores = st.columns(4)
    for column, group in zip(scores, side["positions"]):
        with column:
            st.metric(group["position"].upper(), signed(group["matchup_score"]))
            counts = group["flag_counts"]
            st.caption(f"HOT {counts['hot']} · WARM {counts['warm']} · COOL {counts['cool']} · COLD {counts['cold']}")
    favorable, unfavorable, full, positions = st.tabs(["HOT and WARM", "COOL and COLD", "All stats", "Positions"])
    with favorable:
        _grouped(side, "favorable")
    with unfavorable:
        _grouped(side, "unfavorable")
    with full:
        if not side["spots"]:
            st.caption("No statistical matchup is available.")
        for spot in side["spots"]:
            spot_block(spot)
    with positions:
        for group in side["positions"]:
            rank = group["matchup_rank"]
            rank_text = "n/a" if rank is None else str(rank)
            st.markdown(f"**{group['position'].upper()}** · score {signed(group['matchup_score'])} · weekly rank {rank_text}")


def _grouped(side, key):
    shown = False
    for group in side["positions"]:
        spots = [spot for spot in group["spots"] if spot in side[key] or spot["label"] in _labels(key)]
        if not spots:
            continue
        shown = True
        with st.expander(group["position"].upper(), expanded=True):
            player_rows(group["players"])
            for spot in spots:
                spot_block(spot)
    if not shown:
        st.caption("None for this offense.")


def _labels(key):
    if key == "favorable":
        return {"HOT", "WARM"}
    return {"COOL", "COLD"}
