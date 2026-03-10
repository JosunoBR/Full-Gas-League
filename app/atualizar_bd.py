from run import app
from app.models import db
from sqlalchemy import text

def atualizar_banco():
    with app.app_context():
        print("Iniciando atualização do banco de dados antigo...")
        
        # 1. Cria tabelas novas (como GridConfig, HomeCache) que não existiam
        db.create_all()
        print("- Tabelas novas criadas (se não existiam).")

        # 2. Adiciona colunas novas nas tabelas existentes
        with db.engine.connect() as conn:
            # --- PILOT PROFILE ---
            try:
                conn.execute(text("SELECT penalidade_campeonato FROM pilot_profile LIMIT 1"))
            except:
                print("- Adicionando coluna 'penalidade_campeonato' em pilot_profile...")
                conn.execute(text("ALTER TABLE pilot_profile ADD COLUMN penalidade_campeonato FLOAT DEFAULT 0.0"))

            try:
                conn.execute(text("SELECT motivo_penalidade FROM pilot_profile LIMIT 1"))
            except:
                print("- Adicionando coluna 'motivo_penalidade' em pilot_profile...")
                conn.execute(text("ALTER TABLE pilot_profile ADD COLUMN motivo_penalidade TEXT"))

            # --- PILOT GRID PHOTO (Prevenção de erro 500) ---
            # Verifica se a tabela existe
            try:
                conn.execute(text("SELECT 1 FROM pilot_grid_photo LIMIT 1"))
                has_photo_table = True
            except:
                has_photo_table = False
            
            if has_photo_table:
                try:
                    conn.execute(text("SELECT grid_id FROM pilot_grid_photo LIMIT 1"))
                except:
                    print("- Adicionando coluna 'grid_id' em pilot_grid_photo...")
                    conn.execute(text("ALTER TABLE pilot_grid_photo ADD COLUMN grid_id INTEGER"))
            
        print("Concluído! O banco antigo agora é compatível com o novo sistema.")

if __name__ == "__main__":
    atualizar_banco()
