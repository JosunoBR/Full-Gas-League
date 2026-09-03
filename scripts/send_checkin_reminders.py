import os
import sys

# Adiciona o diretório raiz do projeto ao path do Python
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from run import app
from app.services.scheduler_service import notificar_checkin_pendente

def send_checkin_reminders():
    """
    Busca corridas na janela de check-in e envia notificações push para pilotos
    com check-in pendente via notificar_checkin_pendente.
    """
    with app.app_context():
        print("--- Iniciando verificação de lembretes de check-in ---")
        sucesso, msg, count = notificar_checkin_pendente()
        print(f"Resultado: {msg} (Enviados: {count})")
        print("\n--- Verificação concluída ---")

if __name__ == '__main__':
    # Para executar este script manualmente:
    # python scripts/send_checkin_reminders.py
    send_checkin_reminders()
