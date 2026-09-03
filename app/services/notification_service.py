try:
    import firebase_admin
    from firebase_admin import credentials, messaging
    HAS_FIREBASE = True
except ImportError:
    HAS_FIREBASE = False
import os

# --- INICIALIZAÇÃO DO FIREBASE ADMIN SDK ---
# O SDK precisa de credenciais para autenticar com os serviços do Firebase.
# Ele irá procurar por um arquivo 'firebase-credentials.json' na raiz do projeto.
# Certifique-se de que este arquivo existe e foi baixado do seu console do Firebase.
#
# A inicialização só deve ocorrer uma vez durante a vida da aplicação.
# O bloco 'try/except' garante que não tentaremos inicializar múltiplas vezes,
# o que causaria um erro.

try:
    if not HAS_FIREBASE:
        print("AVISO: Biblioteca 'firebase-admin' não está instalada. As notificações push serão simuladas.")
        _firebase_app = None
    else:
        # Obtém o caminho absoluto para o diretório raiz do projeto
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        cred_path = os.path.join(base_dir, 'firebase-credentials.json')

        if not os.path.exists(cred_path):
            print("AVISO: Arquivo 'firebase-credentials.json' não encontrado. As notificações push não funcionarão.")
            _firebase_app = None
        else:
            cred = credentials.Certificate(cred_path)
            _firebase_app = firebase_admin.initialize_app(cred)

except ValueError as e:
    # O Firebase lança ValueError tanto para app já inicializado (esperado em reloads)
    # quanto para credenciais inválidas. Distinguimos pelos dois casos.
    if 'already exists' in str(e) or 'already initialized' in str(e):
        if HAS_FIREBASE:
            _firebase_app = firebase_admin.get_app()
        else:
            _firebase_app = None
    else:
        print(f"AVISO: Credencial Firebase inválida ou template não preenchido: {e}")
        _firebase_app = None
except Exception as e:
    print(f"Erro ao inicializar Firebase: {e}")
    _firebase_app = None


class NotificationService:
    @staticmethod
    def send_single_notification(token, title, body, data=None):
        """
        Envia uma notificação push para um único dispositivo.

        :param token: O FCM token do dispositivo de destino.
        :param title: O título da notificação.
        :param body: O corpo (mensagem) da notificação.
        :param data: Um dicionário opcional de dados a serem enviados com a mensagem.
        :return: True se o envio foi bem-sucedido, False caso contrário.
        """
        if not _firebase_app:
            print(f"NOTIFICAÇÃO (simulada para {token}): '{title}' - '{body}'")
            return False

        if not token:
            print("Erro de notificação: Token do dispositivo está vazio.")
            return False

        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            token=token,
            data={str(k): str(v) for k, v in (data or {}).items()},
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    sound='default',
                    icon='ic_notification',
                    channel_id='fullgas-default'
                )
            )
        )

        try:
            response = messaging.send(message)
            print(f'Notificação enviada com sucesso para {token[:20]}...: {response}')
            return True
        except messaging.UnregisteredError:
            print(f'Token inválido/expirado: {token[:20]}... — será limpo do banco.')
            return 'INVALID_TOKEN'
        except Exception as e:
            print(f'Erro ao enviar notificação para {token[:20]}...: {e}')
            return False

    @staticmethod
    def send_multicast_notification(tokens, title, body, data=None):
        """
        Envia uma notificação push para múltiplos dispositivos de uma vez.

        :param tokens: Uma lista de FCM tokens dos dispositivos de destino.
        :param title: O título da notificação.
        :param body: O corpo da notificação.
        :param data: Um dicionário opcional de dados.
        :return: Tupla (success_count, invalid_tokens[]) com tokens inválidos para limpeza.
        """
        if not _firebase_app:
            print(f"NOTIFICAÇÃO EM MASSA (simulada para {len(tokens)} usuários): '{title}' - '{body}'")
            return 0, []

        if not tokens:
            print("Erro de notificação: A lista de tokens está vazia.")
            return 0, []

        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            tokens=tokens,
            data={str(k): str(v) for k, v in (data or {}).items()},
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    sound='default',
                    icon='ic_notification',
                    channel_id='fullgas-default'
                )
            )
        )

        try:
            if hasattr(messaging, 'send_each_for_multicast'):
                response = messaging.send_each_for_multicast(message)
            else:
                response = messaging.send_multicast(message)
            print(f'{response.success_count} de {len(tokens)} notificações enviadas com sucesso.')

            # Coleta tokens inválidos para limpeza
            invalid_tokens = []
            if response.failure_count > 0:
                for idx, result in enumerate(response.responses):
                    if not result.success:
                        error_code = result.exception.code if result.exception else 'unknown'
                        if error_code in ('registration-token-not-registered', 'invalid-registration-token'):
                            invalid_tokens.append(tokens[idx])
                        print(f'Falha no token [{idx}]: {error_code}')

            return response.success_count, invalid_tokens
        except Exception as e:
            print(f'Erro ao enviar notificações em massa: {e}')
            return 0, []

    @staticmethod
    def cleanup_invalid_tokens(invalid_tokens):
        """
        Remove tokens FCM inválidos do banco de dados.
        Deve ser chamado após um send_multicast que retornou tokens inválidos.

        :param invalid_tokens: Lista de tokens FCM inválidos a serem removidos.
        """
        if not invalid_tokens:
            return

        try:
            from app.models import db, PilotProfile
            updated = PilotProfile.query.filter(
                PilotProfile.fcm_token.in_(invalid_tokens)
            ).update({PilotProfile.fcm_token: None}, synchronize_session=False)
            db.session.commit()
            print(f'[NotificationService] {updated} token(s) inválido(s) removido(s) do banco.')
        except Exception as e:
            print(f'[NotificationService] Erro ao limpar tokens inválidos: {e}')
