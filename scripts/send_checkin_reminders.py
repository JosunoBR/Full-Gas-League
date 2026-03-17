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
        
        # Define o intervalo de tempo para buscar corridas (próximas 48h)
        now = datetime.utcnow()
        lookahead_start = now + timedelta(hours=23)
        lookahead_end = now + timedelta(hours=48)

        # 1. Encontra corridas agendadas dentro do intervalo
        races_to_remind = Race.query.filter(
            Race.data_corrida >= lookahead_start.date(),
            Race.data_corrida <= lookahead_end.date(),
            Race.status == 'Agendada'
        ).all()

        if not races_to_remind:
            print("Nenhuma corrida encontrada no intervalo para enviar lembretes.")
            return

        print(f"Encontradas {len(races_to_remind)} corridas no período.")
        
        for race in races_to_remind:
            print(f"
Processando corrida: '{race.nome_gp}' do grid '{race.grid}'")
            
            # 2. Encontra todos os pilotos que deveriam correr (vinculados ao grid)
            # Este passo é crucial para encontrar quem AINDA NÃO respondeu.
            all_pilots_in_grid = PilotProfile.query.filter(
                (PilotProfile.teams.any(grid_id=race.grid_id)) |
                (PilotProfile.reserve_teams.any(grid_id=race.grid_id))
            ).all()

            if not all_pilots_in_grid:
                print("Nenhum piloto encontrado para este grid.")
                continue

            # 3. Encontra quem JÁ respondeu ao check-in
            registrations = RaceRegistration.query.filter_by(race_id=race.id).all()
            pilots_who_responded_ids = {reg.pilot_id for reg in registrations}
            
            # 4. Determina quem está pendente e coleta os tokens
            pending_pilots_tokens = []
            for pilot in all_pilots_in_grid:
                if pilot.id not in pilots_who_responded_ids:
                    if pilot.fcm_token:
                        pending_pilots_tokens.append(pilot.fcm_token)
                        print(f"  -> Lembrete para: {pilot.nickname} (ID: {pilot.id})")
            
            if not pending_pilots_tokens:
                print("Todos os pilotos do grid já responderam ao check-in.")
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
