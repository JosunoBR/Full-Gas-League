from run import app
from app.models import db, Season, GridConfig, Team
from datetime import datetime, timezone

# Estrutura de dados baseada na sua lista
DATA_ESTRUTURA = [
    {
        "season_nome": "Temporada 2 / 2026",
        "grids": [
            {
                "nome": "ELITE",
                "ordem": 1,
                "teams": [
                    "Apex Racing", "Scuderia Ferrados", "Rival Pacto GP", "Aurium Racing",
                    "Minardi SMX", "Star Racing", "Mercedola AMG", "Aston Manco", "Lotus", "McLata"
                ]
            },
            {
                "nome": "ADVANCED",
                "ordem": 2,
                "teams": [
                    "Maia Maciel Racing", "Imperium Racing", "APX Racing Fox", "RustEze",
                    "Mercerrari", "Minardi SMX", "Audi Revolut", "Dinoco", "DNF Racing", "Eclipse Motorsport"
                ]
            },
            {
                "nome": "INITIAL",
                "ordem": 3,
                "teams": [
                    "Red Barney", "Schalke Racing", "Jortan", "Senna Racing", "Apex Lamborghini",
                    "Team Caramelo", "Twin Line Racing", "Red Bull Sem Asa", "Escuderia Overdrive", "Mercedes Racing"
                ]
            }
        ]
    },
    {
        "season_nome": "Grid Rivals - Equipes 2026",
        "grids": [
            {
                "nome": "RIVALS",
                "ordem": 1,
                "teams": ["Anaya Racing Team - AYT"]
            }
        ]
    }
]

def cadastrar_equipes():
    with app.app_context():
        print("\n=== INICIANDO CADASTRO E VINCULAÇÃO DE EQUIPES ===")
        
        for s_data in DATA_ESTRUTURA:
            # 1. Garantir que a Temporada existe
            season = Season.query.filter_by(nome=s_data["season_nome"]).first()
            if not season:
                print(f"\nCriando temporada: {s_data['season_nome']}")
                season = Season(nome=s_data["season_nome"], ativa=True, data_inicio=datetime.now(timezone.utc).date())
                db.session.add(season)
                db.session.flush()
            else:
                print(f"\nTemporada encontrada: {season.nome}")

            for g_data in s_data["grids"]:
                # 2. Garantir que o GridConfig existe para esta temporada
                grid_cfg = GridConfig.query.filter_by(season_id=season.id, nome=g_data["nome"]).first()
                if not grid_cfg:
                    print(f"  > Criando GridConfig: {g_data['nome']}")
                    grid_cfg = GridConfig(
                        season_id=season.id,
                        nome=g_data["nome"],
                        vagas=20,
                        ordem=g_data["ordem"],
                        exibir_lastro=True
                    )
                    db.session.add(grid_cfg)
                    db.session.flush()
                
                for t_name in g_data["teams"]:
                    # 3. Garantir Equipe vinculada ao Grid e Temporada
                    # Filtramos por nome, season e grid_id para permitir nomes duplicados em grids diferentes (ex: Minardi)
                    team = Team.query.filter_by(nome=t_name, season_id=season.id, grid_id=grid_cfg.id).first()
                    
                    if not team:
                        print(f"    - Cadastrando equipe: {t_name} no grid {g_data['nome']}")
                        team = Team(
                            nome=t_name,
                            grid=g_data["nome"], # Mantém string para compatibilidade
                            season_id=season.id,
                            grid_id=grid_cfg.id,
                            ativa=True
                        )
                        db.session.add(team)
                    else:
                        # Atualiza se já existir para garantir integridade
                        team.grid_id = grid_cfg.id
                        team.grid = g_data["nome"]

        db.session.commit()
        print("\n✅ Sucesso! Todas as equipes foram organizadas e vinculadas aos IDs corretos.")

if __name__ == "__main__":
    cadastrar_equipes()
