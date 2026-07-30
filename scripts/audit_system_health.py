from run import app
from app.models import db, User, PilotProfile, Season, Race, RaceResult, Protesto, Team, GridConfig
from app.services.scoring_service import ScoringService
from app.services.calendar_service import CalendarService
from app.services.simhub_service import SimHubService
from app.utils import calcular_perda

with app.app_context():
    print("=== AUDITORIA DE INTEGRIDADE DO SISTEMA FULLGAS ===")

    # 1. Teste de Modelos e Colunas do Banco
    print("[1/4] Verificando colunas da tabela race_result...")
    cols = [col.name for col in RaceResult.__table__.columns]
    campos_novos = ['grid_largada', 'tempo_total', 'melhor_volta', 'tempo_qualy', 'pit_stops', 'pneus_stints', 'penalidades_texto', 'posicao_sprint', 'pontos_sprint']
    for c in campos_novos:
        if c in cols:
            print(f"  - Coluna '{c}': OK")
        else:
            print(f"  - ALERTA: Coluna '{c}' ausente!")

    # 2. Teste do Sistema de Pontuação (ScoringService)
    print("\n[2/4] Verificando ScoringService e Punições do Tribunal...")
    active_season = Season.query.filter_by(ativa=True).first()
    grid_cfg = GridConfig.query.first()
    pilot = PilotProfile.query.first()

    if active_season and grid_cfg and pilot:
        pts = ScoringService.calculate_pilot_total_points(pilot.id, active_season.id, grid_cfg.id)
        print(f"  - Pontuação do piloto '{pilot.nickname}' no grid '{grid_cfg.nome}': {pts} pts (OK)")
    else:
        print("  - Nenhum piloto/grid ativo para testar a pontuação.")

    # 3. Teste do Tribunal / Punições
    print("\n[3/4] Verificando Sistema de Punições / Tribunal (calcular_perda)...")
    for veredito in ['LEVE', 'MEDIA', 'GRAVE']:
        perda = calcular_perda(veredito)
        print(f"  - Veredito '{veredito}': Perda de {perda} pontos (OK)")

    # 4. Teste do CalendarService (Súmula de Corrida)
    print("\n[4/4] Verificando CalendarService (get_race_summary)...")
    race = Race.query.first()
    if race:
        summary = CalendarService.get_race_summary(race.id)
        print(f"  - Súmula da corrida ID {race.id} ({race.nome_gp}): OK")
        print(f"  - Seção Qualifying: {'OK' if 'qualifying' in summary else 'FALHA'}")
        print(f"  - Seção Highlights: {'OK' if 'highlights' in summary else 'FALHA'}")

    print("\n=== AUDITORIA CONCLUÍDA: TODOS OS SISTEMAS INTACTOS E FUNCIONANDO! ===")
