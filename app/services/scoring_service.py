from sqlalchemy import func, case
from app.models import db, RaceResult, Race, Protesto, PilotProfile, Team
from app.utils import calcular_perda, PONTUACAO_20, PONTUACAO_22
from app.services.team_context import normalize_team_name

class ScoringService:
    @staticmethod
    def calculate_race_points(result, grid_size=22):
        """
        Calcula a pontuação obtida por um piloto em uma corrida com base na sua posição final,
        tamanho do grid e bônus acumulados (VR, DOTD, FAN).
        """
        if not result or getattr(result, 'dnf', False) or getattr(result, 'dsq', False):
            return 0.0
        if getattr(result, 'status_presenca', 'OK') in ['FJ', 'FNJ']:
            return 0.0

        pos = getattr(result, 'posicao', None)
        if not pos or pos <= 0:
            return 0.0

        table = PONTUACAO_22 if grid_size >= 22 else PONTUACAO_20
        base_points = float(table.get(int(pos), 0))

        bonus = 0.0
        if getattr(result, 'volta_rapida', False):
            bonus += 1.0
        if getattr(result, 'piloto_do_dia', False):
            bonus += 1.0
        if getattr(result, 'piloto_torcida', False):
            bonus += 1.0

        return base_points + bonus
    @staticmethod
    def calculate_pilot_total_points(pilot_id, season_id, grid_id):
        """
        Calcula os pontos totais de um piloto em uma temporada/grid específico.
        Desconta punições do tribunal E penalidade manual.
        """
        # Busca todos os resultados do piloto nesta temporada/grid
        resultados = RaceResult.query.join(Race).filter(
            RaceResult.pilot_id == pilot_id,
            Race.season_id == season_id,
            Race.grid_id == grid_id
        ).all()
        
        # Soma pontos das corridas (incluindo Sprint se houver)
        pontos_corridas = float(sum((r.pontos_ganhos or 0) + (getattr(r, 'pontos_sprint', 0) or 0) for r in resultados))
        
        # Soma punições do tribunal para este grid específico nesta temporada
        punicoes_tribunal = Protesto.query.join(Race).filter(
            Protesto.acusado_id == pilot_id,
            Protesto.grid_id == grid_id,
            Race.season_id == season_id,
            Protesto.status == 'CONCLUIDO'
        ).all()
        total_punicoes_tribunal = sum(calcular_perda(p.veredito_final) for p in punicoes_tribunal)
        
        # Penalidade manual do campeonato
        piloto = PilotProfile.query.get(pilot_id)
        penalidade_manual = float(piloto.penalidade_campeonato or 0) if piloto else 0.0
        
        # Cálculo final
        pontos_totais = pontos_corridas - total_punicoes_tribunal - penalidade_manual
        
        return round(pontos_totais, 1)

    @staticmethod
    def get_team_result_stats(season_id):
        """Return stats by team_id from race_result for a season."""
        stats_query = (
            RaceResult.query.with_entities(
                RaceResult.team_id,
                func.sum(RaceResult.pontos_ganhos).label("total_pontos"),
                func.sum(
                    case((((RaceResult.posicao == 1) & (RaceResult.dsq == False)), 1), else_=0)
                ).label("total_vitorias"),
            )
            .join(Race)
            .filter(Race.season_id == season_id, RaceResult.team_id.is_not(None))
            .group_by(RaceResult.team_id)
            .all()
        )
        return {
            row.team_id: {
                "pontos": float(row.total_pontos or 0.0),
                "vitorias": int(row.total_vitorias or 0),
            }
            for row in stats_query
        }

    @staticmethod
    def preload_season_points(season_id):
        """
        Retorna um dicionário {(pilot_id, grid_id): total_pontos} com a pontuação de TODOS
        os pilotos/grids da temporada em apenas 3 consultas SQL agregadas.
        """
        results = (
            db.session.query(
                RaceResult.pilot_id,
                Race.grid_id,
                func.sum(
                    func.coalesce(RaceResult.pontos_ganhos, 0.0) +
                    func.coalesce(RaceResult.pontos_sprint, 0.0)
                ).label("pontos_corridas")
            )
            .join(Race, RaceResult.race_id == Race.id)
            .filter(Race.season_id == season_id)
            .group_by(RaceResult.pilot_id, Race.grid_id)
            .all()
        )
        
        race_points = {(r.pilot_id, r.grid_id): float(r.pontos_corridas or 0.0) for r in results}

        protestos = (
            db.session.query(
                Protesto.acusado_id,
                Protesto.grid_id,
                Protesto.veredito_final
            )
            .join(Race, Protesto.etapa_id == Race.id)
            .filter(Race.season_id == season_id, Protesto.status == 'CONCLUIDO')
            .all()
        )
        
        punish_map = {}
        for p in protestos:
            key = (p.acusado_id, p.grid_id)
            perda = calcular_perda(p.veredito_final)
            punish_map[key] = punish_map.get(key, 0.0) + perda

        pilotos = PilotProfile.query.with_entities(PilotProfile.id, PilotProfile.penalidade_campeonato).all()
        manual_map = {p.id: float(p.penalidade_campeonato or 0.0) for p in pilotos}

        all_keys = set(race_points.keys()).union(set(punish_map.keys()))
        points_map = {}
        for (pid, gid) in all_keys:
            pts = race_points.get((pid, gid), 0.0) - punish_map.get((pid, gid), 0.0) - manual_map.get(pid, 0.0)
            points_map[(pid, gid)] = round(pts, 1)

        return points_map

    @staticmethod
    def build_constructors_for_home(season_id, grid_configs, canonical_teams, alias_ids_by_key=None, points_map=None):
        """
        Build constructors table by grid.
        Source of truth is the sum of total points of all pilots registered (titulars) in the team.
        """
        if points_map is None:
            points_map = ScoringService.preload_season_points(season_id)

        constructors = {g.id: [] for g in grid_configs}

        for team in canonical_teams:
            if not team.grid_id or team.grid_id not in constructors:
                continue
            
            todos_pilotos = list(team.pilots) + list(team.reserves)
            total_pts = sum(
                points_map.get((pilot.id, team.grid_id), 0.0)
                for pilot in todos_pilotos
            )
            
            total_wins = 0
            for pilot in todos_pilotos:
                res_no_grid = [r for r in pilot.race_results if r.race.season_id == season_id and r.race.grid_id == team.grid_id]
                total_wins += sum(1 for r in res_no_grid if r.posicao == 1 and not r.dsq)

            constructors[team.grid_id].append({
                "equipe": team,
                "pontos": round(total_pts, 1),
                "vitorias": total_wins
            })

        for grid_id in constructors:
            constructors[grid_id].sort(key=lambda x: (x["pontos"], x["vitorias"]), reverse=True)

        return constructors

    @staticmethod
    def get_team_alias_ids(team: Team, season_id: int):
        """Return all team ids considered aliases for the same logical team in a season."""
        if not team or not season_id:
            return []
        if not team.grid_id:
            return [team.id]

        same_name_teams = Team.query.filter(
            Team.season_id == season_id,
            Team.grid_id == team.grid_id,
            func.upper(func.trim(Team.nome)) == normalize_team_name(team.nome),
        ).all()
        if not same_name_teams:
            return [team.id]
        return [t.id for t in same_name_teams]

    @staticmethod
    def team_has_results_in_season(team: Team, season_id: int):
        """Checks if logical team has any race_result in season."""
        alias_ids = ScoringService.get_team_alias_ids(team, season_id)
        if not alias_ids:
            return False

        query = RaceResult.query.join(Race).filter(
            Race.season_id == season_id,
            RaceResult.team_id.in_(alias_ids),
        )
        if team.grid_id:
            query = query.filter(Race.grid_id == team.grid_id)
        return query.first() is not None

    @staticmethod
    def get_team_profile_stats(team: Team, season_id: int):
        """
        Source of truth for public team profile stats:
        - totals and pilot breakdown from currently registered titular pilots.
        """
        stats_pilotos = []
        total_pontos = 0.0
        total_vitorias = 0
        
        for pilot in list(team.pilots) + list(team.reserves):
            # Calcula a pontuação total do piloto no grid/temporada (incluindo punições e penalidades manuais)
            pontos = ScoringService.calculate_pilot_total_points(pilot.id, season_id, team.grid_id)
            
            # Soma as vitórias do piloto neste grid/temporada
            res_no_grid = [r for r in pilot.race_results if r.race.season_id == season_id and r.race.grid_id == team.grid_id]
            vitorias = sum(1 for r in res_no_grid if r.posicao == 1 and not r.dsq)
            
            total_pontos += pontos
            total_vitorias += vitorias
            stats_pilotos.append({
                "piloto": pilot,
                "pontos": pontos,
                "vitorias": vitorias
            })
            
        stats_pilotos.sort(key=lambda x: (x["pontos"], x["vitorias"]), reverse=True)
        
        return {
            "total_pontos": round(total_pontos, 1),
            "total_vitorias": int(total_vitorias),
            "stats_pilotos": stats_pilotos,
        }
        
    @staticmethod
    def get_orphan_results_without_team(season_id):
        rows = (
            RaceResult.query.join(Race)
            .filter(Race.season_id == season_id, RaceResult.team_id.is_(None))
            .count()
        )
        return int(rows)

    @staticmethod
    def get_pilot_wins(pilot_race_results):
        """
        Calcula o número de vitórias a partir de uma lista de resultados de corrida.
        """
        return sum(1 for r in pilot_race_results if r.posicao == 1 and not r.dsq)

    @staticmethod
    def generate_points_evolution(pilot_id, grid_id, season_id):
        """
        Gera dados de evolução acumulativa de pontos para um piloto em um grid específico.
        Movido de utils.py para centralizar lógica de pontuação.
        """
        # 1. Busca apenas os dados necessários das corridas concluídas
        corridas = db.session.query(Race.id, Race.nome_gp, Race.data_corrida)\
            .filter(Race.season_id == season_id, Race.grid_id == grid_id, Race.status == 'Concluida')\
            .order_by(Race.data_corrida).all()
        
        if not corridas:
            return []
        
        # 2. Busca apenas os pontos ganhos pelo piloto
        resultados = db.session.query(RaceResult.race_id, RaceResult.pontos_ganhos)\
            .join(Race)\
            .filter(RaceResult.pilot_id == pilot_id, Race.season_id == season_id, Race.grid_id == grid_id)\
            .all()
        results_dict = {r.race_id: r.pontos_ganhos for r in resultados}
        
        # 3. Busca punições do tribunal para este grid
        punicoes = db.session.query(Protesto.etapa_id, Protesto.veredito_final)\
            .join(Race, Protesto.etapa_id == Race.id)\
            .filter(Protesto.acusado_id == pilot_id, Protesto.status == 'CONCLUIDO', 
                    Race.season_id == season_id, Race.grid_id == grid_id).all()
        punicoes_dict = {}
        for p in punicoes:
            punicoes_dict[p.etapa_id] = punicoes_dict.get(p.etapa_id, 0.0) + calcular_perda(p.veredito_final)
        
        evolucao = [{
            'gp': 'Início',
            'data': '',
            'pontos_acumulados': 0.0,
            'pontos_corrida': 0.0
        }]
        pontos_acumulados = 0.0
        
        for corrida in corridas:
            pontos_corrida = float(results_dict.get(corrida.id) or 0.0)
            penalidade = punicoes_dict.get(corrida.id, 0)
            pontos_acumulados += (pontos_corrida - penalidade)
            
            evolucao.append({
                'gp': corrida.nome_gp,
                'data': corrida.data_corrida.strftime('%d/%m'),
                'pontos_acumulados': round(pontos_acumulados, 1),
                'pontos_corrida': round(pontos_corrida - penalidade, 1)
            })
        
        return evolucao