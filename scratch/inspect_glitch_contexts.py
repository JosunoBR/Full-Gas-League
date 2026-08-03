import sys
import os
sys.path.insert(0, r"c:\Users\Josué\Documents\Sistema FullGas\app")

from run import app
from app.models import PilotProfile, Season, GridConfig, Race, RaceResult, Team

out = []

with app.app_context():
    glitch = PilotProfile.query.filter(PilotProfile.nickname.ilike('%Glitch%')).first()
    if not glitch:
        out.append("Piloto LRB Glitch não encontrado")
    else:
        out.append(f"Piloto ID={glitch.id} | Nick='{glitch.nickname}' | GridString='{glitch.grid}'")
        out.append(f"Titular Teams: {[(t.id, t.nome, t.season_id, t.grid_id) for t in glitch.teams]}")
        out.append(f"Reserva Teams: {[(t.id, t.nome, t.season_id, t.grid_id) for t in glitch.reserve_teams]}")
        
        active_seasons = Season.query.filter_by(ativa=True).all()
        for s in active_seasons:
            out.append(f"\n--- Season ID={s.id} ('{s.nome}') ---")
            configs = GridConfig.query.filter_by(season_id=s.id).all()
            for c in configs:
                out.append(f"  GridConfig ID={c.id} | Nome='{c.nome}'")

        # Reproduce available_contexts logic from public.py
        available_contexts = []
        p_grids = [g.strip() for g in glitch.grid.split(',')] if glitch.grid else []

        for s in active_seasons:
            configs = GridConfig.query.filter_by(season_id=s.id).all()
            cfg_by_id = {c.id: c for c in configs}
            valid_names = {c.nome for c in configs}
            contexts_seen = set()

            # 1) Grids por vínculo de equipe (titular/reserva)
            team_links = [t for t in glitch.teams if t.season_id == s.id] + [t for t in glitch.reserve_teams if t.season_id == s.id]
            for t in team_links:
                g_id = t.grid_id
                g_name = cfg_by_id[g_id].nome if g_id in cfg_by_id else t.nome
                key = (s.id, g_id, g_name)
                out.append(f"Passo 1 (Equipe): t.id={t.id}, t.nome='{t.nome}', g_id={g_id}, g_name='{g_name}'")
                if key in contexts_seen:
                    continue
                contexts_seen.add(key)
                available_contexts.append({'season_id': s.id, 'season_nome': s.nome, 'grid': g_name, 'grid_id': g_id, 'source': 'equipe'})

            # 2) Grids por resultados
            races_res = db.session.query(Race).join(RaceResult).filter(
                RaceResult.pilot_id == glitch.id,
                Race.season_id == s.id
            ).distinct().all()
            for r in races_res:
                g_name = r.grid
                out.append(f"Passo 2 (Resultados): r.id={r.id}, r.grid_id={r.grid_id}, r.grid='{r.grid}'")
                key = (s.id, r.grid_id, g_name)
                if key in contexts_seen:
                    continue
                contexts_seen.add(key)
                available_contexts.append({'season_id': s.id, 'season_nome': s.nome, 'grid': g_name, 'grid_id': r.grid_id, 'source': 'resultados'})

            # 3) Grids do perfil
            for pg in p_grids:
                g_id = int(pg) if pg.isdigit() else None
                cfg = cfg_by_id.get(g_id) if g_id else None
                g_name = cfg.nome if cfg else pg
                out.append(f"Passo 3 (Perfil.grid): pg='{pg}', g_id={g_id}, g_name='{g_name}'")
                key = (s.id, g_id, g_name)
                if key in contexts_seen:
                    continue
                contexts_seen.add(key)
                available_contexts.append({'season_id': s.id, 'season_nome': s.nome, 'grid': g_name, 'grid_id': g_id, 'source': 'perfil.grid'})

        out.append(f"\nAVAILABLE CONTEXTS RESULT: {available_contexts}")

with open(r"c:\Users\Josué\Documents\Sistema FullGas\scratch\glitch_contexts_debug.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))

print("Inspecao salva em scratch/glitch_contexts_debug.txt")
