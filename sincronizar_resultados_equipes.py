from run import app
from app.models import db, Team, RaceResult, Race, GridConfig

def sincronizar():
    with app.app_context():
        print("\n=== SINCRONIZANDO TEAM_ID NOS RESULTADOS DE CORRIDA ===")
        
        teams = Team.query.all()
        total_atualizado = 0
        
        for team in teams:
            # Identifica o nome do grid desta equipe
            t_grid = (team.grid_config.nome if team.grid_config else team.grid).upper().strip()
            
            # Pilotos titulares atuais
            pilot_ids = [p.id for p in team.pilots]
            if not pilot_ids: continue

            # Busca resultados desses pilotos na mesma temporada e grid que não estão com o team_id correto
            resultados = RaceResult.query.join(Race).outerjoin(GridConfig, Race.grid_id == GridConfig.id).filter(
                RaceResult.pilot_id.in_(pilot_ids),
                Race.season_id == team.season_id,
                RaceResult.team_id != team.id
            ).all()

            for res in resultados:
                r_grid = (res.race.grid_config.nome if res.race.grid_config else res.race.grid).upper().strip()
                
                if r_grid == t_grid:
                    res.team_id = team.id
                    total_atualizado += 1
                    print(f"  [OK] Vinculando pontos de {res.pilot.nickname} -> {team.nome} (GP {res.race.nome_gp})")

        if total_atualizado > 0:
            db.session.commit()
            print(f"\n=== SUCESSO! {total_atualizado} resultados sincronizados. ===")
        else:
            print("\nNenhum resultado precisou de sincronização.")

if __name__ == "__main__":
    sincronizar()