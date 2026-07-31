from app.models import db, Race, RaceResult, PilotProfile, Team
from run import app
import json

with app.app_context():
    races = Race.query.filter(Race.nome_gp.ilike('%Japão%')).all()
    if not races:
        races = Race.query.all()

    print(f"Encontradas {len(races)} corridas:")
    for race in races:
        print(f"\n--- RACE ID: {race.id} | GP: {race.nome_gp} | Grid: {race.grid} | Grid_ID: {race.grid_id} | Status: {race.status} ---")
        results = RaceResult.query.filter_by(race_id=race.id).all()
        print(f"Total de RaceResult no banco para race_id={race.id}: {len(results)}")
        for r in results:
            pilot_name = r.pilot.nickname if r.pilot else f"PilotID({r.pilot_id})"
            team_name = r.team_snapshot.nome if r.team_snapshot else f"TeamID({r.team_id})"
            print(f"  Result ID: {r.id} | Pos: {r.posicao} | Presenca: '{r.status_presenca}' | Piloto: {pilot_name} | Equipe: {team_name} | Pts: {r.pontos_ganhos}")

        from app.services.calendar_service import CalendarService
        summary = CalendarService.get_race_summary(race.id)
        print(f"\nSummary do CalendarService para race.id={race.id}:")
        if summary:
            print(f"  Vencedor: {summary.get('vencedor')}")
            print(f"  Total resultados no summary: {len(summary.get('resultados', []))}")
        else:
            print("  Summary retornou None!")
