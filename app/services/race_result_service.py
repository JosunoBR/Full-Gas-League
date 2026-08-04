from app.models import db, Race, RaceResult, PilotProfile, Team
from app.services.scoring_service import ScoringService

class RaceResultService:
    """
    Serviço para gerenciar a lógica de salvamento e cálculo de resultados de corrida.
    """

    @classmethod
    def _get_pilot_team_for_race(cls, pilot, race):
        """
        Busca a equipe do piloto para a corrida.
        1. Verifica equipe titular (pilot.teams)
        2. Se não encontrar, verifica equipe reserva (pilot.reserve_teams)
        3. Caso contrário, retorna None.
        """
        if not pilot:
            return None
        team = next(
            (t for t in pilot.teams if t.season_id == race.season_id and t.grid_id == race.grid_id),
            None
        )
        if team:
            return team
        if hasattr(pilot, 'reserve_teams') and pilot.reserve_teams:
            team = next(
                (t for t in pilot.reserve_teams if t.season_id == race.season_id and t.grid_id == race.grid_id),
                None
            )
            if team:
                return team
        return None

    @classmethod
    def save_race_results_by_position(cls, race_id, form_data):
        """
        Salva os resultados da corrida a partir de um formulário organizado por posição.
        Aplica a Regra Desportiva: ajusta sequencialmente as posições dos pilotos válidos,
        promovendo quem ficou atrás de desclassificados (DSQ), e reposiciona os DSQ ao final.
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
        RaceResult.query.filter_by(race_id=race_id).delete()

        processed_pilots = set()
        raw_entries = []

        # 2. Coleta a classificação da corrida enviada pelo formulário
        for i in range(1, grid_size + 1):
            pilot_id_str = form_data.get(f'pos_{i}_pilot')
            if not pilot_id_str:
                continue # Posição vazia, pula para a próxima

            pilot_id = int(pilot_id_str)

            # Validação para impedir que o mesmo piloto seja salvo em duas posições
            if pilot_id in processed_pilots:
                raise ValueError(f"Piloto com ID {pilot_id} selecionado em mais de uma posição.")
            processed_pilots.add(pilot_id)

            pilot = PilotProfile.query.get(pilot_id)
            team_for_this_race = cls._get_pilot_team_for_race(pilot, race)

            grid_start = form_data.get(f'pos_{i}_grid_largada')
            grid_start_int = int(grid_start) if (grid_start and grid_start.isdigit()) else None
            tempo_tot = (form_data.get(f'pos_{i}_tempo_total') or '').strip() or None
            best_lap = (form_data.get(f'pos_{i}_melhor_volta') or '').strip() or None
            qualy_t = (form_data.get(f'pos_{i}_tempo_qualy') or '').strip() or None
            pits_cnt = form_data.get(f'pos_{i}_pit_stops')
            pits_cnt_int = int(pits_cnt) if (pits_cnt and pits_cnt.isdigit()) else 0
            stints = (form_data.get(f'pos_{i}_pneus_stints') or '').strip() or None
            pens = (form_data.get(f'pos_{i}_penalidades_texto') or '').strip() or None

            is_dsq = form_data.get(f'pos_{i}_dsq') == 'on'
            is_dnf = form_data.get(f'pos_{i}_dnf') == 'on'

            raw_entries.append({
                'pilot_id': pilot_id,
                'team_id': team_for_this_race.id if team_for_this_race else None,
                'grid_largada': grid_start_int,
                'tempo_total': tempo_tot,
                'melhor_volta': best_lap,
                'tempo_qualy': qualy_t,
                'pit_stops': pits_cnt_int,
                'pneus_stints': stints,
                'penalidades_texto': pens,
                'dnf': is_dnf,
                'dsq': is_dsq,
                'volta_rapida': form_data.get(f'pos_{i}_vr') == 'on',
                'piloto_do_dia': form_data.get(f'pos_{i}_dotd') == 'on',
                'piloto_torcida': form_data.get(f'pos_{i}_fan') == 'on',
            })

        # Separate into valid finishers and DSQ entries to re-rank according to sporting rules
        valid_entries = [e for e in raw_entries if not e['dsq']]
        dsq_entries = [e for e in raw_entries if e['dsq']]

        # Assign continuous, adjusted positions to valid finishers (1º, 2º, 3º...)
        final_ordered_entries = []
        for index, entry in enumerate(valid_entries, start=1):
            entry['posicao'] = index
            final_ordered_entries.append(entry)

        # Place DSQ entries after valid finishers
        start_dsq_pos = len(valid_entries) + 1
        for index, entry in enumerate(dsq_entries, start=start_dsq_pos):
            entry['posicao'] = index
            final_ordered_entries.append(entry)

        # Create and save RaceResult entries
        for entry in final_ordered_entries:
            new_result = RaceResult(
                race_id=race.id,
                pilot_id=entry['pilot_id'],
                team_id=entry['team_id'],
                posicao=entry['posicao'],
                status_presenca='OK',
                dnf=entry['dnf'],
                dsq=entry['dsq'],
                volta_rapida=entry['volta_rapida'],
                piloto_do_dia=entry['piloto_do_dia'],
                piloto_torcida=entry['piloto_torcida'],
                grid_largada=entry['grid_largada'],
                tempo_total=entry['tempo_total'],
                melhor_volta=entry['melhor_volta'],
                tempo_qualy=entry['tempo_qualy'],
                pit_stops=entry['pit_stops'],
                pneus_stints=entry['pneus_stints'],
                penalidades_texto=entry['penalidades_texto']
            )

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

                pilot = PilotProfile.query.get(pilot_id)
                team_for_this_race = cls._get_pilot_team_for_race(pilot, race)

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