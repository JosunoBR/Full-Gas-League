from sqlalchemy import text

from app.models import db, GridConfig
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

    return {
        "season_id": season_id,
        "grids_map": grids_map,
        "duplicate_team_names": [dict(r._mapping) for r in dup_team_names],
        "duplicate_titular_links": [dict(r._mapping) for r in dup_titulares],
        "duplicate_reserve_links": [dict(r._mapping) for r in dup_reservas],
        "results_without_team": get_orphan_results_without_team(season_id),
    }

