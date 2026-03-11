from app.models import Race

class CalendarService:
    @staticmethod
    def build_season_calendar(season_id, grid_configs):
        """
        Busca todas as corridas da temporada e as organiza por grid.
        Retorna o calendário em formato de dicionário e a lista de objetos do banco.
        """
        all_races = Race.query.filter_by(season_id=season_id).order_by(Race.data_corrida).all()
        calendar = {g['id']: [] for g in grid_configs}
        
        for r in all_races:
            if r.grid_id in calendar:
                r_dict = r.to_dict()
                # FIX: Garante que a data esteja presente explicitamente no dicionário
                r_dict['data'] = r.data_corrida
                r_dict['data_corrida'] = r.data_corrida
                calendar[r.grid_id].append(r_dict)
        
        return calendar, all_races

    @staticmethod
    def find_last_races(calendar_data, all_races_db, grid_configs):
        """
        Encontra a última corrida concluída para cada grid e serializa seus resultados.
        """
        last_races = {g['id']: None for g in grid_configs}
        
        for g_id in last_races:
            concluidas = [r for r in calendar_data.get(g_id, []) if r['status'] == 'Concluida']
            if concluidas:
                last_race_dict = concluidas[-1]
                last_race_obj = next((r for r in all_races_db if r.id == last_race_dict['id']), None)
                if last_race_obj:
                    # Serialização manual para garantir a estrutura correta para o HTML
                    last_races[g_id] = {
                        'id': last_race_obj.id, 
                        'nome_gp': last_race_obj.nome_gp, 
                        'pista': last_race_obj.pista,
                        'data': last_race_obj.data_corrida, # FIX: Adicionado campo data que faltava
                        'data_corrida': last_race_obj.data_corrida,
                        'results': [{'posicao': r.posicao, 'pontos': r.pontos_ganhos, 'pilot': {'nickname': r.pilot.nickname}, 'team': {'nome': r.team_snapshot.nome if r.team_snapshot else 'N/A'}, 'dnf': r.dnf, 'dsq': r.dsq} for r in last_race_obj.results]
                    }
        return last_races