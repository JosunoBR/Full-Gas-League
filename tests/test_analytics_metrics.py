import unittest
from run import app, db
from app.models import User, AccessLog

class AnalyticsMetricsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_access_log_creation_and_analytics_endpoint(self):
        # 1. Simula um acesso do aplicativo móvel com cabeçalho X-Platform
        res_app = self.client.get('/api/grid-configs', headers={'X-Platform': 'MobileApp'})
        self.assertEqual(res_app.status_code, 200)

        # 2. Simula um acesso do portal Web
        res_web = self.client.get('/')
        self.assertEqual(res_web.status_code, 200)

        # 3. Verifica se os registros foram gravados no banco
        app_logs = AccessLog.query.filter_by(platform='APP').all()
        web_logs = AccessLog.query.filter_by(platform='WEB').all()

        self.assertGreater(len(app_logs), 0, "Deve registrar pelo menos 1 acesso do App")
        self.assertGreater(len(web_logs), 0, "Deve registrar pelo menos 1 acesso da Web")

        print(f"\n[TESTE ANALYTICS] Registros gravados no banco OK: App={len(app_logs)}, Web={len(web_logs)}")

if __name__ == '__main__':
    unittest.main()
