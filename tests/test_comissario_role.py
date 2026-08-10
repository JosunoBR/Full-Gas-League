import unittest
from run import app, db
from app.models import User, PilotProfile

class ComissarioRoleTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Cria usuário Comissário para teste
        self.comissario_user = User.query.filter_by(username='test_comissario').first()
        if not self.comissario_user:
            self.comissario_user = User(username='test_comissario', email='comissario@test.local', role='COMISSARIO')
            self.comissario_user.set_password('pass123')
            db.session.add(self.comissario_user)
            db.session.commit()

        # Cria usuário Super Admin para teste
        self.superadmin_user = User.query.filter_by(username='test_superadmin').first()
        if not self.superadmin_user:
            self.superadmin_user = User(username='test_superadmin', email='superadmin@test.local', role='SUPER_ADM')
            self.superadmin_user.set_password('pass123')
            db.session.add(self.superadmin_user)
            db.session.commit()

    def tearDown(self):
        self.app_context.pop()

    def login(self, username, password='pass123'):
        return self.client.post('/login', data={'login': username, 'password': password}, follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    def test_comissario_allowed_routes(self):
        """Valida se Comissário acessa com sucesso (200) as rotas permitidas."""
        self.login('test_comissario')

        allowed_urls = [
            '/admin/dashboard',
            '/admin/overview',
            '/admin/analytics',
            '/admin/historic',
            '/admin/protests'
        ]

        for url in allowed_urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, f"Comissário deveria ter acesso a {url}")

    def test_comissario_forbidden_routes(self):
        """Valida se Comissário é bloqueado (redirecionado para dashboard) em rotas não autorizadas."""
        self.login('test_comissario')

        forbidden_urls = [
            '/admin/seasons',
            '/admin/pilots',
            '/admin/teams',
            '/admin/seletiva',
            '/admin/invites',
            '/admin/users'
        ]

        for url in forbidden_urls:
            res = self.client.get(url, follow_redirects=False)
            self.assertEqual(res.status_code, 302, f"Comissário deveria ser redirecionado ao tentar acessar {url}")
            self.assertIn('/admin/dashboard', res.location, f"Redirecionamento de {url} deve ser para dashboard")

    def test_superadmin_can_assign_comissario_role(self):
        """Valida se o Super Admin pode atribuir o papel COMISSARIO a outro usuário."""
        self.login('test_superadmin')

        # Criar usuário temporário para alteração de papel
        target_user = User.query.filter_by(username='target_user_role').first()
        if not target_user:
            target_user = User(username='target_user_role', email='target_role@test.local', role='PILOTO')
            target_user.set_password('pass123')
            db.session.add(target_user)
            db.session.commit()

        res = self.client.post(f'/admin/users/{target_user.id}/update_role', data={'role': 'COMISSARIO'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        updated_user = User.query.get(target_user.id)
        self.assertEqual(updated_user.role, 'COMISSARIO')

if __name__ == '__main__':
    unittest.main()
