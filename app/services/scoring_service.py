from sqlalchemy import func, case
from app.models import db, RaceResult, Race, Protesto, PilotProfile, Team
from app.utils import calcular_perda
from app.services.team_context import normalize_team_name

class ScoringService:
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
        
        # Soma pontos das corridas
        pontos_corridas = float(sum(r.pontos_ganhos or 0 for r in resultados))
        
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
    def build_constructors_for_home(season_id, grid_configs, canonical_teams, alias_ids_by_key):
        """
        Build constructors table by grid.
        Source of truth is race_result.team_id only.
        """
        constructors = {g.id: [] for g in grid_configs}
        stats_by_team_id = ScoringService.get_team_result_stats(season_id)

        seen = set()
        for team in canonical_teams:
            if not team.grid_id or team.grid_id not in constructors:
                continue
            key = (team.grid_id, normalize_team_name(team.nome))
            if key in seen:
                continue
            seen.add(key)

            alias_ids = alias_ids_by_key.get(key, [team.id])
            pontos = 0.0
            vitorias = 0
            for tid in alias_ids:
                s = stats_by_team_id.get(tid, {"pontos": 0.0, "vitorias": 0})
                pontos += float(s["pontos"] or 0.0)
                vitorias += int(s["vitorias"] or 0)

            constructors[team.grid_id].append({"equipe": team, "pontos": pontos, "vitorias": vitorias})

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
        - totals and pilot breakdown from race_result.team_id only
        - includes ex-drivers and reserves that raced for the team
        """
        alias_ids = ScoringService.get_team_alias_ids(team, season_id)
        if not alias_ids:
            return {"total_pontos": 0.0, "total_vitorias": 0, "stats_pilotos": []}

        query = db.session.query(
            RaceResult.pilot_id,
            func.sum(RaceResult.pontos_ganhos).label("pontos"),
            func.sum(case((((RaceResult.posicao == 1) & (RaceResult.dsq == False)), 1), else_=0)).label("vitorias"),
        ).join(Race).filter(
            Race.season_id == season_id,
            RaceResult.team_id.in_(alias_ids),
        )
        if team.grid_id:
            query = query.filter(Race.grid_id == team.grid_id)

        rows = query.group_by(RaceResult.pilot_id).all()
        if not rows:
            return {"total_pontos": 0.0, "total_vitorias": 0, "stats_pilotos": []}

        pilot_ids = [r.pilot_id for r in rows]
        pilots = PilotProfile.query.filter(PilotProfile.id.in_(pilot_ids)).all()
        pilot_by_id = {p.id: p for p in pilots}

        stats_pilotos = []
        total_pontos = 0.0
        total_vitorias = 0
        for r in rows:
            p = pilot_by_id.get(r.pilot_id)
            if not p:
                continue
            pontos = float(r.pontos or 0.0)
            vitorias = int(r.vitorias or 0)
            total_pontos += pontos
            total_vitorias += vitorias
            stats_pilotos.append({"piloto": p, "pontos": pontos, "vitorias": vitorias})

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
        punicoes_dict = {p.etapa_id: calcular_perda(p.veredito_final) for p in punicoes}
        
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