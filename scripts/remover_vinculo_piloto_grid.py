"""
Remove vinculos residuais de piloto em equipes de um escopo (temporada/grid).

Uso:
  Dry-run por ID:
    python scripts/remover_vinculo_piloto_grid.py --pilot-id 30 --season-id 1 --grid-id 1

  Aplicar:
    python scripts/remover_vinculo_piloto_grid.py --pilot-id 30 --season-id 1 --grid-id 1 --apply

  Buscar por nickname (contém):
    python scripts/remover_vinculo_piloto_grid.py --nickname gablucas --season-id 1 --grid-id 1
"""

import argparse

from run import app
from app.models import db, PilotProfile, Team


def find_pilots(pilot_id=None, nickname=None):
    if pilot_id:
        p = db.session.get(PilotProfile, pilot_id)
        return [p] if p else []
    if nickname:
        term = f"%{nickname.strip()}%"
        return PilotProfile.query.filter(PilotProfile.nickname.ilike(term)).all()
    return []


def remove_memberships(pilot, season_id, grid_id=None, apply=False):
    query = Team.query.filter_by(season_id=season_id)
    if grid_id is not None:
        query = query.filter_by(grid_id=grid_id)
    teams = query.all()

    removed_titular = 0
    removed_reserva = 0

    for team in teams:
        if any(pp.id == pilot.id for pp in team.pilots):
            print(f"[TITULAR] remover {pilot.nickname} da equipe {team.id} - {team.nome} (grid_id={team.grid_id})")
            if apply:
                team.pilots.remove(pilot)
            removed_titular += 1

        if any(pp.id == pilot.id for pp in team.reserves):
            print(f"[RESERVA] remover {pilot.nickname} da equipe {team.id} - {team.nome} (grid_id={team.grid_id})")
            if apply:
                team.reserves.remove(pilot)
            removed_reserva += 1

    return removed_titular, removed_reserva


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-id", type=int, default=None)
    parser.add_argument("--nickname", type=str, default=None)
    parser.add_argument("--season-id", type=int, required=True)
    parser.add_argument("--grid-id", type=int, default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    with app.app_context():
        pilots = find_pilots(args.pilot_id, args.nickname)
        if not pilots:
            print("Nenhum piloto encontrado.")
            return

        print(f"Pilotos alvo: {[f'{p.id}:{p.nickname}' for p in pilots]}")
        print(f"Escopo: season_id={args.season_id}, grid_id={args.grid_id if args.grid_id is not None else 'TODOS'}")
        print(f"Modo: {'APLICAR' if args.apply else 'DRY-RUN'}")

        total_t = 0
        total_r = 0
        for p in pilots:
            t, r = remove_memberships(p, args.season_id, args.grid_id, apply=args.apply)
            total_t += t
            total_r += r

        if args.apply:
            db.session.commit()
        else:
            db.session.rollback()

        print(f"Resumo: titulares removidos={total_t}, reservas removidos={total_r}, dry_run={not args.apply}")


if __name__ == "__main__":
    main()

