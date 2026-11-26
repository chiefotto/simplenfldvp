import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from services.outlook_service import filter_ranking_rows


def _run(script, timeout=90, **params):
    app = AppTest.from_function(script, default_timeout=timeout)
    app.query_params.update(params)
    app.run(timeout=timeout)
    return app


def _clean(app):
    if not app.exception:
        return
    message = "\n".join(getattr(item, "value", str(item)) for item in app.exception)
    raise AssertionError(message)


class WebSmokeTests(unittest.TestCase):
    def test_pages_render_for_the_stored_slate(self):
        def overview():
            import streamlit as st
            from interfaces.web.pages.overview import page
            from interfaces.web.state import render_sidebar

            season, week, meta = render_sidebar()
            st.session_state["slate"] = (season, week, meta)
            st.session_state["pages"] = {}
            page()

        def schedule():
            import streamlit as st
            from interfaces.web.pages.schedule import page
            from interfaces.web.state import render_sidebar

            season, week, meta = render_sidebar()
            st.session_state["slate"] = (season, week, meta)
            st.session_state["pages"] = {}
            page()

        def rankings():
            import streamlit as st
            from interfaces.web.pages.rankings import page
            from interfaces.web.state import render_sidebar

            season, week, meta = render_sidebar()
            st.session_state["slate"] = (season, week, meta)
            page()

        def players():
            import streamlit as st
            from interfaces.web.pages.player_opportunities import page
            from interfaces.web.state import render_sidebar

            season, week, meta = render_sidebar()
            st.session_state["slate"] = (season, week, meta)
            st.session_state["pages"] = {}
            page()

        overview_app = _run(overview, season="2026", week="11", top="3", metric="receiving_td")
        _clean(overview_app)
        self.assertTrue(overview_app.dataframe)
        self.assertGreater(len(overview_app.dataframe[0].value), 0)
        self.assertLessEqual(len(overview_app.dataframe[0].value), 3)
        for script in (schedule, rankings, players):
            app = _run(script, season="2026", week="11")
            _clean(app)
            self.assertTrue(app.dataframe or app.markdown or app.caption or app.download_button)

    def test_game_page_uses_the_query_id(self):
        import sqlite3

        game = sqlite3.connect("data/nfl_stats.db").execute(
            "SELECT game_id, season, week FROM schedule WHERE season = '2026' AND week = 11 LIMIT 1"
        ).fetchone()

        def game_page():
            import streamlit as st
            from interfaces.web.pages.game_outlook import page
            from interfaces.web.state import render_sidebar

            season, week, meta = render_sidebar()
            st.session_state["slate"] = (season, week, meta)
            page()

        missing = _run(game_page, season="2026", week="11")
        _clean(missing)
        self.assertTrue(any("Open a game" in item.value for item in missing.info))
        opened = _run(game_page, season=str(game[1]), week=str(game[2]), game_id=game[0])
        _clean(opened)
        self.assertTrue(opened.header)
        text = " ".join(getattr(item, "value", "") for item in [*opened.markdown, *opened.caption])
        self.assertIn("Z-score", text)
        self.assertTrue(opened.dataframe or opened.caption)

    def test_empty_schedule_renders(self):
        def overview():
            import streamlit as st
            from interfaces.web.pages.overview import page
            from interfaces.web.state import render_sidebar

            season, week, meta = render_sidebar()
            st.session_state["slate"] = (season, week, meta)
            page()

        with patch("interfaces.web.state.list_seasons_weeks", return_value={}):
            app = _run(overview)
        _clean(app)
        self.assertTrue(app.info or app.warning)

    def test_filtered_rankings_csv_matches_the_filter(self):
        rows = [
            {"offense": "DET", "defense": "CHI", "team": None, "position": "wr", "metric": "Receiving_TD", "label": "HOT", "z_score": 1.5},
            {"offense": "CHI", "defense": "DET", "team": None, "position": "qb", "metric": "Passing_Yd", "label": "COLD", "z_score": -1.6},
        ]
        filtered = filter_ranking_rows(rows, position="WR", flags=["HOT"])
        exported = __import__("pandas").DataFrame(filtered).to_csv(index=False)
        self.assertIn("Receiving_TD", exported)
        self.assertNotIn("Passing_Yd", exported)
        self.assertEqual(filtered[0]["z_score"], 1.5)


if __name__ == "__main__":
    unittest.main()
