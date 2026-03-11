from app.models import Race, RaceResult
from sqlalchemy.orm import joinedload
from app.models import db

class CalendarService:
    @staticmethod
    def build_season_calendar(season_id, grid_configs):
        """
        Busca todas as corridas da temporada e as organiza por grid.
        OTIMIZAÇÃO: NÃO carrega os resultados (súmulas) aqui. Carrega apenas metadados da corrida.
        Retorna o calendário leve e a lista de objetos básicos.
        """
        # Query leve: Apenas dados da tabela Race
        all_races = Race.query.filter_by(season_id=season_id).order_by(Race.data_corrida).all()
        
        calendar = {g['id']: [] for g in grid_configs}
        
        for r in all_races:
            if r.grid_id in calendar:
                r_dict = r.to_dict()
                # FIX: Garante que a data esteja presente explicitamente no dicionário
                r_dict['data_corrida'] = r.data_corrida
                # Otimização: Não carrega 'results' aqui. O modal deve buscar via API /api/race/<id>/results

                calendar[r.grid_id].append(r_dict)
        
        return calendar, all_races

    @staticmethod
    def get_race_summary(race_id):
        """
        Busca os detalhes completos de UMA ÚNICA corrida.
        Usado para o modal de súmula e para os cards de 'Última Corrida'.
        """
        race = (
            Race.query.options(
                joinedload(Race.results).joinedload(RaceResult.pilot),
                joinedload(Race.results).joinedload(RaceResult.team_snapshot),
            )
            .filter_by(id=race_id)
            .first()
        )

        if not race:
            return None

        # Monta dicionário "leve" e totalmente serializável, sem usar Race.to_dict()
        r_dict = {
            "id": race.id,
            "nome_gp": race.nome_gp,
            "pista": race.pista,
            "grid": race.grid,
            "status": race.status,
            "tipo": race.tipo_etapa,
            # estes dois campos são tratados na camada de API
            "data_corrida": race.data_corrida,
            "data_formatada": race.data_corrida.strftime('%d/%m/%Y') if race.data_corrida else 'TBA',
        }

        if race.status == 'Concluida':
            # Ordena resultados colocando sem posição no final
            sorted_results = sorted(
                race.results,
                key=lambda x: x.posicao if x.posicao is not None else 999,
            )

            clean_results = []
            for res in sorted_results:
                pilot_data = (
                    {"id": res.pilot.id, "nickname": res.pilot.nickname}
                    if getattr(res, "pilot", None)
                    else {"id": None, "nickname": "Piloto Removido"}
                )
                team_name = None
                if getattr(res, "team_snapshot", None):
                    # evita acessar atributos que possam não existir
                    team_name = getattr(res.team_snapshot, "nome", None) or "N/A"

                clean_results.append(
                    {
                        "posicao": res.posicao,
                        "pontos": float(res.pontos_ganhos or 0),
                        "pilot": pilot_data,
                        "team": {
                            "id": res.team_id,
                            "nome": team_name or "N/A",
                        },
                        "dnf": bool(res.dnf),
                        "dsq": bool(res.dsq),
                        "ausencia": bool(getattr(res, "ausencia", False)),
                        "vr": bool(res.volta_rapida),
                        "dotd": bool(res.piloto_do_dia),
                    }
                )

            r_dict["results"] = clean_results
        else:
            r_dict["results"] = []

        return r_dict

    @staticmethod
    def find_last_races(calendar_data, grid_configs):
        """
        Identifica a última corrida concluída no calendário leve e busca seus detalhes completos
        apenas para exibição nos cards de destaque da Home.
        """
        last_races = {g['id']: None for g in grid_configs}
        
        for g_id in last_races:
            # Encontra o ID da última corrida concluída na lista leve
            concluidas = [r for r in calendar_data.get(g_id, []) if r['status'] == 'Concluida']
            if concluidas:
                last_race_light = concluidas[-1]
                # Busca o detalhe completo apenas desta corrida (Query pontual)
                full_details = CalendarService.get_race_summary(last_race_light['id'])
                last_races[g_id] = full_details
                
        return last_races