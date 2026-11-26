import sys
from pathlib import Path

# `streamlit run interfaces/web/app.py` puts this folder on sys.path, not the project root.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from streamlit.runtime.pages_manager import PagesManager

# A folder named pages/ next to this file makes Streamlit run those modules
# itself, before this app finishes importing them.
PagesManager.uses_pages_directory = False

from interfaces.web.views.game_outlook import page as game_page
from interfaces.web.views.overview import page as overview_page
from interfaces.web.views.player_opportunities import page as player_page
from interfaces.web.views.rankings import page as rankings_page
from interfaces.web.views.schedule import page as schedule_page
from interfaces.web.state import render_sidebar


def main():
    st.set_page_config(page_title="SimpleNFLDVP", layout="wide")
    season, week, meta = render_sidebar()
    pages = [
        st.Page(overview_page, title="Weekly Overview", default=True),
        st.Page(schedule_page, title="Schedule", url_path="schedule"),
        st.Page(game_page, title="Game Outlook", url_path="game"),
        st.Page(rankings_page, title="Rankings", url_path="rankings"),
        st.Page(player_page, title="Player Opportunities", url_path="players"),
    ]
    st.session_state["slate"] = (season, week, meta)
    st.session_state["pages"] = {page.url_path: page for page in pages}
    st.navigation(pages).run()


if __name__ == "__main__":
    main()
