from app.models import db, Race, RaceResult, PilotProfile, Team, HomeCache
from app.utils import PONTUACAO_20, PONTUACAO_22

class RaceResultService:
    @staticmethod
    def save_race_results(race_id, form_data):
        """
        Processa e salva os resultados de uma corrida a partir de um formulário.
        Centraliza toda a lógica de pontuação, bônus e status de presença.
        """
        race = Race.query.get_or_404(race_id)
        if not race.season.ativa:
            raise ValueError('Temporada encerrada.')

        # Estornar resultados anteriores para evitar duplicidade
        team_snapshot = {r.pilot_id: r.team_id for r in RaceResult.query.filter_by(race_id=race.id).all()}
        RaceResult.query.filter_by(race_id=race.id).delete()

        # Define a tabela de pontuação a ser usada
        pontuacao_ativa = PONTUACAO_22 if race.grid_config and race.grid_config.vagas > 20 else PONTUACAO_20

        # 1. PROCESSAR TITULARES
        titulares_ids = form_data.getlist('titular_id')
        for pid in titulares_ids:
            pid_int = int(pid)
            status_presenca = (form_data.get(f'status_{pid}') or '').strip().upper()
            if not status_presenca:
                raise ValueError(f'Faltou preencher status de presença para o titular ID {pid_int}.')

            equipe_id = team_snapshot.get(pid_int)
            if equipe_id is None:
                form_team_raw = (form_data.get(f'titular_team_{pid_int}') or '').strip()
                if form_team_raw.isdigit():
                    equipe_id = int(form_team_raw)
                else:
                    piloto = PilotProfile.query.get(pid_int)
                    raise ValueError(f'Não foi possível determinar a equipe para o titular {piloto.nickname if piloto else f"ID {pid_int}"}.')

            if status_presenca == 'OK':
                posicao = int(form_data.get(f'pos_{pid}') or 0)
                dnf = form_data.get(f'dnf_{pid}') == 'on'
                dsq = form_data.get(f'dsq_{pid}') == 'on'
                vr = form_data.get(f'vr_{pid}') == 'on'
                dotd = form_data.get(f'dotd_{pid}') == 'on'
                fan = form_data.get(f'fan_{pid}') == 'on'

                pontos = RaceResultService._calculate_points(
                    posicao, pontuacao_ativa, race.tipo_etapa, dnf, dsq, vr, dotd, fan
                )

                db.session.add(RaceResult(
                    race_id=race.id, pilot_id=pid_int, team_id=equipe_id,
                    posicao=posicao, pontos_ganhos=pontos, status_presenca='OK',
                    dnf=dnf, dsq=dsq, volta_rapida=vr, piloto_do_dia=dotd, piloto_torcida=fan
                ))
            else: # FJ ou FNJ
                db.session.add(RaceResult(
                    race_id=race.id, pilot_id=pid_int, team_id=equipe_id,
                    posicao=0, pontos_ganhos=0, status_presenca=status_presenca, ausencia=status_presenca
                ))

        # 2. PROCESSAR RESERVAS
        reserva_pids = form_data.getlist('reserva_pilot')
        reserva_teams = form_data.getlist('reserva_team')
        reserva_pos = form_data.getlist('reserva_pos')

        for i, r_pid in enumerate(reserva_pids):
            if not r_pid or not r_pid.strip():
                continue

            r_pid_int = int(r_pid)
            r_team_val = reserva_teams[i] if i < len(reserva_teams) else None
            if not r_team_val or not r_team_val.strip():
                raise ValueError(f'É obrigatório selecionar uma equipe para o piloto reserva (Linha {i+1}).')

            r_team_id = int(r_team_val)
            r_team_obj = Team.query.get(r_team_id)
            if not r_team_obj or r_team_obj.grid_id != race.grid_id:
                raise ValueError(f'Equipe inválida para o grid desta corrida (Linha {i+1}).')

            r_pos_val = reserva_pos[i] if i < len(reserva_pos) else 0
            r_pos = int(r_pos_val) if r_pos_val else 0

            r_dnf = form_data.get(f'reserva_dnf_{i}') == 'on'
            r_dsq = form_data.get(f'reserva_dsq_{i}') == 'on'
            r_vr = form_data.get(f'reserva_vr_{i}') == 'on'
            r_dotd = form_data.get(f'reserva_dotd_{i}') == 'on'
            r_fan = form_data.get(f'reserva_fan_{i}') == 'on'

            r_pontos = RaceResultService._calculate_points(
                r_pos, pontuacao_ativa, race.tipo_etapa, r_dnf, r_dsq, r_vr, r_dotd, r_fan
            )

            db.session.add(RaceResult(
                race_id=race.id, pilot_id=r_pid_int, team_id=r_team_id,
                posicao=r_pos, pontos_ganhos=r_pontos, status_presenca='OK',
                dnf=r_dnf, dsq=r_dsq, volta_rapida=r_vr, piloto_do_dia=r_dotd, piloto_torcida=r_fan
            ))

        # 3. FINALIZAR
        race.status = 'Concluida'
        HomeCache.query.filter_by(season_id=race.season_id).delete()
        db.session.commit()

    @staticmethod
    def _calculate_points(posicao, pontuacao_tabela, tipo_etapa, dnf, dsq, vr, dotd, fan):
        """
        Sub-rotina para calcular os pontos de um único resultado.
        """
        if dsq:
            return 0.0

        pontos = 0.0
        if not dnf and posicao > 0:
            pontos = float(pontuacao_tabela.get(posicao, 0))

        if tipo_etapa == 'SPRINT':
            pontos *= 0.5
        elif tipo_etapa == 'FINAL':
            pontos *= 2.0

        if vr and not dnf:
            pontos += 1.0
        if dotd:
            pontos += 1.0
        if fan:
            pontos += 1.0

        return pontos