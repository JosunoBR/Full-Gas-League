from app.models import db, Protesto, Race, PilotProfile, Team, GridConfig
from app.services.scoring_service import ScoringService
from app.utils import grid_matches

class StatsService:
    @staticmethod
    def get_grid_statistics(season_id, grid_id):
        """
        Gera estatísticas detalhadas (Starts, Wins, Podiums, etc.) para todos os pilotos
        de um determinado grid em uma temporada.
        """
        grid_cfg = db.session.get(GridConfig, grid_id)
        if not grid_cfg:
            return []

        # 1. Carrega punições para cálculo de pontos líquidos
        punicoes_temporada = Protesto.query.join(Race).filter(
            Protesto.status == 'CONCLUIDO',
            Race.season_id == season_id,
            Race.grid_id == grid_id,
        ).all()

        punicoes_by_pilot = {}
        for prot in punicoes_temporada:
            punicoes_by_pilot.setdefault(prot.acusado_id, []).append(prot)

        # 2. Carrega dados básicos
        pilotos = PilotProfile.query.all() # Otimização futura: filtrar apenas ativos
        all_season_teams = Team.query.filter_by(season_id=season_id).all()

        stats_rows = []

        for p in pilotos:
            # Resultados desta temporada
            resultados_season = [r for r in p.race_results if r.race.season_id == season_id]
            
            # Identifica equipes do piloto na temporada
            teams_season = [t for t in all_season_teams if any(pilot.id == p.id for pilot in t.pilots)]
            reserves_season = [t for t in all_season_teams if any(pilot.id == p.id for pilot in t.reserves)]
            all_my_teams = teams_season + reserves_season

            # Verifica se o piloto participou deste grid (via equipe ou reserva)
            grids_participados_ids = set()
            for t in all_my_teams:
                if t.grid_id:
                    grids_participados_ids.add(t.grid_id)
            
            if grid_id not in grids_participados_ids:
                continue

            # Filtra resultados específicos deste grid
            res_no_grid = [r for r in resultados_season if grid_matches(r.race, grid_cfg)]
            
            # Se não correu, ignora (a menos que tenha equipe e pontos manuais, mas geralmente ignora)
            if not res_no_grid and not any(t.grid_id == grid_id for t in teams_season):
                continue

            my_punicoes = punicoes_by_pilot.get(p.id, [])
            my_punicoes_grid = [pun for pun in my_punicoes if pun.grid_id == grid_id]

            # Pontos totais (já desconta punições via ScoringService)
            pontos_totais = ScoringService.calculate_pilot_total_points(p.id, season_id, grid_id)

            # Time principal do piloto neste grid
            main_team = next((t for t in teams_season if t.grid_id == grid_id), None)

            stats_rows.append({
                'piloto': p,
                'team': main_team,
                'starts': sum(1 for r in res_no_grid if r.status_presenca == 'OK'),
                'wins': sum(1 for r in res_no_grid if r.posicao == 1 and not r.dsq),
                'podiums': sum(1 for r in res_no_grid if r.posicao in (1, 2, 3) and not r.dsq),
                'dnfs': sum(1 for r in res_no_grid if r.dnf),
                'fastest_laps': sum(1 for r in res_no_grid if r.volta_rapida),
                'points': pontos_totais,
                'punicoes': my_punicoes_grid,
            })

        # Ordenação: Pontos (Desc) -> Vitórias (Desc)
        stats_rows.sort(key=lambda x: (x['points'], x['wins']), reverse=True)
        
        return stats_rows

    @staticmethod
    def get_all_time_statistics(pilot_id=None):
        """
        Gera estatísticas de carreira (Geral) para todos os pilotos com histórico.
        Ignora filtros de temporada e grid. Remove pontos conforme solicitado.
        Se pilot_id for informado, retorna apenas estatísticas daquele piloto.
        """
        query = PilotProfile.query
        if pilot_id:
            query = query.filter(PilotProfile.id == pilot_id)
        pilotos = query.all()
        stats_rows = []

        for p in pilotos:
            # Pega todos os resultados da carreira (sem filtro de season/grid)
            results = p.race_results
            
            # Conta participações reais (Status OK)
            starts = sum(1 for r in results if r.status_presenca == 'OK')
            
            if starts == 0:
                continue

            wins = sum(1 for r in results if r.posicao == 1 and not r.dsq)
            podiums = sum(1 for r in results if r.posicao in (1, 2, 3) and not r.dsq)
            dnfs = sum(1 for r in results if r.dnf)
            fastest_laps = sum(1 for r in results if r.volta_rapida)

            # Tenta identificar a equipe ATUAL (da temporada mais recente) apenas para exibir no card
            current_team = None
            if p.teams:
                current_team = sorted(p.teams, key=lambda t: t.season_id or 0, reverse=True)[0]

            stats_rows.append({
                'piloto': p,
                'team': current_team,
                'starts': starts,
                'wins': wins,
                'podiums': podiums,
                'dnfs': dnfs,
                'fastest_laps': fastest_laps,
                'points': 0,  # Pontos zerados/ignorados no modo carreira
                'punicoes': []
            })

        # Ordenação por Vitórias -> Pódios -> Starts
        stats_rows.sort(key=lambda x: (x['wins'], x['podiums'], x['starts']), reverse=True)
        
        return stats_rows