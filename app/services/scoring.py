from app.services.scoring_service import ScoringService


def build_constructors_for_home(season_id, grid_configs, canonical_teams, alias_ids_by_key):
    return ScoringService.build_constructors_for_home(
        season_id, grid_configs, canonical_teams, alias_ids_by_key
    )


def get_team_result_stats(season_id):
    return ScoringService.get_team_result_stats(season_id)
