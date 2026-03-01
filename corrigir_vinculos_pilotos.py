from run import app
from app.models import db, Team, RaceResult, Season, PilotProfile

def corrigir_vinculos():
    with app.app_context():
        print("\n=== CORRIGINDO VÍNCULOS DE PILOTOS COM EQUIPES ===")
        
        # 1. Pega todas as temporadas ativas
        seasons = Season.query.filter_by(ativa=True).all()
        if not seasons:
            print("Erro: Nenhuma temporada ativa encontrada.")
            return
            
        total_vincular_count = 0
        
        for season in seasons:
            print(f"\nProcessando Temporada: {season.nome}")

            # 2. Busca todos os resultados de corrida desta temporada específica
            # O RaceResult é a nossa 'fonte da verdade' de quem correu por qual equipe
            resultados = RaceResult.query.join(RaceResult.race).filter(
                RaceResult.race.has(season_id=season.id),
                RaceResult.team_id != None
            ).all()

            season_vincular_count = 0
            for res in resultados:
                team = res.team
                pilot = res.pilot
                
                # Se o piloto correu pela equipe nesta temporada, ele deve ser titular dela
                if team and pilot:
                    if pilot not in team.pilots:
                        team.pilots.append(pilot)
                        season_vincular_count += 1
                        total_vincular_count += 1
                        print(f"  [OK] Vinculando {pilot.nickname} -> {team.nome} ({team.grid})")
            
            if season_vincular_count == 0:
                print("  > Nenhum vínculo pendente nesta temporada.")

        # 3. Commit das alterações
        if total_vincular_count > 0:
            db.session.commit()
            print(f"\n=== SUCESSO! ===")
            print(f"Total de {total_vincular_count} vínculos restaurados em todas as temporadas ativas.")
            print("Os pilotos agora devem aparecer com suas equipes no carrossel e nas tabelas.")
        else:
            print("\nNenhum vínculo pendente encontrado em nenhuma das temporadas ativas.")

if __name__ == "__main__":
    corrigir_vinculos()