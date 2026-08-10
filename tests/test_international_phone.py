import unittest
from run import app, db
from app.models import User, PilotProfile
from app.utils import format_international_phone, parse_phone_components, DDI_OPTIONS

class InternationalPhoneTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_phone_formatters(self):
        """Valida formatação e parsing de números de telefone com DDI."""
        # 1. Formatação Brasil (+55)
        res_br = format_international_phone('+55', '(11) 95164-2119')
        self.assertEqual(res_br, '+55 (11) 95164-2119')

        # 2. Formatação Portugal (+351)
        res_pt = format_international_phone('+351', '912345678')
        self.assertEqual(res_pt, '+351 912345678')

        # 3. Formatação EUA (+1)
        res_us = format_international_phone('+1', '3055550199')
        self.assertEqual(res_us, '+1 3055550199')

        # 4. Parsing de componentes
        ddi_pt, num_pt = parse_phone_components('+351 912345678')
        self.assertEqual(ddi_pt, '+351')
        self.assertEqual(num_pt, '912345678')

        ddi_br, num_br = parse_phone_components('+55 (11) 95164-2119')
        self.assertEqual(ddi_br, '+55')
        self.assertEqual(num_br, '(11) 95164-2119')

    def test_registration_with_international_phone(self):
        """Valida se o cadastro de piloto salva o telefone no formato com DDI."""
        # Excluir se já existir
        user = User.query.filter_by(email='pilot_pt@test.local').first()
        if user:
            PilotProfile.query.filter_by(user_id=user.id).delete()
            db.session.delete(user)
            db.session.commit()

        response = self.client.post('/register', data={
            'nickname': 'PilotPortugal',
            'nome_real': 'João Silva',
            'email': 'pilot_pt@test.local',
            'password': 'pass123',
            'confirm_password': 'pass123',
            'ddi': '+351',
            'telefone_numero': '912345678'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)

        created_user = User.query.filter_by(email='pilot_pt@test.local').first()
        self.assertIsNotNone(created_user)
        self.assertIsNotNone(created_user.pilot_profile)
        self.assertEqual(created_user.pilot_profile.telefone, '+351 912345678')

if __name__ == '__main__':
    unittest.main()
