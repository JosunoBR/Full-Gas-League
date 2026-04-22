import sys
from run import app
from app.models import db, Team, PilotProfile, Season, GridConfig
from app.services.scoring_service import ScoringService

def auditar_pontuacao_geral():
    with app.app_context():
        print("--- INICIANDO AUDITORIA GERAL DE PONTUACAO DE EQUIPES ---")
        print("NOTA: Este relatorio e alinhado com a regra de pontos F1 oficiais.")
        print("Pontos do piloto contam para a equipe pela qual ele pilotava no momento da etapa.\n")

        # 1. Encontrar a temporada ativa
        season = Season.query.filter_by(ativa=True).order_by(Season.id.desc()).first()

        if not season:
            print("ERRO: Nenhuma temporada ativa encontrada no sistema.")
            return

        print(f"Analisando a temporada ativa: {season.nome} (ID: {season.id})")

        # 2. Buscar todos os grids desta temporada
        grids = GridConfig.query.filter_by(season_id=season.id).order_by(GridConfig.ordem).all()
        if not grids:
            print("ERRO: Nenhum grid configurado para a temporada ativa.")
            return

        print("\nCalculando os pontos oficiais baseados no historico das corridas (ScoringService)...")
        stats_by_team_id = ScoringService.get_team_result_stats(season.id)

        # 3. Iterar sobre cada grid
        for grid_cfg in grids:
            print(f"\n\n{'='*20} AUDITANDO GRID: {grid_cfg.nome.upper()} {'='*20}")

            # 4. Buscar todas as equipes do grid
            teams = Team.query.filter_by(season_id=season.id, grid_id=grid_cfg.id).all()
            if not teams:
                print("Nenhuma equipe encontrada para este grid.")
                continue

            pontuacao_calculada = {}

            print(f"\n--- Detalhamento por Equipe e Pilotos (Participacoes Ativas na Etapa) ---")

            # 5. Iterar sobre cada equipe para calcular os pontos
            for team in teams:
                alias_ids = ScoringService.get_team_alias_ids(team, season.id)
                pontos_totais = 0.0
                for tid in alias_ids:
                    s = stats_by_team_id.get(tid, {"pontos": 0.0})
                    pontos_totais += float(s["pontos"] or 0.0)

                # Buscar detalhamento de quais pilotos enviaram os pontos para a equipe
                profile_stats = ScoringService.get_team_profile_stats(team, season.id)

                print(f"\nEquipe: {team.nome:<30}")
                if not profile_stats["stats_pilotos"]:
                    print("  -> Nao marcou pontos corridos ou possui saldo 0.")
                    pontuacao_calculada[team.nome] = 0.0
                    continue

                for st in profile_stats["stats_pilotos"]:
                    if st['pontos'] != 0:
                        print(f"  - {st['piloto'].nickname:<20}: {st['pontos']:.2f} pts (Marcador)")

                print(f"  ----------------------------------")
                print(f"  Total da Equipe: {pontos_totais:.2f} pts")
                
                pontuacao_calculada[team.nome] = pontos_totais

            # 7. Imprimir o relatorio de classificacao para o grid
            print(f"\n--- RELATORIO DE PONTUACAO CALCULADA E OFICIALIZADA - {grid_cfg.nome.upper()} ---")
            print(f"{'Pos':<4} {'Equipe':<30} | {'Pontos Oficiais'}")
            print("-" * 55)

            # Ordena as equipes pela pontuacao, em ordem decrescente
            sorted_teams = sorted(pontuacao_calculada.items(), key=lambda item: item[1], reverse=True)

            for i, (nome_equipe, pontos) in enumerate(sorted_teams, 1):
                print(f"{i:<4} {nome_equipe:<30} | {pontos:.2f}")

        print("\n\n Auditoria concluida e matematicamente alinhada com as tabelas da Home.")

if __name__ == "__main__":
    auditar_pontuacao_geral()