import unittest
from run import app, db
from app.models import User, Season, GridConfig, PilotProfile
from app.routes.admin import format_driver_broadcast_name

class ExportClassificationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_format_driver_broadcast_name(self):
        # Cria perfis de teste na memória
        class MockPilot:
            def __init__(self, nickname, nome_real):
                self.nickname = nickname
                self.nome_real = nome_real

        # Padrão: Primeiro nome + Inicial do último sobrenome (ex: Lucas V., João B., Leonardo V.)
        self.assertEqual(format_driver_broadcast_name(MockPilot('Barros', 'João Paulo Barros')), 'João B.')
        self.assertEqual(format_driver_broadcast_name(MockPilot('Vieira', 'Lucas Vieira')), 'Lucas V.')
        self.assertEqual(format_driver_broadcast_name(MockPilot('Vieira', 'LEONARDO VIEIRA')), 'Leonardo V.')
        self.assertEqual(format_driver_broadcast_name(MockPilot('Leandro', 'Leandro')), 'Leandro')
        self.assertEqual(format_driver_broadcast_name(MockPilot('Doctor_Killer', '')), 'Doctor_Killer')
        self.assertEqual(format_driver_broadcast_name(MockPilot('SMX | João Shura', '')), 'João S.')

    def test_export_classification_csv_endpoint(self):
        admin = User.query.filter_by(role='ADM').first()
        season = Season.query.filter_by(ativa=True).first()
        grid = GridConfig.query.filter_by(season_id=season.id).first()

        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(admin.id)
            sess['_fresh'] = True

        res = self.client.get(f'/admin/overview/export?season_id={season.id}&grid_id={grid.id}')
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/csv', res.headers.get('Content-Type', ''))
        self.assertIn('attachment', res.headers.get('Content-Disposition', ''))

        # Confirma UTF-8 BOM
        raw_bytes = res.data
        self.assertTrue(raw_bytes.startswith(b'\xef\xbb\xbf'), "Deve conter o BOM UTF-8 para compatibilidade com Excel")

        text = raw_bytes.decode('utf-8-sig')
        lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
        self.assertGreater(len(lines), 0)
        
        # Confirma cabeçalho exato: POSIÇÃO;EQUIPE;NOME;PONTOS
        header = lines[0]
        self.assertEqual(header, 'POSIÇÃO;EQUIPE;NOME;PONTOS')

        # Se houver linhas de dados, valida formato das colunas
        if len(lines) > 1:
            primeira_linha = lines[1].split(';')
            self.assertEqual(len(primeira_linha), 4, "Cada linha deve conter exatamente 4 colunas")
            self.assertEqual(primeira_linha[0], '1', "Primeira posição deve ser 1")

    def test_export_constructors_classification_csv_endpoint(self):
        admin = User.query.filter_by(role='ADM').first()
        season = Season.query.filter_by(ativa=True).first()
        grid = GridConfig.query.filter_by(season_id=season.id).first()

        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(admin.id)
            sess['_fresh'] = True

        res = self.client.get(f'/admin/overview/export_constructors?season_id={season.id}&grid_id={grid.id}')
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/csv', res.headers.get('Content-Type', ''))
        self.assertIn('attachment', res.headers.get('Content-Disposition', ''))

        # Confirma UTF-8 BOM
        raw_bytes = res.data
        self.assertTrue(raw_bytes.startswith(b'\xef\xbb\xbf'), "Deve conter o BOM UTF-8 para compatibilidade com Excel")

        text = raw_bytes.decode('utf-8-sig')
        lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
        self.assertGreater(len(lines), 0)

        # Confirma cabeçalho exato: POSIÇÃO;EQUIPE;PONTOS
        header = lines[0]
        self.assertEqual(header, 'POSIÇÃO;EQUIPE;PONTOS')

        # Se houver linhas de dados, valida formato das colunas
        if len(lines) > 1:
            primeira_linha = lines[1].split(';')
            self.assertEqual(len(primeira_linha), 3, "Cada linha deve conter exatamente 3 colunas")
            self.assertEqual(primeira_linha[0], '1', "Primeira posição deve ser 1")

if __name__ == '__main__':
    unittest.main()

