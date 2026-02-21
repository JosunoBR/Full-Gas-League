from run import app
from app.models import db
from sqlalchemy import text

def atualizar_banco():
    with app.app_context():
        print("Iniciando atualização e correção do banco de dados...")
        
        # 1. Cria tabelas novas (como GridConfig, SeasonChampion) que não existiam
        db.create_all()
        print("- Tabelas estruturais sincronizadas.")

        # 2. Adiciona colunas novas na tabela pilot_profile se faltarem
        # Usa 'begin()' para garantir commit automático das alterações
        with db.engine.begin() as conn:
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

            # 3. CORREÇÃO CRÍTICA DO ERRO DE MIGRAÇÃO
            # Remove a tabela alembic_version para resetar o histórico de migração quebrado
            print("- Resetando histórico de migração (tabela alembic_version)...")
            try:
                conn.execute(text("DROP TABLE alembic_version"))
                print("  > Tabela de versão antiga removida com sucesso.")
            except Exception as e:
                print(f"  > Tabela alembic_version não precisou ser removida ou não existia.")

        print("-" * 30)
        print("SUCESSO! O banco de dados foi corrigido.")
        print("Agora você pode rodar os comandos de migração sem erros.")

if __name__ == "__main__":
    atualizar_banco()