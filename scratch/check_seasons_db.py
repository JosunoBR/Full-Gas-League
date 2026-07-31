from run import app, db
from app.models import Season, GridConfig, Team, Race

with app.app_context():
    seasons = Season.query.all()
    print(f"Total de temporadas no banco: {len(seasons)}")
    for s in seasons:
        grids = GridConfig.query.filter_by(season_id=s.id).all()
        teams = Team.query.filter_by(season_id=s.id).all()
        races = Race.query.filter_by(season_id=s.id).all()
        print(f"\n--- Temporada ID {s.id}: '{s.nome}' | Ativa: {s.ativa} | ExibirHome: {s.exibir_home} ---")
        print(f"  Grids: {[(g.id, g.nome) for g in grids]}")
        print(f"  Total Equipes: {len(teams)} | Total Corridas: {len(races)}")
