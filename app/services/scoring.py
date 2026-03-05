from sqlalchemy import case, func

from app.models import db, PilotProfile, Race, RaceResult, Team
from app.services.team_context import normalize_team_name


def get_team_result_stats(season_id):
    """Return stats by team_id from race_result for a season."""
    stats_query = (
        RaceResult.query.with_entities(
            RaceResult.team_id,
            func.sum(RaceResult.pontos_ganhos).label("total_pontos"),
            func.sum(
                case((((RaceResult.posicao == 1) & (RaceResult.dsq == False)), 1), else_=0)
            ).label("total_vitorias"),
        )
        .join(Race)
        .filter(Race.season_id == season_id, RaceResult.team_id.is_not(None))
        .group_by(RaceResult.team_id)
        .all()
    )
    return {
        row.team_id: {
            "pontos": float(row.total_pontos or 0.0),
            "vitorias": int(row.total_vitorias or 0),
        }
        for row in stats_query
    }


def build_constructors_for_home(season_id, grid_configs, canonical_teams, alias_ids_by_key):
    """
    Build constructors table by grid.
    Source of truth is race_result.team_id only.
    """
    constructors = {g.id: [] for g in grid_configs}
    stats_by_team_id = get_team_result_stats(season_id)

    seen = set()
    for team in canonical_teams:
        if not team.grid_id or team.grid_id not in constructors:
            continue
        key = (team.grid_id, normalize_team_name(team.nome))
        if key in seen:
            continue
        seen.add(key)

        alias_ids = alias_ids_by_key.get(key, [team.id])
        pontos = 0.0
        vitorias = 0
        for tid in alias_ids:
            s = stats_by_team_id.get(tid, {"pontos": 0.0, "vitorias": 0})
            pontos += float(s["pontos"] or 0.0)
            vitorias += int(s["vitorias"] or 0)

        constructors[team.grid_id].append({"equipe": team, "pontos": pontos, "vitorias": vitorias})

    for grid_id in constructors:
        constructors[grid_id].sort(key=lambda x: (x["pontos"], x["vitorias"]), reverse=True)

    return constructors


def get_orphan_results_without_team(season_id):
    """
    Count race results with no team_id.
    Useful diagnostic for legacy records.
    """
    rows = (
        RaceResult.query.join(Race)
        .filter(Race.season_id == season_id, RaceResult.team_id.is_(None))
        .count()
    )
    return int(rows)


def get_team_alias_ids(team: Team, season_id: int):
    """Return all team ids considered aliases for the same logical team in a season."""
    if not team or not season_id:
        return []
    if not team.grid_id:
        return [team.id]

    same_name_teams = Team.query.filter(
        Team.season_id == season_id,
        Team.grid_id == team.grid_id,
        func.upper(func.trim(Team.nome)) == normalize_team_name(team.nome),
    ).all()
    if not same_name_teams:
        return [team.id]
    return [t.id for t in same_name_teams]


def team_has_results_in_season(team: Team, season_id: int):
    """Checks if logical team has any race_result in season."""
    alias_ids = get_team_alias_ids(team, season_id)
    if not alias_ids:
        return False

    query = RaceResult.query.join(Race).filter(
        Race.season_id == season_id,
        RaceResult.team_id.in_(alias_ids),
    )
    if team.grid_id:
        query = query.filter(Race.grid_id == team.grid_id)
    return query.first() is not None


def get_team_profile_stats(team: Team, season_id: int):
    """
    Source of truth for public team profile stats:
    - totals and pilot breakdown from race_result.team_id only
    - includes ex-drivers and reserves that raced for the team
    """
    alias_ids = get_team_alias_ids(team, season_id)
    if not alias_ids:
        return {"total_pontos": 0.0, "total_vitorias": 0, "stats_pilotos": []}

    query = db.session.query(
        RaceResult.pilot_id,
        func.sum(RaceResult.pontos_ganhos).label("pontos"),
        func.sum(case((((RaceResult.posicao == 1) & (RaceResult.dsq == False)), 1), else_=0)).label("vitorias"),
    ).join(Race).filter(
        Race.season_id == season_id,
        RaceResult.team_id.in_(alias_ids),
    )
    if team.grid_id:
        query = query.filter(Race.grid_id == team.grid_id)

    rows = query.group_by(RaceResult.pilot_id).all()
    if not rows:
        return {"total_pontos": 0.0, "total_vitorias": 0, "stats_pilotos": []}

    pilot_ids = [r.pilot_id for r in rows]
    pilots = PilotProfile.query.filter(PilotProfile.id.in_(pilot_ids)).all()
    pilot_by_id = {p.id: p for p in pilots}

    stats_pilotos = []
    total_pontos = 0.0
    total_vitorias = 0
    for r in rows:
        p = pilot_by_id.get(r.pilot_id)
        if not p:
            continue
        pontos = float(r.pontos or 0.0)
        vitorias = int(r.vitorias or 0)
        total_pontos += pontos
        total_vitorias += vitorias
        stats_pilotos.append({"piloto": p, "pontos": pontos, "vitorias": vitorias})

    stats_pilotos.sort(key=lambda x: (x["pontos"], x["vitorias"]), reverse=True)
    return {
        "total_pontos": round(total_pontos, 1),
        "total_vitorias": int(total_vitorias),
        "stats_pilotos": stats_pilotos,
    }
