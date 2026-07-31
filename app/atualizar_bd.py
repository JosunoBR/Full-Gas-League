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
            
            # --- RACE RESULT (Campos Detalhados de Corrida FullGas League) ---
            novas_colunas = [
                ("grid_largada", "INTEGER"),
                ("tempo_total", "VARCHAR(30)"),
                ("melhor_volta", "VARCHAR(20)"),
                ("tempo_qualy", "VARCHAR(20)"),
                ("pit_stops", "INTEGER DEFAULT 0"),
                ("pneus_stints", "VARCHAR(50)"),
                ("penalidades_texto", "VARCHAR(100)"),
                ("posicao_sprint", "INTEGER"),
                ("pontos_sprint", "FLOAT DEFAULT 0.0"),
                ("tempo_sprint", "VARCHAR(30)"),
                ("melhor_volta_sprint", "VARCHAR(20)")
            ]
            for col_nome, col_tipo in novas_colunas:
                try:
                    conn.execute(text(f"SELECT {col_nome} FROM race_result LIMIT 1"))
                except:
                    print(f"- Adicionando coluna '{col_nome}' em race_result...")
                    conn.execute(text(f"ALTER TABLE race_result ADD COLUMN {col_nome} {col_tipo}"))

            # --- ACCESS LOG (Métricas de Acesso Web vs App) ---
            try:
                conn.execute(text("SELECT id FROM access_log LIMIT 1"))
            except:
                print("- Criando tabela 'access_log'...")
                db.create_all()

            conn.commit()
        print("Concluído! O banco antigo agora é compatível com o novo sistema.")

if __name__ == "__main__":
    atualizar_banco()
