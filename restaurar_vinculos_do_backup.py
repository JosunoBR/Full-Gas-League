import sqlite3
import os
from run import app
from app.models import db, PilotProfile, Team, Season

# Configurações
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def restaurar_vinculos():
    # Tenta encontrar o arquivo com as extensões .bd ou .db para evitar erros de digitação
    bkp_path = None
    for ext in ['.bd', '.db']:
        temp_path = os.path.join(BASE_DIR, f'f1_league-bkp{ext}')
        if os.path.exists(temp_path):
            bkp_path = temp_path
            break

    if not bkp_path:
        print(f"❌ Erro: Arquivo de backup não encontrado em {BASE_DIR}")
        print("Certifique-se de que o arquivo 'f1_league-bkp.bd' (ou .db) está na raiz da pasta Full-Gas-League.")
        return

    with app.app_context():
        print("\n=== RESTAURANDO VÍNCULOS DE PILOTOS E EQUIPES DO BACKUP ===")
        
        # 1. Carrega dados do banco atual para memória (Performance e Normalização)
        pilotos_atuais = {p.nickname.upper().strip(): p for p in PilotProfile.query.all()}
        
        # Mapeia equipes atuais por (Nome, Grid)
        seasons_ativas = [s.id for s in Season.query.filter_by(ativa=True).all()]
        equipes_atuais = {} # {(nome, grid): [lista_de_objetos_team]}
        
        for t in Team.query.all():
            # Normaliza o nome do grid (ID ou Texto)
            g_nome = (t.grid_config.nome if t.grid_config else t.grid).upper().strip()
            t_nome = t.nome.upper().strip()
            key = (t_nome, g_nome)
            if key not in equipes_atuais:
                equipes_atuais[key] = []
            equipes_atuais[key].append(t)

        # 2. Conecta ao banco de backup
        conn_bkp = sqlite3.connect(bkp_path)
        conn_bkp.row_factory = sqlite3.Row
        cursor_bkp = conn_bkp.cursor()

        # 3. Mapeia IDs de Pilotos do Backup para os Nicknames
        print("Lendo pilotos do backup...")
        try:
            old_pilots = cursor_bkp.execute("SELECT id, nickname FROM pilot_profile").fetchall()
            old_id_to_nickname = {row['id']: row['nickname'].upper().strip() for row in old_pilots}
        except Exception as e:
            print(f"❌ Erro ao ler pilotos do backup: {e}")
            return

        # 4. Busca os vínculos no backup (Tenta pilot_teams ou coluna team_id)
        print("Buscando vínculos no backup...")
        vinc_bkp = []
        try:
            vinc_bkp = cursor_bkp.execute("""
                SELECT pt.pilot_id, t.nome as team_name, t.grid as grid_name 
                FROM pilot_teams pt 
                JOIN team t ON pt.team_id = t.id
            """).fetchall()
        except:
            vinc_bkp = cursor_bkp.execute("""
                SELECT p.id as pilot_id, t.nome as team_name, t.grid as grid_name 
                FROM pilot_profile p 
                JOIN team t ON p.team_id = t.id 
                WHERE p.team_id IS NOT NULL
            """).fetchall()

        # 5. Aplica os vínculos no banco atual
        count_sucesso = 0
        for row in vinc_bkp:
            nick = old_id_to_nickname.get(row['pilot_id'])
            pilot_obj = pilotos_atuais.get(nick) if nick else None
            
            if pilot_obj:
                t_nome = row['team_name'].upper().strip()
                g_nome = row['grid_name'].upper().strip()
                teams_match = equipes_atuais.get((t_nome, g_nome), [])
                
                for team_obj in teams_match:
                    if team_obj.season_id in seasons_ativas and pilot_obj not in team_obj.pilots:
                        team_obj.pilots.append(pilot_obj)
                        count_sucesso += 1
                        print(f"  [OK] Restaurado: {pilot_obj.nickname} -> {team_obj.nome} ({g_nome})")

        db.session.commit()
        conn_bkp.close()
        print(f"\n=== SUCESSO! {count_sucesso} vínculos restaurados. ===")

if __name__ == "__main__":
    restaurar_vinculos()