import streamlit as st

from interfaces.web.components import player_estimate_table, show_result_error, show_warning, signed, spot_block, team_logo
from interfaces.web.state import choice, query_value

BASELINES = {"Season": "season", "Last 3": "last3", "Last 5": "last5"}
SCOPES = {"Relevant": "relevant", "All eligible": "eligible", "All rostered": "all"}


def page():
    season, week, meta = st.session_state.get("slate", (None, None, {}))
    st.title("Game Outlook")
    game_id = query_value("game_id")
    if not game_id:
        st.info("Open a game from the schedule or weekly overview.")
        return
    from interfaces.web.data import cached_data_revision, cached_game, cached_health, cached_player_opportunities

    show_warning(meta)
    if season is not None and week is not None:
        health = cached_health(str(season), int(week))
        if health.get("player_warning"):
            st.warning(health["player_warning"])
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
    baseline_label = choice("baseline", "Baseline", list(BASELINES), "Season")
    scope_label = choice("roster", "Players", list(SCOPES), "Relevant")
    show_z = _estimate_note()
    revision = cached_data_revision(str(game["season"]))
    players = cached_player_opportunities(
        str(game["season"]), int(game["week"]), BASELINES[baseline_label], SCOPES[scope_label], revision,
    )
    for side in game["sides"]:
        _offense(side, teams, players, show_z)


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


def _estimate_note():
    with st.expander("About this estimate"):
        st.caption(
            "The adjusted number is experimental. It is not a projection, a probability, or a start/sit recommendation. "
            "It multiplies the player's per-game average by a factor from how many of that stat the defense allows "
            "compared with the league average. The factor starts at half of that difference and is capped between 0.50 and 1.50. "
            "HOT and COLD still come from the defensive z-score, not from the size of this adjustment. "
            "Fewer than three games is a limited sample. A dash means there is not enough data."
        )
        return st.checkbox("Show z-score comparison", value=False)


def _offense(side, teams, players, show_z):
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
        _grouped(side, "favorable", players, show_z)
    with unfavorable:
        _grouped(side, "unfavorable", players, show_z)
    with full:
        if not side["spots"]:
            st.caption("No statistical matchup is available.")
        for spot in side["spots"]:
            _spot(side, spot, players, show_z)
    with positions:
        for group in side["positions"]:
            rank = group["matchup_rank"]
            rank_text = "n/a" if rank is None else str(rank)
            st.markdown(f"**{group['position'].upper()}** · score {signed(group['matchup_score'])} · weekly rank {rank_text}")


def _spot(side, spot, players, show_z):
    spot_block(spot)
    matched = [
        row for row in players
        if row["offense"] == side["offense"] and row["position"] == spot["position"] and row["metric"] == spot["metric"]
    ]
    player_estimate_table(matched, show_z)


def _grouped(side, key, players, show_z):
    shown = False
    for group in side["positions"]:
        spots = [spot for spot in group["spots"] if spot in side[key] or spot["label"] in _labels(key)]
        spots.sort(key=lambda spot: spot["z_score"], reverse=key == "favorable")
        if not spots:
            continue
        shown = True
        with st.expander(group["position"].upper(), expanded=True):
            for spot in spots:
                _spot(side, spot, players, show_z)
    if not shown:
        st.caption("None for this offense.")


def _labels(key):
    if key == "favorable":
        return {"HOT", "WARM"}
    return {"COOL", "COLD"}
