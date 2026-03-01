import sqlite3
import os
from run import app
from app.models import db, PilotProfile, Team, Race, RaceResult
from sqlalchemy import func

# Configurações
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
OLD_DB = os.path.join(BASE_DIR, 'f1_league_old.db')

def restaurar_home():
    if not os.path.exists(OLD_DB):
        print(f"❌ Erro: Arquivo {OLD_DB} não encontrado na pasta raiz.")
        return

    with app.app_context():
        print("\n=== RESTAURANDO VÍNCULOS E PONTUAÇÃO DA HOME ===")
        
        # 1. Mapeamento do Banco Novo para memória
        pilotos_novos = {p.nickname.upper().strip(): p for p in PilotProfile.query.all()}
        
        # Mapeia equipes novas por (Nome, Grid_Nome, Season_ID) e também apenas por (Nome, Grid) para fallback
        equipes_novas = {}
        equipes_por_nome_grid = {}
        for t in Team.query.all():
            g_nome = t.grid_config.nome.upper().strip() if t.grid_config else t.grid.upper().strip()
            t_nome = t.nome.upper().strip()
            equipes_novas[(t_nome, g_nome, t.season_id)] = t
            
            key = (t_nome, g_nome)
            if key not in equipes_por_nome_grid: equipes_por_nome_grid[key] = []
            equipes_por_nome_grid[key].append(t)
            
        # Mapeia corridas novas
        corridas_novas = {}
        corridas_por_nome_grid = {}
        for r in Race.query.all():
            g_nome = r.grid_config.nome.upper().strip() if r.grid_config else r.grid.upper().strip()
            r_nome = r.nome_gp.upper().strip()
            corridas_novas[(r_nome, g_nome, r.season_id)] = r
            
            key = (r_nome, g_nome)
            if key not in corridas_por_nome_grid: corridas_por_nome_grid[key] = []
            corridas_por_nome_grid[key].append(r)

        # 2. Conecta ao banco antigo e detecta estrutura
        conn_old = sqlite3.connect(OLD_DB)
        conn_old.row_factory = sqlite3.Row
        cursor_old = conn_old.cursor()
        
        # Verifica se as colunas de temporada existem no banco antigo
        team_cols = [c[1] for c in cursor_old.execute("PRAGMA table_info(team)").fetchall()]
        has_team_season = 'season_id' in team_cols
        
        race_cols = [c[1] for c in cursor_old.execute("PRAGMA table_info(race)").fetchall()]
        has_race_season = 'season_id' in race_cols

        # 3. Mapeia IDs de Pilotos Antigos para os Novos Objetos
        print("Mapeando pilotos...")
        old_id_to_new_pilot = {}
        old_pilots = cursor_old.execute("SELECT id, nickname FROM pilot_profile").fetchall()
        for op in old_pilots:
            p = pilotos_novos.get(op['nickname'].upper().strip())
            if p: old_id_to_new_pilot[op['id']] = p

        # 4. Restaurar Associações de Equipes e Grids nos Perfis
        print("Restaurando vínculos de equipes e carrossel...")
        db.session.execute(db.text("DELETE FROM pilot_teams"))
        
        assoc_antigas = []
        try:
            # Tenta buscar da tabela de associação
            q = "SELECT pt.pilot_id, t.nome as team_name, t.grid as grid_name"
            if has_team_season: q += ", t.season_id"
            q += " FROM pilot_teams pt JOIN team t ON pt.team_id = t.id"
            assoc_antigas = cursor_old.execute(q).fetchall()
        except:
            # Fallback para coluna team_id no perfil
            rows = cursor_old.execute("SELECT id as pilot_id, team_id FROM pilot_profile WHERE team_id IS NOT NULL").fetchall()
            for r in rows:
                q_t = "SELECT nome, grid"
                if has_team_season: q_t += ", season_id"
                q_t += " FROM team WHERE id=?"
                t_info = cursor_old.execute(q_t, (r['team_id'],)).fetchone()
                if t_info:
                    d = {'pilot_id': r['pilot_id'], 'team_name': t_info['nome'], 'grid_name': t_info['grid']}
                    if has_team_season: d['season_id'] = t_info['season_id']
                    assoc_antigas.append(d)

        count_assoc = 0
        for row in assoc_antigas:
            p = old_id_to_new_pilot.get(row['pilot_id'])
            if not p: continue

            g_nome = row['grid_name'].upper().strip() if row['grid_name'] else ""
            t_nome = row['team_name'].upper().strip()
            
            # Identifica quais equipes no banco novo correspondem a este vínculo
            target_teams = []
            if has_team_season and 'season_id' in row.keys():
                t = equipes_novas.get((t_nome, g_nome, row['season_id']))
                if t: target_teams.append(t)
            else:
                # Se não sabemos a temporada, vinculamos em todas as temporadas onde essa equipe existe
                target_teams = equipes_por_nome_grid.get((t_nome, g_nome), [])
            
            # Atualiza a string de grid do perfil para o carrossel
            grids_atuais = [x.strip().upper() for x in p.grid.split(',')]
            if g_nome and g_nome not in grids_atuais:
                if 'SEM_GRID' in grids_atuais: grids_atuais.remove('SEM_GRID')
                grids_atuais.append(g_nome)
                p.grid = ",".join(sorted(list(set(grids_atuais))))
            
            for t in target_teams:
                if t not in p.teams:
                    p.teams.append(t)
                    count_assoc += 1

        # 5. Restaurar Resultados (Pontos nas Tabelas)
        print("Restaurando resultados de corridas (pontuação)...")
        RaceResult.query.delete()
        
        res_cols = [c[1] for c in cursor_old.execute("PRAGMA table_info(race_result)").fetchall()]
        has_fan = 'piloto_torcida' in res_cols

        q_res = "SELECT rr.*, r.nome_gp, r.grid as r_grid"
        if has_race_season: q_res += ", r.season_id"
        q_res += ", t.nome as t_nome, t.grid as t_grid"
        q_res += " FROM race_result rr JOIN race r ON rr.race_id = r.id LEFT JOIN team t ON rr.team_id = t.id"
        
        old_results = cursor_old.execute(q_res).fetchall()
        
        count_res = 0
        for row in old_results:
            p = old_id_to_new_pilot.get(row['pilot_id'])
            r_g_nome = row['r_grid'].upper().strip() if row['r_grid'] else ""
            r_name = row['nome_gp'].upper().strip()
            
            race = None
            if has_race_season:
                race = corridas_novas.get((r_name, r_g_nome, row['season_id']))
            else:
                # Fallback: pega a primeira corrida com este nome/grid no banco novo
                matches = corridas_por_nome_grid.get((r_name, r_g_nome), [])
                if matches: race = matches[0]
            
            if p and race:
                t_id = None
                if row['t_nome']:
                    t_g_nome = row['t_grid'].upper().strip() if row['t_grid'] else ""
                    t_name = row['t_nome'].upper().strip()
                    # Tenta encontrar a equipe dentro da mesma temporada da corrida
                    t = equipes_novas.get((t_name, t_g_nome, race.season_id))
                    if t: t_id = t.id

                res = RaceResult(
                    race_id=race.id, pilot_id=p.id, team_id=t_id,
                    posicao=row['posicao'], pontos_ganhos=row['pontos_ganhos'],
                    dnf=bool(row['dnf']), dsq=bool(row['dsq']),
                    volta_rapida=bool(row['volta_rapida']),
                    piloto_do_dia=bool(row['piloto_do_dia']),
                    piloto_torcida=bool(row['piloto_torcida']) if has_fan else False,
                    ausencia=row['ausencia']
                )
                db.session.add(res)
                count_res += 1

        db.session.commit()
        conn_old.close()
        print(f"\n✅ SUCESSO:")
        print(f"  > {count_assoc} vínculos de equipe e grids restaurados.")
        print(f"  > {count_res} resultados de corrida (pontos) restaurados.")
        print("\nReinicie o servidor e verifique a Home. Tudo deve estar no lugar agora!")

if __name__ == "__main__":
    restaurar_home()
