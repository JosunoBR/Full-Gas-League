from run import app
from app.models import db, Team, Race, SeasonChampion, GridConfig
from sqlalchemy import text

def migrar_para_ids():
    with app.app_context():
        print("\n=== INICIANDO MIGRAÇÃO DE ARQUITETURA (TEXTO -> ID) ===")
        
        # 1. Atualiza o Schema do Banco (Cria as colunas grid_id)
        print("1. Atualizando estrutura do banco de dados...")
        with db.engine.begin() as conn:
            for table in ['team', 'race', 'season_champion']:
                try:
                    conn.execute(text(f"SELECT grid_id FROM {table} LIMIT 1"))
                except:
                    print(f"   > Criando coluna grid_id na tabela {table}...")
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN grid_id INTEGER REFERENCES grid_config(id)"))
        
        # 2. Mapeamento e Normalização de Grids
        print("\n2. Normalizando Grids e Criando Configurações...")
        
        # Busca todos os nomes de grids usados atualmente (Texto)
        grids_usados = set()
        
        races = Race.query.all()
        teams = Team.query.all()
        champs = SeasonChampion.query.all()
        
        for r in races: 
            if r.grid: grids_usados.add(r.grid.strip())
        for t in teams: 
            if t.grid: grids_usados.add(t.grid.strip())
        for c in champs: 
            if c.grid: grids_usados.add(c.grid.strip())
            
        print(f"   > Grids encontrados (Texto): {grids_usados}")
        
        # Garante que existe um GridConfig para cada nome encontrado
        mapa_ids = {} # {'ELITE': 1, 'ADVANCED': 2}
        
        for nome_grid in grids_usados:
            nome_upper = nome_grid.upper()
            
            # Busca ou Cria
            config = GridConfig.query.filter(func.upper(GridConfig.nome) == nome_upper).first()
            if not config:
                print(f"   > Criando configuração para novo grid: {nome_upper}")
                config = GridConfig(nome=nome_upper, vagas=20, ordem=99)
                db.session.add(config)
                db.session.commit() # Commit para gerar o ID
            
            # Mapeia o nome original (ex: "Elite") para o ID (ex: 1)
            mapa_ids[nome_grid] = config.id
            # Mapeia também o upper para garantir
            mapa_ids[nome_upper] = config.id

        print(f"   > Mapa de IDs gerado: {mapa_ids}")

        # 3. Migração dos Dados
        print("\n3. Migrando dados para as novas colunas...")
        
        count_race = 0
        for r in races:
            if r.grid and r.grid.strip() in mapa_ids:
                r.grid_id = mapa_ids[r.grid.strip()]
                count_race += 1
        
        count_team = 0
        for t in teams:
            if t.grid and t.grid.strip() in mapa_ids:
                t.grid_id = mapa_ids[t.grid.strip()]
                count_team += 1
                
        count_champ = 0
        for c in champs:
            if c.grid and c.grid.strip() in mapa_ids:
                c.grid_id = mapa_ids[c.grid.strip()]
                count_champ += 1

        db.session.commit()
        print(f"   > Sucesso! Migrados: {count_race} Corridas, {count_team} Equipes, {count_champ} Campeões.")
        print("\n=== MIGRAÇÃO CONCLUÍDA COM SUCESSO ===")
        print("O sistema agora está pronto para usar IDs relacionais.")

from sqlalchemy import func

if __name__ == "__main__":
    migrar_para_ids()
