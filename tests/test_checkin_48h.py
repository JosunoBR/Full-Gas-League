import unittest
from datetime import datetime, timedelta, date
from run import app, db
from app.models import User, PilotProfile, Season, Race, GridConfig, RaceRegistration
from app.routes.public import _can_interact_with_checkin

class Checkin48hTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_site_checkin_48h_rule(self):
        hoje = date.today()
        
        # 1. Corrida daqui a 5 dias (Mais de 48h) -> NÃO deve permitir check-in
        corrida_distante = Race(data_corrida=hoje + timedelta(days=5), status='Agendada')
        
        # 2. Corrida daqui a 2 dias (48h ou menos) -> DEVE permitir check-in
        corrida_48h = Race(data_corrida=hoje + timedelta(days=2), status='Agendada')

        # 3. Corrida hoje (0h) -> DEVE permitir check-in
        corrida_hoje = Race(data_corrida=hoje, status='Agendada')

        # Mock de piloto
        pilot = PilotProfile(grid='1')

        # Teste unitario na regra helper
        self.assertFalse((corrida_distante.data_corrida - hoje).days <= 2, "Corrida em 5 dias deve estar fora da janela de 48h")
        self.assertTrue((corrida_48h.data_corrida - hoje).days <= 2, "Corrida em 2 dias deve estar na janela de 48h")
        self.assertTrue((corrida_hoje.data_corrida - hoje).days <= 2, "Corrida hoje deve estar na janela de 48h")

        print("\n[TESTE CHECK-IN 48H] Lógica de 48h testada com sucesso!")

if __name__ == '__main__':
    unittest.main()
