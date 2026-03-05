from collections import defaultdict

from run import app
from app.models import db, Team, Race, RaceResult


def sincronizar():
    with app.app_context():
        print("\n=== SINCRONIZANDO TEAM_ID NULO NOS RESULTADOS ===")

        # (pilot_id, season_id, grid_id) -> {team_id}
        candidates = defaultdict(set)
        teams = Team.query.filter(Team.season_id.isnot(None), Team.grid_id.isnot(None)).all()
        for team in teams:
            for pilot in team.pilots:
                candidates[(pilot.id, team.season_id, team.grid_id)].add(team.id)
            for pilot in team.reserves:
                candidates[(pilot.id, team.season_id, team.grid_id)].add(team.id)

        total_updated = 0
        total_ambiguous = 0
        total_no_candidate = 0

        null_results = RaceResult.query.join(Race).filter(RaceResult.team_id.is_(None)).all()
        for res in null_results:
            race = res.race
            key = (res.pilot_id, race.season_id, race.grid_id)
            team_ids = sorted(candidates.get(key, set()))

            if len(team_ids) == 1:
                res.team_id = team_ids[0]
                total_updated += 1
                print(f"  [OK] RR#{res.id} {res.pilot.nickname} -> team_id={team_ids[0]} ({race.nome_gp})")
            elif len(team_ids) > 1:
                total_ambiguous += 1
                print(f"  [SKIP][AMBIGUO] RR#{res.id} {res.pilot.nickname} candidatos={team_ids}")
            else:
                total_no_candidate += 1

        if total_updated:
            db.session.commit()
            print(f"\n=== SUCESSO! {total_updated} resultados atualizados. ===")
        else:
            print("\nNenhum resultado foi atualizado.")

        print(f"[RESUMO] Ambiguos: {total_ambiguous} | Sem candidato: {total_no_candidate}")


if __name__ == "__main__":
    sincronizar()
