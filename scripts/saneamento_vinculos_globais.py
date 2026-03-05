"""
Saneamento global de vínculos piloto-equipe.

Regra aplicada:
- Um piloto não pode estar em mais de uma equipe no mesmo (season_id, grid_id),
  seja como titular ou reserva.
- Se houver conflito de titulares: mantém apenas 1 vínculo (prioridade: equipe ativa,
  mais resultados históricos para o piloto nessa equipe, maior team_id).
- Se houver conflito de reservas: mesma regra.
- Se o piloto estiver titular e reserva no mesmo (season_id, grid_id), mantém titular
  e remove reservas nesse mesmo contexto.

Uso:
  Dry-run (padrão):
    python scripts/saneamento_vinculos_globais.py

  Aplicar:
    python scripts/saneamento_vinculos_globais.py --apply

  Limitar a uma temporada:
    python scripts/saneamento_vinculos_globais.py --season-id 1
"""

import argparse
from collections import defaultdict

from run import app
from app.models import db, PilotProfile, Team, Race, RaceResult


def _build_result_weight_map(season_id=None):
    """
    Peso de vínculo por histórico real do piloto na equipe (no race_result).
    Quanto maior, mais forte é o vínculo para desempate.
    """
    query = (
        db.session.query(
            RaceResult.pilot_id,
            RaceResult.team_id,
            Race.season_id,
            Race.grid_id,
            db.func.count(RaceResult.id).label("qtd"),
        )
        .join(Race)
        .filter(RaceResult.team_id.isnot(None), Race.grid_id.isnot(None))
    )
    if season_id is not None:
        query = query.filter(Race.season_id == season_id)
    rows = query.group_by(
        RaceResult.pilot_id, RaceResult.team_id, Race.season_id, Race.grid_id
    ).all()
    return {
        (r.pilot_id, r.team_id, r.season_id, r.grid_id): int(r.qtd or 0)
        for r in rows
    }


def _team_rank(team, pilot_id, season_id, grid_id, result_weights):
    return (
        1 if team.ativa else 0,
        result_weights.get((pilot_id, team.id, season_id, grid_id), 0),
        team.id,
    )


def run_cleanup(apply=False, season_id=None):
    with app.app_context():
        result_weights = _build_result_weight_map(season_id=season_id)

        pilots = PilotProfile.query.all()
        changes = {
            "titular_removed": 0,
            "reserve_removed": 0,
            "contexts_fixed": 0,
        }

        for pilot in pilots:
            contexts = defaultdict(lambda: {"titular": [], "reserve": []})

            for team in pilot.teams:
                if not team.season_id or not team.grid_id:
                    continue
                if season_id is not None and team.season_id != season_id:
                    continue
                contexts[(team.season_id, team.grid_id)]["titular"].append(team)

            for team in pilot.reserve_teams:
                if not team.season_id or not team.grid_id:
                    continue
                if season_id is not None and team.season_id != season_id:
                    continue
                contexts[(team.season_id, team.grid_id)]["reserve"].append(team)

            for (sid, gid), data in contexts.items():
                titular = data["titular"]
                reserve = data["reserve"]

                changed_here = False

                # Resolve conflito de titulares.
                if len(titular) > 1:
                    keep = max(
                        titular,
                        key=lambda t: _team_rank(t, pilot.id, sid, gid, result_weights),
                    )
                    for t in titular:
                        if t.id == keep.id:
                            continue
                        print(
                            f"[TITULAR] pilot={pilot.id}:{pilot.nickname} "
                            f"sid={sid} gid={gid} remove team={t.id}:{t.nome} keep={keep.id}:{keep.nome}"
                        )
                        if apply:
                            t.pilots.remove(pilot)
                        changes["titular_removed"] += 1
                        changed_here = True

                # Resolve conflito de reservas.
                if len(reserve) > 1:
                    keep = max(
                        reserve,
                        key=lambda t: _team_rank(t, pilot.id, sid, gid, result_weights),
                    )
                    for t in reserve:
                        if t.id == keep.id:
                            continue
                        print(
                            f"[RESERVE] pilot={pilot.id}:{pilot.nickname} "
                            f"sid={sid} gid={gid} remove team={t.id}:{t.nome} keep={keep.id}:{keep.nome}"
                        )
                        if apply:
                            t.reserves.remove(pilot)
                        changes["reserve_removed"] += 1
                        changed_here = True

                # Se existe titular no contexto, remove quaisquer reservas desse contexto.
                final_tit = [
                    t for t in pilot.teams
                    if t.season_id == sid and t.grid_id == gid
                ]
                if final_tit:
                    for t in list(pilot.reserve_teams):
                        if t.season_id == sid and t.grid_id == gid:
                            print(
                                f"[PROMOTION] pilot={pilot.id}:{pilot.nickname} "
                                f"sid={sid} gid={gid} remove reserve team={t.id}:{t.nome} (already titular)"
                            )
                            if apply:
                                t.reserves.remove(pilot)
                            changes["reserve_removed"] += 1
                            changed_here = True

                if changed_here:
                    changes["contexts_fixed"] += 1

        if apply:
            db.session.commit()
        else:
            db.session.rollback()

        print(
            f"Resumo: contexts_fixed={changes['contexts_fixed']}, "
            f"titular_removed={changes['titular_removed']}, "
            f"reserve_removed={changes['reserve_removed']}, dry_run={not apply}"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--season-id", type=int, default=None)
    args = parser.parse_args()
    run_cleanup(apply=args.apply, season_id=args.season_id)


if __name__ == "__main__":
    main()

