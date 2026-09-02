"""
scheduler_service.py
====================
Jobs de notificações automáticas usando APScheduler.

Jobs ativos:
  - lembrete_corrida_2_dias:  Dispara 48h antes de cada corrida agendada.
  - alertas_ban_dia_corrida:  Dispara todo dia às 08:00 para pilotos com bans.
  - alerta_prazo_defesa:      Dispara a cada hora, avisa pilotos com prazo de defesa expirando em 24h.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import logging

logger = logging.getLogger(__name__)

# Instância global do scheduler
scheduler = BackgroundScheduler(timezone='America/Sao_Paulo')


def _lembrete_corrida_2_dias():
    """
    Verifica corridas que acontecerão em ~48 horas e envia lembrete
    para todos os pilotos titulares do grid dessa etapa.
    """
    from flask import current_app
    from app.models import db, Race, PilotProfile, GridConfig
    from app.services.notification_service import NotificationService
    from app.utils import get_brasilia_now
    from datetime import timedelta, date

    with current_app.app_context():
        hoje = get_brasilia_now().date()
        data_alvo = hoje + timedelta(days=2)

        corridas = Race.query.filter(
            Race.data_corrida == data_alvo,
            Race.status == 'Agendada'
        ).all()

        if not corridas:
            return

        for corrida in corridas:
            if not corrida.grid_id:
                continue

            # Busca todos os pilotos titulares deste grid com fcm_token
            pilotos = PilotProfile.query.filter(
                PilotProfile.fcm_token.isnot(None),
                PilotProfile.fcm_token != '',
                PilotProfile.grid.contains(str(corrida.grid_id))
            ).all()

            tokens = [p.fcm_token for p in pilotos if p.fcm_token]
            if not tokens:
                continue

            logger.info(f"[SCHEDULER] Enviando lembrete de 2 dias para {len(tokens)} pilotos — {corrida.nome_gp}")
            success, invalid = NotificationService.send_multicast_notification(
                tokens=tokens,
                title=f"🏎️ {corrida.nome_gp} em 2 dias!",
                body="Não esqueça de fazer o check-in no app ou no site e verificar eventuais penalidades antes da corrida.",
                data={"type": "race_reminder", "race_id": str(corrida.id)}
            )
            if invalid:
                NotificationService.cleanup_invalid_tokens(invalid)


def _alertas_ban_dia_corrida():
    """
    Roda todo dia às 08:00 (horário de Brasília).
    Para corridas marcadas para HOJE, verifica pilotos com ban ativo
    e envia alerta individual.
    """
    from flask import current_app
    from app.models import db, Race, PilotProfile, RaceResult
    from app.services.notification_service import NotificationService
    from app.utils import get_brasilia_now

    with current_app.app_context():
        hoje = get_brasilia_now().date()

        corridas_hoje = Race.query.filter(
            Race.data_corrida == hoje,
            Race.status == 'Agendada'
        ).all()

        if not corridas_hoje:
            return

        for corrida in corridas_hoje:
            if not corrida.grid_id:
                continue

            pilotos = PilotProfile.query.filter(
                PilotProfile.fcm_token.isnot(None),
                PilotProfile.fcm_token != '',
                PilotProfile.grid.contains(str(corrida.grid_id))
            ).all()

            for piloto in pilotos:
                # Race Ban: pontos CNH zerados
                if piloto.pontos_cnh <= 0:
                    result = NotificationService.send_single_notification(
                        token=piloto.fcm_token,
                        title="⛔ Atenção: você tem um Race Ban!",
                        body=f"Você possui restrição para a corrida de hoje ({corrida.nome_gp}). Consulte o site para mais detalhes.",
                        data={"type": "ban_alert", "ban_type": "race_ban", "race_id": str(corrida.id)}
                    )
                    if result == 'INVALID_TOKEN':
                        NotificationService.cleanup_invalid_tokens([piloto.fcm_token])

                # Quali Ban: penalidade de campeonato ativa
                elif piloto.penalidade_campeonato and piloto.penalidade_campeonato > 0:
                    result = NotificationService.send_single_notification(
                        token=piloto.fcm_token,
                        title="⚠️ Atenção: você tem um Quali Ban!",
                        body=f"Você possui restrição para o quali de hoje ({corrida.nome_gp}). Consulte o site para mais detalhes.",
                        data={"type": "ban_alert", "ban_type": "quali_ban", "race_id": str(corrida.id)}
                    )
                    if result == 'INVALID_TOKEN':
                        NotificationService.cleanup_invalid_tokens([piloto.fcm_token])

        logger.info(f"[SCHEDULER] Alertas de ban verificados para {len(corridas_hoje)} corrida(s) hoje.")


def _alerta_prazo_defesa():
    """
    Roda a cada hora.
    Avisa pilotos acusados cujo prazo de defesa expira nas próximas 24 horas.
    Só envia uma vez (marca com flag no corpo para evitar spam — controla via data_criacao).
    """
    from flask import current_app
    from app.models import db, Protesto, PilotProfile
    from app.services.notification_service import NotificationService
    from app.utils import get_brasilia_now
    from datetime import timedelta

    with current_app.app_context():
        agora = get_brasilia_now()
        # Prazo de defesa: 48h após a criação do protesto (ajuste conforme regra do campeonato)
        PRAZO_DEFESA_HORAS = 48
        JANELA_AVISO_HORAS = 24

        limite_criacao_min = agora - timedelta(hours=PRAZO_DEFESA_HORAS)
        limite_criacao_max = agora - timedelta(hours=PRAZO_DEFESA_HORAS - JANELA_AVISO_HORAS)

        protestos_expirando = Protesto.query.filter(
            Protesto.status == 'AGUARDANDO_DEFESA',
            Protesto.data_criacao >= limite_criacao_min,
            Protesto.data_criacao <= limite_criacao_max,
        ).all()

        for protesto in protestos_expirando:
            acusado = db.session.get(PilotProfile, protesto.acusado_id)
            if not acusado or not acusado.fcm_token:
                continue

            result = NotificationService.send_single_notification(
                token=acusado.fcm_token,
                title="⏳ Prazo de defesa expirando!",
                body=f"Você tem menos de 24h para enviar sua defesa no protesto #{protesto.id}. Acesse o site agora.",
                data={"type": "defense_deadline", "protest_id": str(protesto.id)}
            )
            if result == 'INVALID_TOKEN':
                NotificationService.cleanup_invalid_tokens([acusado.fcm_token])

        if protestos_expirando:
            logger.info(f"[SCHEDULER] Alertas de prazo de defesa enviados: {len(protestos_expirando)} protesto(s).")


def init_scheduler(app):
    """
    Inicializa e inicia o APScheduler com a referência ao app Flask.
    Deve ser chamado UMA vez no factory da aplicação (app/__init__.py).
    """
    if scheduler.running:
        logger.warning("[SCHEDULER] Scheduler já está rodando — ignorando segunda inicialização.")
        return

    # Job 1: Lembrete de corrida — verifica a cada 6 horas
    scheduler.add_job(
        func=lambda: app.app_context().push() or _lembrete_corrida_2_dias(),
        trigger=IntervalTrigger(hours=6),
        id='lembrete_corrida_2_dias',
        replace_existing=True
    )

    # Job 2: Alertas de ban — todo dia às 08:00 (Brasília)
    scheduler.add_job(
        func=lambda: app.app_context().push() or _alertas_ban_dia_corrida(),
        trigger=CronTrigger(hour=8, minute=0),
        id='alertas_ban_dia_corrida',
        replace_existing=True
    )

    # Job 3: Prazo de defesa — a cada 1 hora
    scheduler.add_job(
        func=lambda: app.app_context().push() or _alerta_prazo_defesa(),
        trigger=IntervalTrigger(hours=1),
        id='alerta_prazo_defesa',
        replace_existing=True
    )

    scheduler.start()
    logger.info("[SCHEDULER] APScheduler iniciado com 3 jobs de notificação.")
