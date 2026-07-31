import unittest
from run import app, db
from app.models import Season, GridConfig, Race, PilotProfile, RaceResult, Team

class RaceSummaryWebAndAppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_web_and_app_race_summary_endpoints(self):
        # Encontra a primeira corrida cadastrada no banco
        race = Race.query.first()
        if not race:
            self.skipTest("Nenhuma corrida encontrada no banco para testar súmula.")

        print(f"\n[TESTE] Testando corrida ID {race.id} - GP '{race.nome_gp}'...")

        # 1. Teste do Endpoint Exclusivo do Portal WEB (/api/race/<id>/results)
        res_web = self.client.get(f'/api/race/{race.id}/results')
        self.assertEqual(res_web.status_code, 200, "Endpoint Web deve retornar HTTP 200")
        data_web = res_web.get_json()
        self.assertIn('nome_gp', data_web)
        self.assertEqual(data_web['id'], race.id)
        print(f"[TESTE WEB] Súmula Web OK: nome_gp='{data_web.get('nome_gp')}', status={res_web.status_code}")

        # 2. Teste do Endpoint Exclusivo do APP MOBILE (/api/app/race/<id>/summary)
        res_app = self.client.get(f'/api/app/race/{race.id}/summary')
        self.assertEqual(res_app.status_code, 200, "Endpoint App Mobile deve retornar HTTP 200")
        data_app = res_app.get_json()
        self.assertIn('nome_gp', data_app)
        self.assertIn('resultados', data_app)
        self.assertEqual(data_app['id'], race.id)
        
        # Garante que resultados do App contem pilotos com posicao > 0
        for r in data_app.get('resultados', []):
            self.assertGreater(r['posicao'], 0, "App nao deve ter posicao <= 0")
            self.assertIn('piloto', r)
            self.assertIn('equipe', r)

        print(f"[TESTE APP] Súmula App Mobile OK: total resultados válidos={len(data_app.get('resultados', []))}, status={res_app.status_code}")

if __name__ == '__main__':
    unittest.main()
