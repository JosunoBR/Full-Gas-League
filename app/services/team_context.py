from collections import defaultdict

from app.models import Team


def normalize_team_name(name):
    return (name or "").strip().upper()


def build_team_context(season_id):
    """
    Build canonical team and pilot membership context for one season.

    Returns:
      dict with:
        - raw_teams
        - canonical_teams
        - canonical_by_key[(grid_id, TEAM_NAME)] -> Team
        - alias_ids_by_key[(grid_id, TEAM_NAME)] -> [team_ids]
        - titular_team_by_pilot_grid[(pilot_id, grid_id)] -> Team (canonical)
        - reserve_team_by_pilot_grid[(pilot_id, grid_id)] -> Team (canonical)
        - participants_by_grid[grid_id] -> [{'pilot', 'team', 'is_reserve'}]
    """
    raw_teams = Team.query.filter_by(season_id=season_id, ativa=True).all()

    canonical_by_key = {}
    alias_ids_by_key = defaultdict(list)
    for team in raw_teams:
        if not team.grid_id:
            continue
        key = (team.grid_id, normalize_team_name(team.nome))
        alias_ids_by_key[key].append(team.id)
        current = canonical_by_key.get(key)
        if not current or team.id > current.id:
            canonical_by_key[key] = team

    canonical_teams = list(canonical_by_key.values())

    titular_team_by_pilot_grid = {}
    reserve_team_by_pilot_grid = {}
    source_titular_id = {}
    source_reserve_id = {}

    for team in raw_teams:
        if not team.grid_id:
            continue
        key = (team.grid_id, normalize_team_name(team.nome))
        canonical = canonical_by_key.get(key, team)

        for pilot in team.pilots:
            pkey = (pilot.id, team.grid_id)
            prev_src = source_titular_id.get(pkey, -1)
            if team.id > prev_src:
                source_titular_id[pkey] = team.id
                titular_team_by_pilot_grid[pkey] = canonical

        for pilot in team.reserves:
            pkey = (pilot.id, team.grid_id)
            prev_src = source_reserve_id.get(pkey, -1)
            if team.id > prev_src:
                source_reserve_id[pkey] = team.id
                reserve_team_by_pilot_grid[pkey] = canonical

    pilot_obj_by_id = {}
    for team in raw_teams:
        for pilot in team.pilots:
            pilot_obj_by_id[pilot.id] = pilot
        for pilot in team.reserves:
            pilot_obj_by_id[pilot.id] = pilot

    participants_by_grid = defaultdict(list)
    pilot_keys = set(titular_team_by_pilot_grid.keys()) | set(reserve_team_by_pilot_grid.keys())
    for pilot_id, grid_id in pilot_keys:
        team = titular_team_by_pilot_grid.get((pilot_id, grid_id))
        is_reserve = False
        if not team:
            team = reserve_team_by_pilot_grid.get((pilot_id, grid_id))
            is_reserve = True
        if not team:
            continue

        pilot = pilot_obj_by_id.get(pilot_id)
        if not pilot:
            continue

        participants_by_grid[grid_id].append({
            "pilot": pilot,
            "team": team,
            "is_reserve": is_reserve
        })

    # Stable ordering improves deterministic UI output.
    for grid_id in participants_by_grid:
        participants_by_grid[grid_id].sort(key=lambda x: (x["pilot"].nickname or "").upper())

    return {
        "raw_teams": raw_teams,
        "canonical_teams": canonical_teams,
        "canonical_by_key": canonical_by_key,
        "alias_ids_by_key": dict(alias_ids_by_key),
        "titular_team_by_pilot_grid": titular_team_by_pilot_grid,
        "reserve_team_by_pilot_grid": reserve_team_by_pilot_grid,
        "participants_by_grid": dict(participants_by_grid),
    }
