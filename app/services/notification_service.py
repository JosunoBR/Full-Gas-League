import firebase_admin
from firebase_admin import credentials, messaging
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
    # Obtém o caminho absoluto para o diretório raiz do projeto
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    cred_path = os.path.join(base_dir, 'firebase-credentials.json')

    if not os.path.exists(cred_path):
        print("AVISO: Arquivo 'firebase-credentials.json' não encontrado. As notificações push não funcionarão.")
        # Define uma variável para que o resto do código saiba que o serviço não está disponível
        _firebase_app = None
    else:
        cred = credentials.Certificate(cred_path)
        _firebase_app = firebase_admin.initialize_app(cred)

except ValueError:
    # O app já foi inicializado, o que é esperado em recarregamentos (reload).
    _firebase_app = firebase_admin.get_app()


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
            data=data or {},
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    sound='default',
                    icon='ic_notification' # Certifique-se de ter 'ic_notification.png' em 'android/app/src/main/res/drawable'
                )
            )
        )

        try:
            response = messaging.send(message)
            print(f'Notificação enviada com sucesso para {token}: {response}')
            return True
        except Exception as e:
            print(f'Erro ao enviar notificação para {token}: {e}')
            return False

    @staticmethod
    def send_multicast_notification(tokens, title, body, data=None):
        """
        Envia uma notificação push para múltiplos dispositivos de uma vez.

        :param tokens: Uma lista de FCM tokens dos dispositivos de destino.
        :param title: O título da notificação.
        :param body: O corpo da notificação.
        :param data: Um dicionário opcional de dados.
        :return: True se pelo menos uma notificação foi enviada com sucesso.
        """
        if not _firebase_app:
            print(f"NOTIFICAÇÃO EM MASSA (simulada para {len(tokens)} usuários): '{title}' - '{body}'")
            return False

        if not tokens:
            print("Erro de notificação: A lista de tokens está vazia.")
            return False

        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            tokens=tokens,
            data=data or {},
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    sound='default',
                    icon='ic_notification'
                )
            )
        )

        try:
            response = messaging.send_multicast(message)
            print(f'{response.success_count} de {len(tokens)} notificações enviadas com sucesso.')
            if response.failure_count > 0:
                print(f'{response.failure_count} notificações falharam.')
            return response.success_count > 0
        except Exception as e:
            print(f'Erro ao enviar notificações em massa: {e}')
            return False
