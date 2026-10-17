import unittest
from run import app, db
from app.models import User, PilotProfile, Protesto, VotoComissario

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
            db.session.add(self.comissario_user)
        self.comissario_user.role = 'COMISSARIO'
        self.comissario_user.set_password('pass123')
        db.session.commit()

        # Cria usuário Comissário Convidado para teste
        self.comissario_convidado_user = User.query.filter_by(username='test_comissario_convidado').first()
        if not self.comissario_convidado_user:
            self.comissario_convidado_user = User(username='test_comissario_convidado', email='comissario_convidado@test.local', role='COMISSARIO_CONVIDADO')
            db.session.add(self.comissario_convidado_user)
        self.comissario_convidado_user.role = 'COMISSARIO_CONVIDADO'
        self.comissario_convidado_user.set_password('pass123')
        db.session.commit()

        # Cria usuário Super Admin para teste
        self.superadmin_user = User.query.filter_by(username='test_superadmin').first()
        if not self.superadmin_user:
            self.superadmin_user = User(username='test_superadmin', email='superadmin@test.local', role='SUPER_ADM')
            db.session.add(self.superadmin_user)
        self.superadmin_user.role = 'SUPER_ADM'
        self.superadmin_user.set_password('pass123')
        db.session.commit()

    def tearDown(self):
        self.app_context.pop()

    def login(self, username, password='pass123'):
        if username == 'test_comissario':
            email = self.comissario_user.email
        elif username == 'test_comissario_convidado':
            email = self.comissario_convidado_user.email
        elif username == 'test_superadmin':
            email = self.superadmin_user.email
        else:
            email = f"{username}@test.local" if '@' not in username else username
        return self.client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

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

    def test_comissario_convidado_allowed_routes(self):
        """Valida se Comissário Convidado tem acesso apenas ao dashboard e ao tribunal (protests)."""
        self.login('test_comissario_convidado')

        allowed_urls = [
            '/admin/dashboard',
            '/admin/protests'
        ]

        for url in allowed_urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, f"Comissário Convidado deveria ter acesso a {url}")

    def test_comissario_convidado_forbidden_routes(self):
        """Valida se Comissário Convidado é bloqueado em rotas como overview, analytics, historic, seasons, etc."""
        self.login('test_comissario_convidado')

        forbidden_urls = [
            '/admin/overview',
            '/admin/analytics',
            '/admin/historic',
            '/admin/seasons',
            '/admin/pilots',
            '/admin/teams',
            '/admin/seletiva',
            '/admin/invites',
            '/admin/users'
        ]

        for url in forbidden_urls:
            res = self.client.get(url, follow_redirects=False)
            self.assertEqual(res.status_code, 302, f"Comissário Convidado deveria ser redirecionado de {url}")
            self.assertIn('/admin/dashboard', res.location, f"Redirecionamento de {url} deve ser para dashboard")

    def test_comissario_convidado_dashboard_cards(self):
        """Valida que o dashboard renderiza o Tribunal e não exibe os cards bloqueados para o Comissário Convidado."""
        self.login('test_comissario_convidado')
        res = self.client.get('/admin/dashboard')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn('Tribunal', html)
        self.assertIn('SALA DOS JUÍZES', html)
        self.assertNotIn('Visão Geral', html)
        self.assertNotIn('Analytics & Acessos', html)
        self.assertNotIn('Mídia & Broadcast', html)

    def test_superadmin_can_promote_pilot_to_comissario_convidado(self):
        """Valida se o Super Admin pode promover um piloto ao papel COMISSARIO_CONVIDADO."""
        self.login('test_superadmin')

        # Criar piloto temporário com perfil
        test_pilot_user = User.query.filter_by(email='promo_test@test.local').first()
        if not test_pilot_user:
            test_pilot_user = User(username='pilot_promo_test', email='promo_test@test.local', role='PILOTO')
            test_pilot_user.set_password('pass123')
            db.session.add(test_pilot_user)
            db.session.flush()
            profile = PilotProfile(user_id=test_pilot_user.id, nickname='PromoPilot', nome_real='Promo Test', grid='SEM_GRID')
            db.session.add(profile)
            db.session.commit()
        else:
            test_pilot_user.role = 'PILOTO'
            db.session.commit()

        pilot_profile = test_pilot_user.pilot_profile
        # Executa POST na rota de edição de piloto promovendo para COMISSARIO_CONVIDADO
        post_data = {
            'nickname': pilot_profile.nickname,
            'nome_real': pilot_profile.nome_real,
            'role': 'COMISSARIO_CONVIDADO'
        }
        res = self.client.post(f'/admin/pilots/edit/{pilot_profile.id}', data=post_data, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        db.session.refresh(test_pilot_user)
        self.assertEqual(test_pilot_user.role, 'COMISSARIO_CONVIDADO')

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

        updated_user = db.session.get(User, target_user.id)
        self.assertEqual(updated_user.role, 'COMISSARIO')

    def test_comissario_convidado_can_vote_in_protest(self):
        """Valida que o Comissário Convidado pode votar normalmente em um protesto em andamento."""
        protesto = Protesto.query.filter_by(status='EM_VOTACAO').first()
        if not protesto:
            protesto = Protesto.query.first()
        if protesto:
            protesto.status = 'EM_VOTACAO'
            db.session.commit()

            self.login('test_comissario_convidado')
            res = self.client.post(f'/admin/protests/{protesto.id}', data={'voto': 'INOCENTE'}, follow_redirects=True)
            self.assertEqual(res.status_code, 200)

            voto = VotoComissario.query.filter_by(protesto_id=protesto.id, admin_id=self.comissario_convidado_user.id).first()
            self.assertIsNotNone(voto)
            self.assertEqual(voto.escolha, 'INOCENTE')

    def test_comissario_convidado_cannot_manipulate_tickets(self):
        """Valida que o Comissário Convidado NÃO pode fechar, encerrar ou reabrir tickets."""
        protesto = Protesto.query.filter_by(status='EM_VOTACAO').first()
        if not protesto:
            protesto = Protesto.query.first()
        if protesto:
            protesto.status = 'EM_VOTACAO'
            db.session.commit()

            self.login('test_comissario_convidado')

            # 1. Tentativa de encerrar protesto
            close_data = {
                'encerrar': 'true',
                'veredito_final': 'LEVE',
                'justificativa': 'Tentativa indevida'
            }
            res = self.client.post(f'/admin/protests/{protesto.id}', data=close_data, follow_redirects=True)
            self.assertEqual(res.status_code, 200)

            db.session.refresh(protesto)
            self.assertEqual(protesto.status, 'EM_VOTACAO', "Comissário Convidado não deve conseguir encerrar o ticket")

            # 2. Tentativa de reabrir protesto já concluído
            protesto.status = 'CONCLUIDO'
            db.session.commit()

            reopen_data = {'reabrir': 'true'}
            res = self.client.post(f'/admin/protests/{protesto.id}', data=reopen_data, follow_redirects=True)
            self.assertEqual(res.status_code, 200)

            db.session.refresh(protesto)
            self.assertEqual(protesto.status, 'CONCLUIDO', "Comissário Convidado não deve conseguir reabrir o ticket")

if __name__ == '__main__':
    unittest.main()


