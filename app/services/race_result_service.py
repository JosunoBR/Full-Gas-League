from app.models import db, Race, RaceResult, PilotProfile, Team
from app.services.scoring_service import ScoringService

class RaceResultService:
    """
    Serviço para gerenciar a lógica de salvamento e cálculo de resultados de corrida.
    """

    @classmethod
    def save_race_results_by_position(cls, race_id, form_data):
        """
        Salva os resultados da corrida a partir de um formulário organizado por posição.
        Esta função é o "tradutor" entre o novo formulário e o banco de dados.
        """
        race = Race.query.get_or_404(race_id)
        
        # Determina o tamanho do grid para os loops
        grid_size = race.grid_config.vagas if race.grid_config and race.grid_config.vagas else 22

        # 0. Processa a Pole Position e Metadados do GP/Lobby
        pole_pilot_id = form_data.get('pole_pilot_id')
        race.pole_pilot_id = int(pole_pilot_id) if (pole_pilot_id and pole_pilot_id.isdigit()) else None
        race.pole_time = (form_data.get('pole_time') or '').strip() or None

        race.sc_vsc_info = (form_data.get('sc_vsc_info') or '').strip() or None
        race.clima_temp = (form_data.get('clima_temp') or '').strip() or None
        tot_v = form_data.get('total_voltas')
        race.total_voltas = int(tot_v) if (tot_v and tot_v.isdigit()) else None
        race.lobby_settings_json = form_data.get('lobby_settings_json') or None

        # 1. Limpa todos os resultados antigos desta corrida para evitar duplicatas.
        #    Isso torna a operação de salvar idempotente (o resultado final é o mesmo, não importa quantas vezes você salve).
        RaceResult.query.filter_by(race_id=race_id).delete()

        processed_pilots = set()

        # 2. Processa a classificação da corrida (pilotos que pontuaram/correram)
        for i in range(1, grid_size + 1):
            pilot_id_str = form_data.get(f'pos_{i}_pilot')
            if not pilot_id_str:
                continue # Posição vazia, pula para a próxima

            pilot_id = int(pilot_id_str)

            # Validação para impedir que o mesmo piloto seja salvo em duas posições
            if pilot_id in processed_pilots:
                raise ValueError(f"Piloto com ID {pilot_id} selecionado em mais de uma posição.")
            processed_pilots.add(pilot_id)

            # Busca a equipe do piloto para esta temporada/grid
            pilot = PilotProfile.query.get(pilot_id)
            team_for_this_race = next(
                (t for t in pilot.teams if t.season_id == race.season_id and t.grid_id == race.grid_id),
                None
            )

            grid_start = form_data.get(f'pos_{i}_grid_largada')
            grid_start_int = int(grid_start) if (grid_start and grid_start.isdigit()) else None
            tempo_tot = (form_data.get(f'pos_{i}_tempo_total') or '').strip() or None
            best_lap = (form_data.get(f'pos_{i}_melhor_volta') or '').strip() or None
            qualy_t = (form_data.get(f'pos_{i}_tempo_qualy') or '').strip() or None
            pits_cnt = form_data.get(f'pos_{i}_pit_stops')
            pits_cnt_int = int(pits_cnt) if (pits_cnt and pits_cnt.isdigit()) else 0
            stints = (form_data.get(f'pos_{i}_pneus_stints') or '').strip() or None
            pens = (form_data.get(f'pos_{i}_penalidades_texto') or '').strip() or None

            # Cria o novo registro de resultado
            new_result = RaceResult(
                race_id=race.id,
                pilot_id=pilot_id,
                team_id=team_for_this_race.id if team_for_this_race else None,
                posicao=i,
                status_presenca='OK',
                dnf=form_data.get(f'pos_{i}_dnf') == 'on',
                dsq=form_data.get(f'pos_{i}_dsq') == 'on',
                volta_rapida=form_data.get(f'pos_{i}_vr') == 'on',
                piloto_do_dia=form_data.get(f'pos_{i}_dotd') == 'on',
                piloto_torcida=form_data.get(f'pos_{i}_fan') == 'on',
                grid_largada=grid_start_int,
                tempo_total=tempo_tot,
                melhor_volta=best_lap,
                tempo_qualy=qualy_t,
                pit_stops=pits_cnt_int,
                pneus_stints=stints,
                penalidades_texto=pens
            )

            # Usa o ScoringService para calcular os pontos, mantendo a lógica centralizada
            new_result.pontos_ganhos = ScoringService.calculate_race_points(new_result, grid_size)
            
            db.session.add(new_result)

        # 3. Processa os pilotos ausentes (FJ/FNJ)
        for key, status in form_data.items():
            if key.startswith('status_ausente_'):
                if status not in ['FJ', 'FNJ']:
                    continue # Ignora se o status for 'OK' (Não Correu)

                pilot_id = int(key.split('_')[-1])

                # Garante que um piloto que correu não seja marcado como ausente
                if pilot_id in processed_pilots:
                    continue

                # Busca a equipe do piloto (mesma lógica de antes)
                pilot = PilotProfile.query.get(pilot_id)
                team_for_this_race = next(
                    (t for t in pilot.teams if t.season_id == race.season_id and t.grid_id == race.grid_id),
                    None
                )

                # Cria um registro para a ausência
                absent_result = RaceResult(
                    race_id=race.id,
                    pilot_id=pilot_id,
                    team_id=team_for_this_race.id if team_for_this_race else None,
                    posicao=0, # Posição 0 para ausentes
                    status_presenca=status,
                    pontos_ganhos=0 # Ausentes não pontuam
                )
                db.session.add(absent_result)

        # 4. Atualiza o status da corrida para 'Concluida' quando resultados são salvos
        if processed_pilots:
            race.status = 'Concluida'

        # 5. Invalida o cache da home para refletir os novos resultados
        from app.models import HomeCache
        HomeCache.query.filter_by(season_id=race.season_id).delete()

        # 6. Confirma todas as alterações no Banco de Dados (Commit)
        db.session.commit()
        return True

    # A função antiga pode ser mantida para referência ou removida.
    # @classmethod
    # def save_race_results(cls, race_id, form_data): ...