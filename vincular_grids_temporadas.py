from run import app
from app.models import db, Season, GridConfig, Race, Team, SeasonChampion
from sqlalchemy import text

def reparar_arquitetura_grids():
    with app.app_context():
        print("--- VINCULANDO GRIDS ÀS TEMPORADAS ---")
        
        # 1. Garante que a coluna season_id existe em grid_config
        print("Verificando estrutura da tabela grid_config...")
        
        # No SQLite, remover uma restrição UNIQUE exige recriar a tabela.
        # Como GridConfig é uma tabela de configuração que este script reconstrói,
        # a estratégia mais segura é resetá-la para aplicar o novo modelo sem UNIQUE.
        with db.engine.connect() as conn:
            # Verifica se a coluna season_id existe
            columns = [row[1] for row in conn.execute(text("PRAGMA table_info(grid_config)")).fetchall()]
            
            # Verifica se existe índice UNIQUE no nome
            index_info = conn.execute(text("PRAGMA index_list(grid_config)")).fetchall()
            has_unique_index = any(idx[2] == 1 for idx in index_info)

            if 'season_id' not in columns or has_unique_index:
                print("  > Detectada necessidade de atualização estrutural em grid_config.")
                print("  > Resetando tabela grid_config para remover restrições antigas...")
                
                with db.engine.begin() as trans_conn:
                    trans_conn.execute(text("PRAGMA foreign_keys = OFF"))
                    trans_conn.execute(text("DROP TABLE IF EXISTS grid_config"))
                    # Recria a tabela usando a definição atual do Model (sem UNIQUE)
                    GridConfig.__table__.create(trans_conn)
                    trans_conn.execute(text("PRAGMA foreign_keys = ON"))
                print("  > Tabela grid_config recriada com sucesso.")

        # 2. Limpa a tabela e remove vínculos antigos para reconstrução total
        print("Limpando tabela grid_config e resetando vínculos antigos...")
        GridConfig.query.delete()
        Race.query.update({Race.grid_id: None})
        Team.query.update({Team.grid_id: None})
        SeasonChampion.query.update({SeasonChampion.grid_id: None})
        db.session.commit()

        seasons = Season.query.all()
        for s in seasons:
            print(f"\nProcessando: {s.nome}")
            
            # LÓGICA DE DEFINIÇÃO DE GRIDS POR TEMPORADA (Solicitado pelo Usuário)
            if "Grid Rivals" in s.nome:
                nomes_encontrados = ["RIVALS"]
            elif "Temporada 2" in s.nome:
                nomes_encontrados = ["ELITE", "ADVANCED", "INITIAL"]
            else:
                # Descoberta automática para outras temporadas (Seletivas, etc)
                grids_races = db.session.query(Race.grid).filter_by(season_id=s.id).distinct().all()
                grids_teams = db.session.query(Team.grid).filter_by(season_id=s.id).distinct().all()
                nomes_encontrados = list(set([r[0] for r in grids_races if r[0]] + [t[0] for t in grids_teams if t[0]]))
            
            for nome in nomes_encontrados:
                nome = nome.strip().upper()
                if not nome: continue

                print(f"  > Criando config para grid '{nome}' na temporada {s.id}")
                # Define ordem padrão baseada no nome
                ordem = 1 if 'ELITE' in nome.upper() else 2 if 'ADVANCED' in nome.upper() else 3
                nova_cfg = GridConfig(
                    season_id=s.id,
                    nome=nome,
                    vagas=20,
                    ordem=ordem,
                    exibir_lastro=True
                )
                db.session.add(nova_cfg)
                db.session.flush() # Gera o ID para vincular os filhos
                
                # VINCULAÇÃO CRÍTICA: Atualiza Corridas, Equipes e Campeões para usarem o novo ID
                # Isso garante que o sistema respeite o lugar de cada um
                Race.query.filter(Race.season_id == s.id, db.func.upper(Race.grid) == nome).update({Race.grid_id: nova_cfg.id}, synchronize_session=False)
                Team.query.filter(Team.season_id == s.id, db.func.upper(Team.grid) == nome).update({Team.grid_id: nova_cfg.id}, synchronize_session=False)
                SeasonChampion.query.filter(SeasonChampion.season_id == s.id, db.func.upper(SeasonChampion.grid) == nome).update({SeasonChampion.grid_id: nova_cfg.id}, synchronize_session=False)
        
        db.session.commit()
        print("\n✅ Sucesso! Agora cada temporada tem seus próprios grids independentes.")

if __name__ == "__main__":
    reparar_arquitetura_grids()
