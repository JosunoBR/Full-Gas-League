from collections import defaultdict

from sqlalchemy import text

from app.models import db, GridConfig, Race, RaceResult
from app.services.scoring import get_orphan_results_without_team


def build_data_health_report(season_id):
    grids = GridConfig.query.filter_by(season_id=season_id).order_by(GridConfig.ordem).all()
    grids_map = {g.id: g.nome for g in grids}

    dup_team_names = db.session.execute(
        text(
            """
            SELECT t.grid_id, UPPER(TRIM(t.nome)) AS nome_norm, COUNT(*) AS qtd
            FROM team t
            WHERE t.season_id = :sid AND t.ativa = 1
            GROUP BY t.grid_id, UPPER(TRIM(t.nome))
            HAVING COUNT(*) > 1
            ORDER BY t.grid_id, nome_norm
            """
        ),
        {"sid": season_id},
    ).fetchall()

    dup_titulares = db.session.execute(
        text(
            """
            SELECT pt.pilot_id, t.grid_id, COUNT(*) AS qtd
            FROM pilot_teams pt
            JOIN team t ON t.id = pt.team_id
            WHERE t.season_id = :sid
            GROUP BY pt.pilot_id, t.grid_id
            HAVING COUNT(*) > 1
            ORDER BY qtd DESC
            """
        ),
        {"sid": season_id},
    ).fetchall()

    dup_reservas = db.session.execute(
        text(
            """
            SELECT pr.pilot_id, t.grid_id, COUNT(*) AS qtd
            FROM pilot_reserves pr
            JOIN team t ON t.id = pr.team_id
            WHERE t.season_id = :sid
            GROUP BY pr.pilot_id, t.grid_id
            HAVING COUNT(*) > 1
            ORDER BY qtd DESC
            """
        ),
        {"sid": season_id},
    ).fetchall()

    orphan_by_grid_rows = (
        db.session.query(Race.grid_id, db.func.count(RaceResult.id).label("qtd"))
        .join(Race, Race.id == RaceResult.race_id)
        .filter(Race.season_id == season_id, RaceResult.team_id.is_(None))
        .group_by(Race.grid_id)
        .all()
    )
    orphan_by_grid = [
        {"grid_id": int(r.grid_id) if r.grid_id is not None else None, "qtd": int(r.qtd or 0)}
        for r in orphan_by_grid_rows
    ]

    open_races = (
        Race.query.filter(
            Race.season_id == season_id,
            Race.status != "Concluida",
            Race.data_corrida.is_not(None),
            Race.grid_id.is_not(None),
        )
        .order_by(Race.data_corrida, Race.grid_id, Race.id)
        .all()
    )
    groups = defaultdict(list)
    for race in open_races:
        groups[(race.grid_id, race.data_corrida)].append(race)

    duplicate_open_races_same_day = []
    duplicate_open_races_conflicting_event = []
    for (grid_id, race_date), races in groups.items():
        if len(races) <= 1:
            continue
        entries = [
            {
                "id": r.id,
                "nome_gp": r.nome_gp,
                "pista": r.pista,
                "tipo_etapa": r.tipo_etapa,
            }
            for r in races
        ]
        duplicate_open_races_same_day.append(
            {
                "grid_id": int(grid_id),
                "data_corrida": race_date,
                "qtd": len(races),
                "races": entries,
            }
        )

        event_keys = {(e["nome_gp"] or "").strip().upper() for e in entries}
        if len(event_keys) > 1:
            duplicate_open_races_conflicting_event.append(
                {
                    "grid_id": int(grid_id),
                    "data_corrida": race_date,
                    "qtd": len(races),
                    "races": entries,
                }
            )

    return {
        "season_id": season_id,
        "grids_map": grids_map,
        "duplicate_team_names": [dict(r._mapping) for r in dup_team_names],
        "duplicate_titular_links": [dict(r._mapping) for r in dup_titulares],
        "duplicate_reserve_links": [dict(r._mapping) for r in dup_reservas],
        "results_without_team": get_orphan_results_without_team(season_id),
        "orphan_results_by_grid": orphan_by_grid,
        "duplicate_open_races_same_day": duplicate_open_races_same_day,
        "duplicate_open_races_conflicting_event": duplicate_open_races_conflicting_event,
    }
