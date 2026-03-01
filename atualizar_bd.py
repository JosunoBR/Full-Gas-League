from run import app
from app.models import db
from sqlalchemy import text

def atualizar_banco():
    with app.app_context():
        print("Iniciando atualização e correção do banco de dados...")
        
        # 1. Cria tabelas novas (como GridConfig, SeasonChampion, PilotGridPhoto, pilot_teams, pilot_reserves) que não existiam
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

            # Verifica e adiciona exibir_lastro em grid_config
            try:
                conn.execute(text("SELECT exibir_lastro FROM grid_config LIMIT 1"))
            except:
                print("- Adicionando coluna 'exibir_lastro' em grid_config...")
                conn.execute(text("ALTER TABLE grid_config ADD COLUMN exibir_lastro BOOLEAN DEFAULT 1"))

            # Verifica e adiciona season_id em team
            try:
                conn.execute(text("SELECT season_id FROM team LIMIT 1"))
            except:
                print("- Adicionando coluna 'season_id' em team...")
                conn.execute(text("ALTER TABLE team ADD COLUMN season_id INTEGER REFERENCES season(id)"))
                
                # MIGRAÇÃO DE DADOS: Vincula equipes existentes à temporada ativa mais recente
                # Isso impede que as equipes sumam da tela após a atualização
                print("- Vinculando equipes existentes à temporada ativa mais recente...")
                result = conn.execute(text("SELECT id FROM season WHERE ativa = 1 ORDER BY id DESC LIMIT 1")).first()
                if result:
                    latest_season_id = result[0]
                    conn.execute(text("UPDATE team SET season_id = :sid WHERE season_id IS NULL"), {"sid": latest_season_id})
                    print(f"  > Equipes antigas vinculadas à temporada ID {latest_season_id}")

            # MIGRAÇÃO DE EQUIPES (De team_id para pilot_teams)
            # Verifica se existem dados na tabela antiga e migra para a nova
            try:
                # Seleciona pilotos com equipe definida na coluna antiga
                result = conn.execute(text("SELECT id, team_id FROM pilot_profile WHERE team_id IS NOT NULL"))
                migrated_count = 0
                for row in result:
                    # Insere na nova tabela de associação (ignorando duplicatas)
                    conn.execute(text("INSERT OR IGNORE INTO pilot_teams (pilot_id, team_id) VALUES (:pid, :tid)"), {"pid": row[0], "tid": row[1]})
                    migrated_count += 1
                if migrated_count > 0:
                    print(f"- Migrados {migrated_count} registros de equipe para o novo formato multi-grid.")
            except Exception as e:
                print(f"- Nota sobre migração de equipes: {e}")

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