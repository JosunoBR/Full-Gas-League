import os
import sys

from run import app, db
from app.models import Season, GridConfig, Race, PilotProfile, RaceResult, Team

with app.app_context():
    print("=== TEMPORADAS ===")
    seasons = Season.query.all()
    for s in seasons:
        print(f"Season ID: {s.id}, Nome: {s.nome}, Ativa: {s.ativa}")

    active_season = Season.query.filter_by(ativa=True).order_by(Season.id.asc()).first()
    if not active_season:
        print("NENHUMA TEMPORADA ATIVA ENCONTRADA!")
    else:
        print(f"\nTemporada Ativa ID: {active_season.id} - {active_season.nome}")

        print("\n=== GRID CONFIGS DA TEMPORADA ATIVA ===")
        configs = GridConfig.query.filter_by(season_id=active_season.id).all()
        for c in configs:
            print(f"GridConfig ID: {c.id}, Nome: '{c.nome}', Ordem: {c.ordem}")

        print("\n=== CORRIDAS DA TEMPORADA ATIVA ===")
        races = Race.query.filter_by(season_id=active_season.id).all()
        print(f"Total de Corridas na Temporada Ativa: {len(races)}")
        for r in races[:15]:
            print(f"Race ID: {r.id}, GP: '{r.nome_gp}', Grid ID: {r.grid_id}, Grid Text: '{r.grid}', Data: {r.data_corrida}")

        print("\n=== TODOS OS GRID CONFIGS DA BASE ===")
        all_cfgs = GridConfig.query.all()
        for c in all_cfgs:
            print(f"All GridConfig ID: {c.id}, Season ID: {c.season_id}, Nome: '{c.nome}'")

        print("\n=== TODAS AS CORRIDAS DA BASE ===")
        all_races = Race.query.all()
        print(f"Total de Corridas no Banco: {len(all_races)}")
        for r in all_races[:15]:
            print(f"All Race ID: {r.id}, Season ID: {r.season_id}, GP: '{r.nome_gp}', Grid ID: {r.grid_id}, Grid Text: '{r.grid}'")
