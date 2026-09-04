import os
import logging
import threading
from flask import current_app, render_template

logger = logging.getLogger(__name__)

try:
    import resend
    HAS_RESEND_LIB = True
except ImportError:
    HAS_RESEND_LIB = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class EmailService:
    """
    Serviço Centralizado de Envio de E-mails da FullGas League.
    Suporta envio transacional via API do Resend com fallback automático
    para Modo Simulação quando a chave ainda não estiver configurada.
    """

    @classmethod
    def is_configured(cls):
        """Verifica se a chave da API do Resend está configurada."""
        try:
            key = current_app.config.get('RESEND_API_KEY')
            return bool(key and str(key).strip().startswith('re_'))
        except Exception:
            return False

    @classmethod
    def _dispatch_email(cls, app, payload):
        """
        Executa o envio em background (thread separada) para evitar
        bloqueio do servidor web.
        """
        with app.app_context():
            api_key = app.config.get('RESEND_API_KEY')
            sender = app.config.get('MAIL_DEFAULT_SENDER') or 'FullGas League <contato@fullgasleague.com.br>'
            reply_to = app.config.get('MAIL_REPLY_TO') or 'fullgasracingf1@gmail.com'

            recipients = payload.get('to')
            if isinstance(recipients, str):
                recipients = [recipients]

            # Filtra e-mails válidos
            valid_recipients = [e.strip() for e in recipients if e and '@' in e]
            if not valid_recipients:
                logger.warning("[EmailService] Nenhum destinatário válido fornecido.")
                return False

            subject = payload.get('subject', 'Comunicado FullGas League')
            html_content = payload.get('html', '')

            # SE A CHAVE DO RESEND ESTIVER CONFIGURADA: DISPARO REAL
            if api_key and str(api_key).strip().startswith('re_'):
                try:
                    if HAS_RESEND_LIB:
                        resend.api_key = api_key
                        # O Resend aceita múltiplos destinatários em lote (até 50 por chamada ou individual)
                        for recipient in valid_recipients:
                            resend.Emails.send({
                                "from": sender,
                                "to": [recipient],
                                "reply_to": reply_to,
                                "subject": subject,
                                "html": html_content
                            })
                        logger.info(f"[EmailService] {len(valid_recipients)} e-mail(s) enviado(s) com sucesso via Resend SDK.")
                        return True
                    elif HAS_REQUESTS:
                        # Fallback direto via REST API caso a lib resend não esteja instalada
                        url = "https://api.resend.com/emails"
                        headers = {
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        }
                        for recipient in valid_recipients:
                            data = {
                                "from": sender,
                                "to": [recipient],
                                "reply_to": reply_to,
                                "subject": subject,
                                "html": html_content
                            }
                            requests.post(url, json=data, headers=headers, timeout=10)
                        logger.info(f"[EmailService] {len(valid_recipients)} e-mail(s) enviado(s) com sucesso via Resend API REST.")
                        return True
                except Exception as e:
                    logger.error(f"[EmailService] Erro ao enviar e-mail via Resend: {e}")
                    return False
            else:
                # MODO SIMULAÇÃO / LOG: Ideal para testes e desenvolvimento
                logger.info(
                    f"[EmailService - MODO SIMULAÇÃO] "
                    f"Para: {len(valid_recipients)} piloto(s) {valid_recipients[:3]}... | "
                    f"Assunto: '{subject}' | Remetente: {sender}"
                )
                return True

    @classmethod
    def send_async(cls, subject, recipients, html_content):
        """Dispara um e-mail assincronamente em uma thread secundária."""
        app = current_app._get_current_object()
        payload = {
            'subject': subject,
            'to': recipients,
            'html': html_content
        }
        thread = threading.Thread(target=cls._dispatch_email, args=(app, payload))
        thread.daemon = True
        thread.start()

    # =========================================================================
    # DISPARO MANUAL (PAINEL DE COMUNICAÇÃO)
    # =========================================================================
    @classmethod
    def _get_base_url(cls, app):
        """Retorna o domínio base ativo (considerando request atual ou fallback config)."""
        try:
            from flask import has_request_context, request
            if has_request_context() and request.host_url:
                return request.host_url.rstrip('/')
        except Exception:
            pass
        return app.config.get('BASE_URL') or 'https://fullgasleague.com.br'

    @classmethod
    def send_custom_broadcast(cls, subject, recipients, message_html, category="Comunicado Oficial"):
        """
        Envia comunicado criado pelo Administrador no Painel de Comunicação.
        """
        app = current_app._get_current_object()
        base_url = cls._get_base_url(app)
        full_html = render_template(
            'emails/broadcast_email.html',
            subject=subject,
            category=category,
            message_content=message_html,
            base_url=base_url,
            instagram_url=app.config.get('INSTAGRAM_URL'),
            youtube_url=app.config.get('YOUTUBE_URL')
        )
        cls.send_async(subject, recipients, full_html)
        return len(recipients)

    # =========================================================================
    # GATILHOS AUTÔNOMOS (INTEGRADOS AO SCHEDULER E PROTESTOS)
    # =========================================================================
    @classmethod
    def send_race_reminder_email(cls, race, pilots):
        """
        Autônomo (48h antes da corrida):
        Envia lembrete oficial de etapa para os pilotos do Grid.
        """
        if not pilots:
            return 0

        valid_emails = []
        for p in pilots:
            if hasattr(p, 'user') and p.user and p.user.email and '@' in p.user.email:
                valid_emails.append(p.user.email)

        if not valid_emails:
            return 0

        app = current_app._get_current_object()
        base_url = cls._get_base_url(app)
        subject = f"🏎️ FullGas League: {race.nome_gp} em 48 horas!"
        html_content = render_template(
            'emails/race_reminder_email.html',
            race=race,
            subject=subject,
            base_url=base_url,
            instagram_url=app.config.get('INSTAGRAM_URL'),
            youtube_url=app.config.get('YOUTUBE_URL')
        )
        cls.send_async(subject, valid_emails, html_content)
        logger.info(f"[EmailService Autônomo] Lembrete de corrida enviado para {len(valid_emails)} piloto(s) - {race.nome_gp}")
        return len(valid_emails)

    @classmethod
    def send_ban_alert_email(cls, pilot, race, ban_type="race_ban"):
        """
        Autônomo (Dia da corrida):
        Alerta formal de punição/banimento para o piloto afetado.
        """
        if not (pilot and pilot.user and pilot.user.email):
            return False

        app = current_app._get_current_object()
        base_url = cls._get_base_url(app)
        is_race_ban = (ban_type == "race_ban")
        subject = "⛔ Notificação Oficial: Restrição de Corrida (Race Ban)" if is_race_ban else "⚠️ Notificação Oficial: Restrição de Qualificação (Quali Ban)"

        html_content = render_template(
            'emails/ban_alert_email.html',
            pilot=pilot,
            race=race,
            ban_type=ban_type,
            subject=subject,
            base_url=base_url
        )
        cls.send_async(subject, [pilot.user.email], html_content)
        return True

    @classmethod
    def send_protest_alert_email(cls, protest, pilot, alert_type="abertura", extra_info=None):
        """
        Autônomo (Tribunal / Protestos):
        - 'abertura': Protesto aberto contra o piloto (prazo para defesa).
        - 'prazo_24h': Menos de 24h para envio da defesa.
        - 'veredito': Decisão final dos comissários emitida.
        """
        if not (pilot and pilot.user and pilot.user.email):
            return False

        app = current_app._get_current_object()
        base_url = cls._get_base_url(app)

        subjects = {
            'abertura': f"⚖️ Tribunal FullGas: Protesto #{protest.id} aberto contra você",
            'prazo_24h': f"⏳ Urgente: Menos de 24h para envio da sua defesa no Protesto #{protest.id}",
            'veredito': f"📋 Tribunal FullGas: Julgamento concluído - Protesto #{protest.id}"
        }

        subject = subjects.get(alert_type, f"⚖️ Notificação do Tribunal - Protesto #{protest.id}")

        html_content = render_template(
            'emails/protest_alert_email.html',
            protest=protest,
            pilot=pilot,
            alert_type=alert_type,
            extra_info=extra_info,
            subject=subject,
            base_url=base_url
        )
        cls.send_async(subject, [pilot.user.email], html_content)
        return True
