import os
import sys

# Garante que o diretório atual está no PYTHONPATH para importar a aplicação local
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from run import app, db
from app.models import Season, GridConfig, RaceResult, Race, Team, SeasonChampion
from sqlalchemy import func, case
import shutil
import secrets

with app.app_context():
    # 1. Busca todas as temporadas encerradas
    closed_seasons = Season.query.filter_by(ativa=False).all()
    print(f"Temporadas encerradas encontradas: {[s.nome for s in closed_seasons]}")
    
    upload_folder = app.config['UPLOAD_FOLDER']
    
    for season in closed_seasons:
        print(f"\nProcessando {season.nome} (ID {season.id})...")
        grid_configs = GridConfig.query.filter_by(season_id=season.id).all()
        
        for g_cfg in grid_configs:
            grid_name = g_cfg.nome
            print(f"  Grid: {grid_name} (ID {g_cfg.id})")
            
            # Calcula o ranking de equipes na temporada e grid
            team_results = db.session.query(
                RaceResult.team_id,
                func.sum(RaceResult.pontos_ganhos).label('total_pts'),
                func.sum(case(((RaceResult.posicao == 1) & (RaceResult.dsq == False), 1), else_=0)).label('total_wins')
            ).join(Race).filter(
                Race.season_id == season.id,
                Race.grid_id == g_cfg.id,
                RaceResult.team_id != None
            ).group_by(RaceResult.team_id).all()
            
            if not team_results:
                print(f"    Nenhum resultado de equipe encontrado.")
                continue
                
            # Ordena pelo total de pontos e desempate por vitórias
            sorted_teams = sorted(team_results, key=lambda x: (x.total_pts or 0, x.total_wins or 0), reverse=True)
            print(f"    Equipes no ranking: {len(sorted_teams)}")
            
            # Pega as top 3
            top_3 = sorted_teams[:3]
            
            for j, t_stats in enumerate(top_3):
                pos = j + 1
                team = Team.query.get(t_stats.team_id)
                if not team:
                    continue
                
                # Verifica se já existe um registro para esta equipe neste grid e posição
                existing = SeasonChampion.query.filter_by(
                    season_id=season.id,
                    grid_id=g_cfg.id,
                    category='CONSTRUCTOR',
                    position=pos
                ).first()
                
                if existing:
                    print(f"    [OK] Posição {pos} já registrada: {existing.name} com {existing.pontos} pts")
                    # Atualiza os pontos se necessário
                    if existing.pontos != t_stats.total_pts:
                        existing.pontos = t_stats.total_pts
                        existing.vitorias = t_stats.total_wins
                        print(f"         (pontuação atualizada para {t_stats.total_pts})")
                else:
                    # Copia logo da equipe para o snapshot de campeão
                    champ_logo = None
                    if team.logo_url:
                        ext = team.logo_url.split('.')[-1]
                        champ_logo = f"champ_team_{season.id}_{grid_name}_{pos}_{secrets.token_hex(4)}.{ext}"
                        try:
                            shutil.copy(os.path.join(upload_folder, team.logo_url), os.path.join(upload_folder, champ_logo))
                        except (OSError, FileNotFoundError) as e:
                            print(f"WARN: Falha ao copiar logo da equipe campeã {team.nome}: {e}")
                            champ_logo = None

                    # Adiciona novo registro de campeão (2º ou 3º)
                    print(f"    [NEW] Registrando Posição {pos}: {team.nome} com {t_stats.total_pts} pts")
                    db.session.add(SeasonChampion(
                        season_id=season.id,
                        grid=grid_name,
                        grid_id=g_cfg.id,
                        category='CONSTRUCTOR',
                        position=pos,
                        name=team.nome,
                        image_url=champ_logo,
                        pontos=t_stats.total_pts,
                        vitorias=t_stats.total_wins
                    ))
                    
    db.session.commit()
    print("\nConcluído com sucesso!")
