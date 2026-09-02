try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False

import logging

logger = logging.getLogger(__name__)

# Instância global do scheduler (apenas se a biblioteca estiver instalada)
scheduler = BackgroundScheduler(timezone='America/Sao_Paulo') if HAS_APSCHEDULER else None


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


def notificar_transmissao_corrida_dia(corrida_especifica_id=None, youtube_url_custom=None, titulo_custom=None, mensagem_custom=None):
    """
    Envia notificação push para TODOS os pilotos anunciando as corridas de hoje
    e convidando para assistir a transmissão ao vivo no canal oficial do YouTube.
    Pode ser acionado automaticamente pelo APScheduler ou manualmente pelo painel admin.

    :param corrida_especifica_id: (Opcional) ID de uma corrida específica para focar o anúncio.
    :param youtube_url_custom: (Opcional) Link direto da live no YouTube.
    :param titulo_custom: (Opcional) Título personalizado da notificação.
    :param mensagem_custom: (Opcional) Mensagem personalizada da notificação.
    :return: (sucesso: bool, mensagem: str, total_enviados: int)
    """
    from flask import current_app
    from app.models import Race, PilotProfile
    from app.services.notification_service import NotificationService
    from app.utils import get_brasilia_now

    hoje = get_brasilia_now().date()

    if corrida_especifica_id:
        corridas = Race.query.filter(Race.id == corrida_especifica_id).all()
    else:
        corridas = Race.query.filter(
            Race.data_corrida == hoje,
            Race.status == 'Agendada'
        ).all()

    if not corridas:
        return False, "Nenhuma corrida agendada encontrada para o dia de hoje.", 0

    # Coleta os nomes dos GPs e Grids envolvidos
    nomes_gps = []
    grids_nomes = []
    for c in corridas:
        if c.nome_gp and c.nome_gp not in nomes_gps:
            nomes_gps.append(c.nome_gp)
        nome_grid = c.grid_config.nome if getattr(c, 'grid_config', None) else c.grid
        if nome_grid and nome_grid not in grids_nomes:
            grids_nomes.append(nome_grid)

    gp_txt = " / ".join(nomes_gps) if nomes_gps else "Grande Prêmio"
    grids_txt = ", ".join(grids_nomes) if grids_nomes else "todos os grids"

    default_youtube = current_app.config.get('YOUTUBE_URL', 'https://www.youtube.com/@FullGasLeagueF1Oficial')
    youtube_url = (youtube_url_custom.strip() if youtube_url_custom and youtube_url_custom.strip() else default_youtube)

    # Monta o título e mensagem convidativa para o anúncio
    title = (
        titulo_custom.strip() if titulo_custom and titulo_custom.strip() else
        f"🔴 HOJE É DIA DE CORRIDA! | {gp_txt} 🏁"
    )
    body = (
        mensagem_custom.strip() if mensagem_custom and mensagem_custom.strip() else
        f"Hoje tem pista quente! Disputas confirmadas: {grids_txt}. "
        f"Acompanhe a transmissão oficial ao vivo no YouTube da Full Gas League!"
    )

    # Busca todos os pilotos que possuem FCM token cadastrado no app
    pilotos = PilotProfile.query.filter(
        PilotProfile.fcm_token.isnot(None),
        PilotProfile.fcm_token != ''
    ).all()

    tokens = list(set([p.fcm_token for p in pilotos if p.fcm_token]))

    if not tokens:
        return False, "Nenhum piloto com token de notificação ativo no aplicativo.", 0

    logger.info(f"[NOTIFICAÇÃO YOUTUBE] Enviando anúncio de corrida para {len(tokens)} pilotos.")

    success_count, invalid_tokens = NotificationService.send_multicast_notification(
        tokens=tokens,
        title=title,
        body=body,
        data={
            "type": "race_day",
            "url": youtube_url,
            "race_ids": ",".join(str(c.id) for c in corridas)
        }
    )

    if invalid_tokens:
        NotificationService.cleanup_invalid_tokens(invalid_tokens)

    return True, f"Anúncio de transmissão enviado com sucesso para {success_count} piloto(s)!", success_count


def _notificacao_corrida_hoje_youtube():
    """
    Disparado pelo scheduler nos horários programados para alertar todos os membros
    sobre a transmissão do dia no YouTube.
    """
    from flask import current_app
    with current_app.app_context():
        sucesso, msg, count = notificar_transmissao_corrida_dia()
        logger.info(f"[SCHEDULER YOUTUBE] {msg}")


def init_scheduler(app):
    """
    Inicializa e inicia o APScheduler com a referência ao app Flask.
    """
    if not HAS_APSCHEDULER or scheduler is None:
        logger.warning("[SCHEDULER] APScheduler não instalado. Lembretes automáticos desativados.")
        return

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

    # Job 4: Anúncio do dia de corrida (Almoço) — todo dia às 12:00 (Brasília)
    scheduler.add_job(
        func=lambda: app.app_context().push() or _notificacao_corrida_hoje_youtube(),
        trigger=CronTrigger(hour=12, minute=0),
        id='notificacao_corrida_dia_12h',
        replace_existing=True
    )

    # Job 5: Chamada para a transmissão ao vivo (Noite) — todo dia às 19:30 (Brasília)
    scheduler.add_job(
        func=lambda: app.app_context().push() or _notificacao_corrida_hoje_youtube(),
        trigger=CronTrigger(hour=19, minute=30),
        id='notificacao_corrida_dia_19h30',
        replace_existing=True
    )

    scheduler.start()
    logger.info("[SCHEDULER] APScheduler iniciado com 5 jobs de notificação.")

