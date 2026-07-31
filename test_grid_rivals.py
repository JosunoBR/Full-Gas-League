import os
import sys

basedir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, basedir)

out_path = os.path.join(basedir, "test_rivals_output.txt")

with open(out_path, "w", encoding="utf-8") as f:
    try:
        from run import app, db
        from app.models import Season, GridConfig, Race, PilotProfile, RaceResult, Team, User
        from app.services.team_context import build_team_context
        from app.services.scoring_service import ScoringService

        with app.app_context():
            f.write("=== 1. TEMPORADA ATIVA ===\n")
            season = Season.query.filter_by(ativa=True).order_by(Season.id.asc()).first()
            if not season:
                f.write("Nenhuma temporada ativa!\n")
                season = Season.query.order_by(Season.id.desc()).first()
            
            f.write(f"Season: ID={season.id}, Nome='{season.nome}'\n\n")

            f.write("=== 2. GRID CONFIGS ===\n")
            cfgs = GridConfig.query.filter_by(season_id=season.id).all()
            for c in cfgs:
                f.write(f"GridConfig ID={c.id}, Nome='{c.nome}', Ordem={c.ordem}\n")

            f.write("\n=== 3. EQUIPES (TEAMS) ===\n")
            teams = Team.query.filter_by(season_id=season.id).all()
            f.write(f"Total Equipes: {len(teams)}\n")
            for t in teams:
                f.write(f"Team ID={t.id}, Nome='{t.nome}', GridID={t.grid_id}, Pilotos={len(t.pilots)}, Reservas={len(t.reserves)}\n")

            f.write("\n=== 4. PILOTOS (PILOT PROFILES) ===\n")
            pilots = PilotProfile.query.all()
            f.write(f"Total Pilotos: {len(pilots)}\n")
            for p in pilots:
                f.write(f"Pilot ID={p.id}, Nick='{p.nickname}', GridField='{p.grid}', Teams={[t.id for t in p.teams]}, ReserveTeams={[t.id for t in p.reserve_teams]}\n")

            f.write("\n=== 5. CORRIDAS (RACES) ===\n")
            races = Race.query.filter_by(season_id=season.id).all()
            f.write(f"Total Corridas na Season: {len(races)}\n")
            for r in races:
                f.write(f"Race ID={r.id}, GP='{r.nome_gp}', GridID={r.grid_id}, GridField='{r.grid}', Data={r.data_corrida}, Results={len(r.race_results)}\n")

            f.write("\n=== 6. TESTE BUILD_TEAM_CONTEXT ===\n")
            ctx = build_team_context(season.id)
            f.write(f"Grids com participantes em ctx: {list(ctx['participants_by_grid'].keys())}\n")
            for g_id, p_list in ctx['participants_by_grid'].items():
                f.write(f"  Grid ID {g_id}: {len(p_list)} participantes\n")
                for item in p_list:
                    f.write(f"    - Piloto: {item['pilot'].nickname} (ID={item['pilot'].id}), Equipe: {item['team'].nome if item['team'] else 'Sem Equipe'}\n")

            f.write("\n=== 7. TESTE DA BUSCA DA API DA TABELA ===\n")
            grid_input = "Grid Rivals - 2ª TEMP"
            
            # Teste de matching do grid_cfg
            g_cfg_exact = GridConfig.query.filter_by(season_id=season.id, nome=grid_input).first()
            f.write(f"Exact match para '{grid_input}': {g_cfg_exact}\n")

            g_cfgs_all = GridConfig.query.filter_by(season_id=season.id).all()
            f.write("Todos os nomes de GridConfig:\n")
            for c in g_cfgs_all:
                f.write(f"  ID={c.id}, repr(nome)={repr(c.nome)}\n")
                f.write(f"  Equal exact: {c.nome == grid_input}\n")
                f.write(f"  Equal lower: {c.nome.lower() == grid_input.lower()}\n")

    except Exception as err:
        f.write(f"\nERRO EXECUTANDO TESTE: {err}\n")
        import traceback
        f.write(traceback.format_exc())

print("EXECUTADO COM SUCESSO!")
