import json
from datetime import datetime, timedelta
from app.models import db, Race, RaceResult, Protesto, Team, PilotProfile, GridConfig, HomeCache, News
from sqlalchemy.orm import joinedload
from app.utils import calcular_perda, ORDEM_CARROS, grid_matches
from app.services.team_context import build_team_context
from app.services.scoring_service import ScoringService
from app.services.discipline_service import DisciplineService
from app.services.presentation_service import PresentationService
from app.services.calendar_service import CalendarService

class StandingsService:
    @staticmethod
    def get_home_data(season_id):
        """
        Agrega todos os dados da Home (Notícias, Classificação, Calendário) com cache.
        """
        cache = HomeCache.query.filter_by(season_id=season_id).first()
        if cache and cache.last_updated > datetime.utcnow() - timedelta(minutes=10):
            try:
                print(f"DEBUG: Carregando Home do Cache (Season {season_id})")
                data = json.loads(cache.data_json)
                # Converte chaves de string de volta para int para compatibilidade com o Jinja
                for field in ['standings', 'constructors', 'calendar', 'last_races', 'pilots_by_grid']:
                    if field in data:
                        data[field] = {int(k): v for k, v in data[field].items()}
                return data
            except:
                print("DEBUG: Erro ao ler JSON do cache, recalculando...")
                pass

        print(f"DEBUG: Cache expirado ou inexistente. Recalculando tudo para Season {season_id}...")
        # 1. Notícias
        news = News.query.order_by(News.data_publicacao.desc()).limit(5).all()
        news_list = [n.to_dict() for n in news]
        
        # 2. Configurações de Grid
        grid_configs = GridConfig.query.filter_by(season_id=season_id).order_by(GridConfig.ordem).all()
        grid_configs_json = [{'id': g.id, 'nome': g.nome, 'vagas': g.vagas, 'exibir_lastro': g.exibir_lastro} for g in grid_configs]
        
        # 3. Contexto de Equipes e Construtores
        team_ctx = build_team_context(season_id)
        raw_constructors = ScoringService.build_constructors_for_home(
            season_id, grid_configs, team_ctx["canonical_teams"], team_ctx["alias_ids_by_key"]
        )
        # Serializa as equipes nos construtores para que possam ser salvas no JSON
        constructors = {}
        for g_id, teams_list in raw_constructors.items():
            constructors[g_id] = []
            for item in teams_list:
                constructors[g_id].append({
                    "equipe": item["equipe"].to_dict(),
                    "pontos": item["pontos"],
                    "vitorias": item["vitorias"]
                })

        # 4. Classificação (Standings) e Pilotos por Grid
        standings = { g.id: [] for g in grid_configs }
        pilots_by_grid = { g.id: [] for g in grid_configs }
        
        points_cache = {}
        evolution_cache = {}

        for g in grid_configs:
            for item in team_ctx["participants_by_grid"].get(g.id, []):
                p = item["pilot"]
                team_ref = item["team"]
                key_pg = (p.id, g.id)
                
                if key_pg not in points_cache:
                    points_cache[key_pg] = ScoringService.calculate_pilot_total_points(p.id, season_id, g.id)
                
                res_no_grid = [r for r in p.race_results if r.race.season_id == season_id and grid_matches(r.race, g)]
                vitorias = ScoringService.get_pilot_wins(res_no_grid)

                quali_ban = DisciplineService.is_quali_banned(p.id, g.id)

                foto_final = PresentationService.get_pilot_photo_for_grid(p, g.id)

                if key_pg not in evolution_cache:
                    evolution_cache[key_pg] = ScoringService.generate_points_evolution(p.id, g.id, season_id)

                standings[g.id].append({
                    "piloto": {'id': p.id, 'nome_real': p.nome_real, 'nickname': p.nickname},
                    "pilot": {'id': p.id, 'nome_real': p.nome_real, 'nickname': p.nickname},
                    "pontos": points_cache[key_pg],
                    "vitorias": vitorias,
                    "carro": "",
                    "quali_ban": quali_ban,
                    "foto_url": foto_final,
                    "team_name": team_ref.nome if team_ref else "Sem Equipe",
                    "is_reserve": item["is_reserve"],
                    "evolucao": evolution_cache[key_pg],
                })

                if not any(x["data"]["id"] == p.id for x in pilots_by_grid[g.id]):
                    pilots_by_grid[g.id].append({
                        "data": {'id': p.id, 'nickname': p.nickname},
                        "foto_url": foto_final,
                        "team": team_ref.to_dict() if team_ref else None
                    })

            # Ordenação e Lastro
            standings[g.id].sort(key=lambda x: (x["pontos"], x["vitorias"]), reverse=True)
            PresentationService.assign_ballast(standings[g.id], g)

        # 5. Calendário e Últimas Corridas
        calendar, all_races_db = CalendarService.build_season_calendar(season_id, grid_configs_json)
        last_races = CalendarService.find_last_races(calendar, all_races_db, grid_configs_json)
        
        data = {
            'noticias': news_list,
            'grid_configs': grid_configs_json,
            'standings': standings,
            'constructors': constructors,
            'calendar': calendar,
            'last_races': last_races,
            'pilots_by_grid': pilots_by_grid
        }

        if not cache:
            cache = HomeCache(season_id=season_id)
            db.session.add(cache)
        cache.data_json = json.dumps(data, default=str)
        cache.last_updated = datetime.utcnow()
        db.session.commit()
        return data