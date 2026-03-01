from run import app
from app.models import db, Team, RaceResult, Season, PilotProfile

def corrigir_vinculos():
    with app.app_context():
        print("\n=== CORRIGINDO VÍNCULOS DE PILOTOS COM EQUIPES ===")
        
        # 1. Pega a temporada ativa
        season = Season.query.filter_by(ativa=True).order_by(Season.id.desc()).first()
        if not season:
            print("Erro: Nenhuma temporada ativa encontrada.")
            return
            
        print(f"Temporada Detectada: {season.nome}")

        # 2. Busca todos os resultados de corrida desta temporada
        # O RaceResult é a nossa 'fonte da verdade' de quem correu por qual equipe
        resultados = RaceResult.query.join(RaceResult.race).filter(
            RaceResult.race.has(season_id=season.id),
            RaceResult.team_id != None
        ).all()

        vincular_count = 0
        for res in resultados:
            team = res.team
            pilot = res.pilot
            
            # Se o piloto correu pela equipe nesta temporada, ele deve ser titular dela
            if team and pilot:
                if pilot not in team.pilots:
                    team.pilots.append(pilot)
                    vincular_count += 1
                    print(f"  [OK] Vinculando {pilot.nickname} -> {team.nome} ({team.grid})")

        # 3. Commit das alterações
        if vincular_count > 0:
            db.session.commit()
            print(f"\n=== SUCESSO! ===")
            print(f"Total de {vincular_count} vínculos restaurados baseando-se no histórico de corridas.")
            print("Os pilotos agora devem aparecer com suas equipes no carrossel e nas tabelas.")
        else:
            print("\nNenhum vínculo pendente encontrado ou não há resultados de corrida para processar.")
            print("Se a temporada for nova e não houver corridas, os pilotos devem ser vinculados via Painel Admin.")

if __name__ == "__main__":
    corrigir_vinculos()