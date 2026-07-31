from run import app, db
from app.models import Race, RaceResult, PilotProfile, Team

with app.app_context():
    races = Race.query.all()
    print(f"Total de corridas no banco: {len(races)}")
    for race in races:
        results = RaceResult.query.filter_by(race_id=race.id).all()
        if results:
            print(f"\n--- Corrida ID {race.id}: {race.nome_gp} ({len(results)} resultados) ---")
            for r in results[:5]:
                p_name = r.pilot.nickname if r.pilot else "Sem Piloto"
                t_name = r.team_snapshot.nome if r.team_snapshot else (Team.query.get(r.team_id).nome if r.team_id and Team.query.get(r.team_id) else "Sem Equipe")
                print(f"  Pos: {r.posicao} | Piloto: {p_name} | Equipe: {t_name} | Presença: {r.status_presenca} | Pts: {r.pontos_ganhos}")
