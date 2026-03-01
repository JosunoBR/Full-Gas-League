import sqlite3
import os
from run import app
from app.models import db, PilotProfile, Team, Race, RaceResult, Season, GridConfig
from sqlalchemy import func

# Configurações
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
OLD_DB = os.path.join(BASE_DIR, 'f1_league_old.db')

def migrar_dados():
    if not os.path.exists(OLD_DB):
        print(f"❌ Erro: Arquivo {OLD_DB} não encontrado.")
        return

    with app.app_context():
        print("\n=== INICIANDO AJUSTE DE RESULTADOS E VÍNCULOS (TEXTO -> ID) ===")
        
        # Conecta ao banco antigo
        conn_old = sqlite3.connect(OLD_DB)
        conn_old.row_factory = sqlite3.Row
        cursor_old = conn_old.cursor()

        # 1. MAPEAMENTO DE PILOTOS (Nickname -> Novo ID)
        print("1. Mapeando pilotos...")
        pilotos_novos = {p.nickname.upper(): p.id for p in PilotProfile.query.all()}
        mapa_pilotos = {} # old_id -> new_id
        
        try:
            old_pilots = cursor_old.execute("SELECT id, nickname FROM pilot_profile").fetchall()
            for op in old_pilots:
                nick = op['nickname'].upper()
                if nick in pilotos_novos:
                    mapa_pilotos[op['id']] = pilotos_novos[nick]
        except Exception as e:
            print(f"   > Aviso ao ler pilotos antigos: {e}")

        # 2. MAPEAMENTO DE CORRIDAS (GP + Grid -> Novo ID)
        print("2. Mapeando corridas...")
        corridas_novas = {(r.nome_gp.upper(), r.grid.upper() if r.grid else ""): r.id for r in Race.query.all()}
        mapa_corridas = {} # old_id -> new_id

        try:
            old_races = cursor_old.execute("SELECT * FROM race").fetchall()
            for ora in old_races:
                nome_gp_old = ora['nome_gp'].upper()
                grid_old = ora['grid'].upper() if 'grid' in ora.keys() and ora['grid'] else ""
                chave = (nome_gp_old, grid_old)
                if chave in corridas_novas:
                    mapa_corridas[ora['id']] = corridas_novas[chave]
        except Exception as e:
            print(f"   > Aviso ao ler corridas antigas: {e}")

        # 3. MAPEAMENTO DE INFORMAÇÕES DE EQUIPES ANTIGAS
        print("3. Coletando nomes de equipes antigas para referência...")
        old_teams_info = {}
        try:
            rows = cursor_old.execute("SELECT id, nome, grid FROM team").fetchall()
            for r in rows:
                old_teams_info[r['id']] = {
                    'nome': r['nome'].upper(), 
                    'grid': r['grid'].upper() if r['grid'] else ""
                }
        except:
            pass

        # 4. RESTAURAÇÃO DE VÍNCULOS DE EQUIPES (PILOTO <-> EQUIPE)
        print("4. Restaurando vínculos de pilotos com equipes (Titulares e Reservas)...")
        db.session.execute(db.text("DELETE FROM pilot_teams"))
        db.session.execute(db.text("DELETE FROM pilot_reserves"))
        db.session.commit()
        
        count_assoc = 0
        try:
            # Tenta ler da tabela de associação ou da coluna team_id
            associações = []
            try:
                associações = cursor_old.execute("SELECT pilot_id, team_id FROM pilot_teams").fetchall()
            except:
                associações = cursor_old.execute("SELECT id as pilot_id, team_id FROM pilot_profile WHERE team_id IS NOT NULL").fetchall()

            for assoc in associações:
                new_p_id = mapa_pilotos.get(assoc['pilot_id'])
                old_t_id = assoc['team_id']
                
                if new_p_id and old_t_id in old_teams_info:
                    p = db.session.get(PilotProfile, new_p_id)
                    t_info = old_teams_info[old_t_id]
                    
                    # Busca a equipe no novo banco que combine com nome e grid
                    # Como equipes agora são por temporada, pegamos a mais recente ou a que combine
                    t_match = Team.query.filter(
                        func.upper(Team.nome) == t_info['nome'],
                        func.upper(Team.grid) == t_info['grid']
                    ).first()
                    
                    if p and t_match and t_match not in p.teams:
                        p.teams.append(t_match)
                        count_assoc += 1
        except Exception as e:
            print(f"   > Erro ao restaurar vínculos: {e}")
        print(f"   > {count_assoc} vínculos de pilotos restaurados.")

        # 5. MIGRAÇÃO DE RESULTADOS (O CORAÇÃO DA PONTUAÇÃO)
        print("5. Migrando resultados de corridas (Ajustando IDs de Pilotos e Equipes)...")
        RaceResult.query.delete()
        
        try:
            old_results = cursor_old.execute("SELECT * FROM race_result").fetchall()
            count_res = 0
            for ores in old_results:
                new_r_id = mapa_corridas.get(ores['race_id'])
                new_p_id = mapa_pilotos.get(ores['pilot_id'])
                
                if new_r_id and new_p_id:
                    race_obj = db.session.get(Race, new_r_id)
                    pilot_obj = db.session.get(PilotProfile, new_p_id)
                    
                    # Lógica para encontrar o ID da Equipe correta no novo sistema
                    new_t_id = None
                    old_tid = ores['team_id']
                    
                    if old_tid and old_tid in old_teams_info:
                        t_info = old_teams_info[old_tid]
                        # Procura equipe no novo banco com mesmo nome, temporada e grid_id da corrida
                        t_match = Team.query.filter(
                            Team.season_id == race_obj.season_id,
                            func.upper(Team.nome) == t_info['nome'],
                            (Team.grid_id == race_obj.grid_id if race_obj.grid_id else func.upper(Team.grid) == t_info['grid'])
                        ).first()
                        if t_match:
                            new_t_id = t_match.id
                    
                    if not new_t_id:
                        # Fallback: Procura qualquer equipe do piloto nesta temporada/grid
                        r_grid_name = (race_obj.grid_config.nome if race_obj.grid_config else race_obj.grid).upper()
                        for t in pilot_obj.teams:
                            t_grid_name = (t.grid_config.nome if t.grid_config else t.grid).upper()
                            if t.season_id == race_obj.season_id and t_grid_name == r_grid_name:
                                new_t_id = t.id
                                break
                    
                    res = RaceResult(
                        race_id=new_r_id,
                        pilot_id=new_p_id,
                        team_id=new_t_id,
                        posicao=ores['posicao'],
                        pontos_ganhos=ores['pontos_ganhos'],
                        volta_rapida=bool(ores['volta_rapida']),
                        piloto_do_dia=bool(ores['piloto_do_dia']),
                        piloto_torcida=bool(ores.get('piloto_torcida', 0)),
                        dnf=bool(ores['dnf']),
                        dsq=bool(ores['dsq']),
                        ausencia=ores['ausencia']
                    )
                    db.session.add(res)
                    count_res += 1
            print(f"   > {count_res} resultados de corrida ajustados e restaurados.")
        except Exception as e:
            print(f"   > Erro crítico nos resultados: {e}")

        db.session.commit()
        conn_old.close()
        print("\n✅ AJUSTE CONCLUÍDO!")
        print("Os resultados agora usam os novos IDs e as pontuações devem estar corretas na Home.")

if __name__ == "__main__":
    migrar_dados()
