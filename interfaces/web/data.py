import streamlit as st

from services.outlook_service import get_game_outlook, get_leaderboards, get_rankings, get_schedule_outlook


@st.cache_data(ttl=300)
def cached_leaderboards(season, week, top, position, metric, flags, best):
    return get_leaderboards(season, week, top, position, metric, flags, best)


@st.cache_data(ttl=300)
def cached_schedule(season, week):
    return get_schedule_outlook(season, week)


@st.cache_data(ttl=300)
def cached_game(game_id, season, week):
    return get_game_outlook(game_id, season, week)


@st.cache_data(ttl=300)
def cached_rankings(mode, season, week):
    return get_rankings(mode, season, week)
