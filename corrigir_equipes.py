from run import app
from app.models import db, Team, Season, GridConfig

# Mapeamento de Equipes para Grids conforme sua lista
CORRECOES_GRID = {
    # INITIAL
    "Red Barney": "INITIAL",
    "Schalke Racing": "INITIAL",
    "Apex Lamborghini": "INITIAL",
    "Jortan": "INITIAL",
    "Team Caramelo": "INITIAL",
    "Senna Racing": "INITIAL",
    "Twin Line Racing": "INITIAL",
    "Red Bull Sem Asa": "INITIAL",
    "Escuderia Overdrive": "INITIAL",
    "Mercedes Racing": "INITIAL",

    # ADVANCED
    "Maia Maciel Racing": "ADVANCED",
    "Imperium Racing": "ADVANCED",
    "APX Racing Fox": "ADVANCED",
    "RustEze": "ADVANCED",
    "Mercerrari": "ADVANCED",
    "Audi Revolut": "ADVANCED",
    "Dinoco": "ADVANCED",
    "Eclipse Motorsport": "ADVANCED",
    "DNF Racing": "ADVANCED",
    # "Minardi SMX": "ADVANCED", # Tratado via lógica especial abaixo (duplicata)

    # ELITE
    "Apex Racing": "ELITE",
    "Scuderia Ferrados": "ELITE",
    "Rival Pacto GP": "ELITE",
    "Aurium Racing": "ELITE",
    # "Minardi SMX": "ELITE", # Tratado via lógica especial abaixo (duplicata)
    "Star Racing": "ELITE",
    "Mercedola AMG": "ELITE",
    "Aston Manco": "ELITE",
    "Lotus": "ELITE",
    "McLata": "ELITE",

    # RIVALS
    "Anaya Racing Team - AYT": "RIVALS"
}

def corrigir_equipes():
    with app.app_context():
        print("--- INICIANDO CORREÇÃO DE EQUIPES ---")
        
        # 1. Tenta encontrar a Temporada 2 / 2026, senão pega a ativa mais recente
        nome_alvo = "Temporada 2 / 2026"
        season = Season.query.filter(Season.nome.ilike(f"%{nome_alvo}%")).first()
        
        if not season:
            print(f"Aviso: Temporada '{nome_alvo}' não encontrada pelo nome exato.")
            season = Season.query.filter_by(ativa=True).order_by(Season.id.desc()).first()
        
        if not season:
            print("ERRO CRÍTICO: Nenhuma temporada ativa encontrada no sistema.")
            return

        print(f"Temporada Alvo definida: {season.nome} (ID: {season.id})")
        
        # 2. Garante que o grid RIVALS exista na configuração (para aparecer a aba)
        rivals_cfg = GridConfig.query.filter_by(nome='RIVALS').first()
        if not rivals_cfg:
            print("Criando configuração para grid RIVALS...")
            # Ordem 4 (assumindo Elite=1, Advanced=2, Initial=3)
            db.session.add(GridConfig(nome='RIVALS', vagas=20, ordem=4, exibir_lastro=True))
            db.session.commit()

        teams = Team.query.all()
        count_season = 0
        count_grid = 0
        minardi_count = 0 # Contador para lidar com a equipe duplicada

        for team in teams:
            # Vincula à temporada se estiver sem vínculo (NULL)
            if team.season_id is None:
                team.season_id = season.id
                count_season += 1
            
            nome_limpo = team.nome.strip()
            
            # Lógica Especial para Minardi SMX (Duplicada em Elite e Advanced)
            if nome_limpo == "Minardi SMX":
                minardi_count += 1
                # Tenta distribuir: 1ª encontrada vai para Advanced, 2ª para Elite
                novo_grid = "ADVANCED" if minardi_count == 1 else "ELITE"
                
                if team.grid != novo_grid:
                    print(f" [DUPLICATA] {team.nome} (ID {team.id}) -> Definido como {novo_grid}")
                    team.grid = novo_grid
                    count_grid += 1
            
            elif nome_limpo in CORRECOES_GRID:
                novo_grid = CORRECOES_GRID[nome_limpo]
                if team.grid != novo_grid:
                    print(f" [GRID] {team.nome}: '{team.grid}' -> '{novo_grid}'")
                    team.grid = novo_grid
                    count_grid += 1
            
            # Se a equipe não está na lista e não tem grid, define um padrão para não sumir da tela
            elif not team.grid or team.grid.strip() == "":
                print(f" [ALERTA] {team.nome} não está na lista. Definindo 'ELITE' temporariamente.")
                team.grid = "ELITE"
                count_grid += 1

        db.session.commit()
        print(f"\nSUCESSO: {count_season} equipes vinculadas à temporada e {count_grid} grids corrigidos.")
        print("Verifique no painel se a Minardi SMX ficou no grid correto (se não, inverta manualmente).")

if __name__ == "__main__":
    corrigir_equipes()
