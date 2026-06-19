import unittest

from run import app
from app.models import Season, GridConfig
from app.services.team_context import build_team_context, normalize_team_name
from app.services.scoring import build_constructors_for_home, get_team_result_stats
from app.services.scoring_service import ScoringService



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
            for team in ctx["canonical_teams"]:
                if not team.grid_id:
                    continue
                
                # A pontuação esperada é a soma da pontuação total dos pilotos titulares e reservas registrados na equipe
                expected = sum(
                    ScoringService.calculate_pilot_total_points(pilot.id, season.id, team.grid_id)
                    for pilot in list(team.pilots) + list(team.reserves)
                )

                row = next((r for r in constructors.get(team.grid_id, []) if r["equipe"].id == team.id), None)
                self.assertIsNotNone(row)
                self.assertAlmostEqual(float(row["pontos"]), expected, places=3)


if __name__ == "__main__":
    unittest.main()

