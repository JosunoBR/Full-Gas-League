import sys
from app import create_app
from app.models import Team, Season, GridConfig

app = create_app()
with app.app_context():
    print("=== TEMPORADAS ===")
    for s in Season.query.all():
        print(f"Season ID: {s.id}, Nome: {s.nome}, Ativa: {s.ativa}")
    
    print("\n=== EQUIPES ===")
    for t in Team.query.all():
        print(f"Team ID: {t.id}, Nome: {t.nome}, Grid: {t.grid}, Season ID: {t.season_id}")

    print("\n=== GRIDS ===")
    for g in GridConfig.query.all():
        print(f"Grid ID: {g.id}, Nome: {g.nome}, Season ID: {g.season_id}, Lastro: {g.exibir_lastro}")
