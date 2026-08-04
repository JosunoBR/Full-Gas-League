from app import create_app
from app.models import db, Race, RaceResult, PilotProfile, Team

app = create_app()
with app.app_context():
    r = Race.query.order_by(Race.id.desc()).first()
    if r:
        print(f"Race ID: {r.id}, Name: {r.nome_gp}, Pista: {r.pista}, Date: {r.data_corrida}, Voltas: {r.total_voltas}")
        results = RaceResult.query.filter_by(race_id=r.id).order_by(RaceResult.posicao.asc()).all()
        for res in results:
            pilot_name = res.pilot.nickname if res.pilot else 'N/A'
            team_name = res.team_snapshot.nome if res.team_snapshot else 'N/A'
            reserves = [t.nome for t in res.pilot.reserve_teams] if res.pilot else []
            teams = [t.nome for t in res.pilot.teams] if res.pilot else []
            print(f"Pos: {res.posicao} | Pilot: {pilot_name} | Team: {team_name} | DSQ: {res.dsq} | Pts: {res.pontos_ganhos} | Pilot Teams: {teams} | Reserve Teams: {reserves}")
