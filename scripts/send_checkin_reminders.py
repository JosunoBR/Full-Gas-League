import os
import sys
from datetime import datetime, timedelta

# Adiciona o diretório raiz do projeto ao path do Python
# para que possamos importar os módulos do nosso aplicativo Flask
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Race, RaceRegistration, PilotProfile
from app.services.notification_service import NotificationService

def send_checkin_reminders():
    """
    Busca corridas se aproximando e envia notificações para pilotos
    com check-in pendente.
    """
    app = create_app()
    with app.app_context():
        print("--- Iniciando verificação de lembretes de check-in ---")
        
        # Define o intervalo estrito: Apenas corridas hoje ou nas próximas 24h (véspera do GP)
        now = datetime.utcnow()
        today = now.date()
        tomorrow = today + timedelta(days=1)

        # 1. Encontra apenas corridas agendadas para hoje ou amanhã (janela de 24h)
        races_to_remind = Race.query.filter(
            Race.data_corrida >= today,
            Race.data_corrida <= tomorrow,
            Race.status == 'Agendada'
        ).all()

        if not races_to_remind:
            print("Nenhuma corrida agendada nas próximas 24h para enviar lembretes.")
            return

        print(f"Encontradas {len(races_to_remind)} corridas na janela de 24h.")
        
        for race in races_to_remind:
            print(f"\nProcessando corrida: '{race.nome_gp}' do grid ID {race.grid_id} ('{race.grid}')")
            
            # 2. Encontra os pilotos vinculados ao grid desta corrida específica
            if race.grid_id:
                all_pilots_in_grid = PilotProfile.query.filter(
                    (PilotProfile.teams.any(grid_id=race.grid_id)) |
                    (PilotProfile.reserve_teams.any(grid_id=race.grid_id))
                ).all()
            else:
                all_pilots_in_grid = PilotProfile.query.filter(PilotProfile.grid != 'SEM_GRID').all()

            if not all_pilots_in_grid:
                print("Nenhum piloto ativo encontrado para este grid.")
                continue

            # 3. Encontra quem JÁ respondeu (CONFIRMADO ou JUSTIFICADO)
            registrations = RaceRegistration.query.filter_by(race_id=race.id).all()
            pilots_who_responded_ids = {
                reg.pilot_id for reg in registrations 
                if reg.status in ['CONFIRMADO', 'JUSTIFICADO']
            }
            
            # 4. Determina quem está pendente e possui token FCM registrado
            pending_pilots_tokens = []
            for pilot in all_pilots_in_grid:
                if pilot.id not in pilots_who_responded_ids and pilot.fcm_token:
                    pending_pilots_tokens.append(pilot.fcm_token)
                    print(f"  -> Lembrete (24h) para: {pilot.nickname} (ID: {pilot.id})")
            
            if not pending_pilots_tokens:
                print("Todos os pilotos deste grid já responderam ou não possuem dispositivo registrado.")
                continue

            # 5. Envia a notificação em massa
            print(f"Enviando notificação para {len(pending_pilots_tokens)} pilotos...")
            
            title = "🏁 Lembrete de Check-in"
            body = f"A corrida '{race.nome_gp}' se aproxima! Acesse o app e confirme sua presença."
            
            success = NotificationService.send_multicast_notification(
                tokens=pending_pilots_tokens,
                title=title,
                body=body,
                data={'race_id': str(race.id)}
            )

            if success:
                print("Notificações de lembrete enviadas com sucesso.")
            else:
                print("Falha ao enviar notificações de lembrete.")

    print("
--- Verificação concluída ---")

if __name__ == '__main__':
    # Para executar este script manualmente:
    # python scripts/send_checkin_reminders.py
    send_checkin_reminders()
