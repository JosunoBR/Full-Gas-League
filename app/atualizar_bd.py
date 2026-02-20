from run import app
from app.models import db
from sqlalchemy import text

def atualizar_banco():
    with app.app_context():
        print("Iniciando atualização do banco de dados antigo...")
        
        # 1. Cria tabelas novas (como GridConfig) que não existiam
        db.create_all()
        print("- Tabelas novas criadas (se não existiam).")

        # 2. Adiciona colunas novas na tabela pilot_profile se faltarem
        with db.engine.connect() as conn:
            # Verifica e adiciona penalidade_campeonato
            try:
                conn.execute(text("SELECT penalidade_campeonato FROM pilot_profile LIMIT 1"))
            except:
                print("- Adicionando coluna 'penalidade_campeonato'...")
                conn.execute(text("ALTER TABLE pilot_profile ADD COLUMN penalidade_campeonato FLOAT DEFAULT 0.0"))

            # Verifica e adiciona motivo_penalidade
            try:
                conn.execute(text("SELECT motivo_penalidade FROM pilot_profile LIMIT 1"))
            except:
                print("- Adicionando coluna 'motivo_penalidade'...")
                conn.execute(text("ALTER TABLE pilot_profile ADD COLUMN motivo_penalidade TEXT"))

            # Verifica e adiciona grid (caso o banco seja MUITO antigo, mas provavel que ja tenha)
            # O SQLite não suporta alterar tamanho de VARCHAR facilmente, mas o Python lida com isso.
            
        print("Concluído! O banco antigo agora é compatível com o novo sistema.")

if __name__ == "__main__":
    atualizar_banco()
