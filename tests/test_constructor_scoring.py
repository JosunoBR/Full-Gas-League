import unittest

from run import app
from app.models import Season, GridConfig
from app.services.team_context import build_team_context, normalize_team_name
from app.services.scoring import build_constructors_for_home, get_team_result_stats


class ConstructorScoringTests(unittest.TestCase):
    def test_constructors_are_aggregated_from_race_results_aliases(self):
        with app.app_context():
            season = Season.query.filter_by(ativa=True).order_by(Season.id.asc()).first()
            if not season:
                self.skipTest("No active season")

            grids = GridConfig.query.filter_by(season_id=season.id).all()
            if not grids:
                self.skipTest("No grid configs")

            ctx = build_team_context(season.id)
            constructors = build_constructors_for_home(
                season.id, grids, ctx["canonical_teams"], ctx["alias_ids_by_key"]
            )
            stats_by_team_id = get_team_result_stats(season.id)

            for team in ctx["canonical_teams"]:
                if not team.grid_id:
                    continue
                key = (team.grid_id, normalize_team_name(team.nome))
                alias_ids = ctx["alias_ids_by_key"].get(key, [team.id])
                expected = sum(float(stats_by_team_id.get(tid, {"pontos": 0.0})["pontos"]) for tid in alias_ids)

                row = next((r for r in constructors.get(team.grid_id, []) if r["equipe"].id == team.id), None)
                self.assertIsNotNone(row)
                self.assertAlmostEqual(float(row["pontos"]), expected, places=3)


if __name__ == "__main__":
    unittest.main()

