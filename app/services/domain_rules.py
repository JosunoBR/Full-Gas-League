def validate_unique_membership_per_grid(team):
    """
    Rule: a pilot can run in many grids and seasons, but cannot belong to more than
    one team in the same season+grid.
    """
    if not team or not team.season_id or not team.grid_id:
        return

    for pilot in team.pilots:
        duplicates = [
            t for t in pilot.teams
            if t.season_id == team.season_id and t.grid_id == team.grid_id and t.id != team.id
        ]
        if duplicates:
            raise ValueError(
                f"Piloto {pilot.nickname} ja vinculado a outra equipe no mesmo grid/temporada."
            )

    for pilot in team.reserves:
        duplicates = [
            t for t in pilot.reserve_teams
            if t.season_id == team.season_id and t.grid_id == team.grid_id and t.id != team.id
        ]
        if duplicates:
            raise ValueError(
                f"Piloto {pilot.nickname} ja vinculado como reserva em outra equipe no mesmo grid/temporada."
            )

