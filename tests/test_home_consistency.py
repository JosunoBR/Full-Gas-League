import unittest

from run import app
from app.models import Season, GridConfig
from app.services.team_context import build_team_context


class HomeConsistencyTests(unittest.TestCase):
    def test_participants_have_same_source_for_carousel_and_standings(self):
        with app.app_context():
            season = Season.query.filter_by(ativa=True).order_by(Season.id.asc()).first()
            if not season:
                self.skipTest("No active season")

            grids = GridConfig.query.filter_by(season_id=season.id).all()
            team_ctx = build_team_context(season.id)
            participants_by_grid = team_ctx["participants_by_grid"]

            for grid in grids:
                participants = participants_by_grid.get(grid.id, [])
                carousel_ids = {item["pilot"].id for item in participants}
                standings_ids = {item["pilot"].id for item in participants}
                self.assertSetEqual(carousel_ids, standings_ids)


if __name__ == "__main__":
    unittest.main()

