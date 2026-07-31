import os
import sys

basedir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, basedir)

out_file = os.path.join(basedir, "db_info_output.txt")

with open(out_file, "w", encoding="utf-8") as out:
    try:
        from run import app, db
        from app.models import Season, GridConfig, Race, PilotProfile, RaceResult, Team

        with app.app_context():
            out.write("=== TEMPORADAS ===\n")
            seasons = Season.query.all()
            for s in seasons:
                out.write(f"Season ID: {s.id}, Nome: '{s.nome}', Ativa: {s.ativa}\n")

            active_season = Season.query.filter_by(ativa=True).order_by(Season.id.asc()).first()
            if not active_season:
                out.write("\nNENHUMA TEMPORADA ATIVA ENCONTRADA!\n")
            else:
                out.write(f"\nTemporada Ativa ID: {active_season.id} - '{active_season.nome}'\n")

                out.write("\n=== GRID CONFIGS DA TEMPORADA ATIVA ===\n")
                configs = GridConfig.query.filter_by(season_id=active_season.id).all()
                for c in configs:
                    out.write(f"GridConfig ID: {c.id}, Nome: '{c.nome}', Ordem: {c.ordem}\n")

                out.write("\n=== CORRIDAS DA TEMPORADA ATIVA ===\n")
                races = Race.query.filter_by(season_id=active_season.id).all()
                out.write(f"Total de Corridas na Temporada Ativa: {len(races)}\n")
                for r in races[:20]:
                    out.write(f"Race ID: {r.id}, GP: '{r.nome_gp}', Grid ID: {r.grid_id}, Grid Text: '{r.grid}', Data: {r.data_corrida}\n")

                out.write("\n=== TODAS AS CORRIDAS DA BASE ===\n")
                all_races = Race.query.all()
                out.write(f"Total de Corridas no Banco: {len(all_races)}\n")
                for r in all_races[:20]:
                    out.write(f"All Race ID: {r.id}, Season ID: {r.season_id}, GP: '{r.nome_gp}', Grid ID: {r.grid_id}, Grid Text: '{r.grid}'\n")

                out.write("\n=== TESTE GET_CALENDAR POR GRID ===\n")
                for gname in ["ELITE", "PRO", "LIGHT", "ADVANCED", "INITIAL", "1", "2"]:
                    g_cfg = GridConfig.query.filter_by(season_id=active_season.id, nome=gname.upper()).first()
                    if not g_cfg and gname.isdigit():
                        g_cfg = GridConfig.query.get(int(gname))
                    if not g_cfg:
                        c_list = Race.query.filter(Race.season_id == active_season.id, db.func.upper(Race.grid) == gname.upper()).all()
                    else:
                        c_list = Race.query.filter_by(season_id=active_season.id, grid_id=g_cfg.id).all()
                    out.write(f"Grid query '{gname}': encontrou {len(c_list)} corridas. (grid_cfg: {g_cfg.id if g_cfg else None})\n")

    except Exception as e:
        out.write(f"ERRO AO EXECUTAR: {e}\n")

print("DUMP COMPLETO EM db_info_output.txt")
