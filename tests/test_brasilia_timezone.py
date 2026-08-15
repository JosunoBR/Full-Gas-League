import unittest
from datetime import datetime, timedelta
from run import app, db, format_datetime
from app.models import User, PilotProfile, Season, Race, GridConfig, Protesto, RaceRegistration
from app.utils import get_brasilia_now
from app.routes.public import _is_protest_defense_open

class BrasiliaTimezoneTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_get_brasilia_now_offset(self):
        """Garante que get_brasilia_now() está exatamente 3 horas atrás do UTC."""
        utc_now = datetime.utcnow()
        br_now = get_brasilia_now()
        
        # A diferença entre UTC e Brasília deve ser de aproximadamente 3 horas (10800s)
        diff_seconds = (utc_now - br_now).total_seconds()
        self.assertAlmostEqual(diff_seconds, 3 * 3600, delta=5, msg="get_brasilia_now() deve ser UTC-3")

    def test_protest_creation_in_brasilia_time(self):
        """Garante que novos protestos e registros são gravados diretamente no fuso horário de Brasília."""
        br_now_before = get_brasilia_now()
        
        protesto = Protesto(
            etapa_id=1,
            acusador_id=1,
            acusado_id=2,
            minuto="Volta 5",
            descricao="Incidente de teste"
        )
        
        br_now_after = get_brasilia_now()
        
        # A data_criacao deve ser preenchida pelo default get_brasilia_now
        self.assertIsNotNone(protesto.data_criacao)
        self.assertTrue(br_now_before <= protesto.data_criacao <= br_now_after, "data_criacao deve estar no fuso de Brasília")

    def test_format_datetime_filter(self):
        """Garante que format_datetime exibe corretamente o horário gravado em Brasília."""
        dt_test = datetime(2026, 8, 12, 19, 30) # 12/08/2026 às 19:30
        formatted = format_datetime(dt_test)
        self.assertEqual(formatted, "12/08/2026 às 19:30", "O format_datetime deve exibir o horário exato sem distorções de fuso")

    def test_protest_defense_48h_window_in_brasilia(self):
        """Garante que a janela de defesa de 48h funciona perfeitamente com o horário de Brasília."""
        protesto_recente = Protesto(data_criacao=get_brasilia_now() - timedelta(hours=24))
        protesto_expirado = Protesto(data_criacao=get_brasilia_now() - timedelta(hours=49))

        self.assertTrue(_is_protest_defense_open(protesto_recente), "Protesto de 24h atrás deve aceitar defesa")
        self.assertFalse(_is_protest_defense_open(protesto_expirado), "Protesto de 49h atrás não deve aceitar defesa")

if __name__ == '__main__':
    unittest.main()
