from run import app
from app.models import db, Team
import os

def remover_equipes_inativas():
    with app.app_context():
        print("=== INICIANDO REMOÇÃO DE EQUIPES DESATIVADAS ===")
        
        # Busca todas as equipes onde ativa é False
        equipes_inativas = Team.query.filter_by(ativa=False).all()
        
        if not equipes_inativas:
            print("Nenhuma equipe desativada encontrada no banco de dados.")
            return

        print(f"Encontradas {len(equipes_inativas)} equipes para remover.")
        
        count = 0
        for team in equipes_inativas:
            nome = team.nome
            tid = team.id
            
            # 1. Limpa associações de pilotos e reservas (tabelas de ligação pilot_teams/pilot_reserves)
            team.pilots.clear()
            team.reserves.clear()
            
            # 2. Remove o arquivo de logo físico se existir
            if team.logo_url:
                path = os.path.join(app.config['UPLOAD_FOLDER'], team.logo_url)
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception as e:
                        print(f"  [!] Erro ao deletar arquivo {team.logo_url}: {e}")

            # 3. Deleta o registro da equipe
            db.session.delete(team)
            print(f"  > Equipe '{nome}' (ID: {tid}) removida com sucesso.")
            count += 1
            
        db.session.commit()
        print(f"\n✅ Concluído! {count} equipes foram removidas permanentemente.")

if __name__ == "__main__":
    remover_equipes_inativas()