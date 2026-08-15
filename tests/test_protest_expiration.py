import os
import sys
import tempfile
import shutil
import unittest
from datetime import timedelta

from flask import Flask
from flask_login import LoginManager
from flask_jwt_extended import JWTManager

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.models import db, User, PilotProfile, Season, Race, Protesto, GridConfig
from app.routes.admin import admin_bp
from app.routes.public import public_bp
from app.services.protest_service import ProtestService
from app.utils import get_brasilia_now


def create_test_app(database_uri, upload_folder):
    app = Flask(
        __name__,
        template_folder=os.path.join(PROJECT_ROOT, 'app', 'templates'),
        static_folder=os.path.join(PROJECT_ROOT, 'app', 'static'),
    )
    app.config.update(
        TESTING=True,
        SECRET_KEY='test-secret-key',
        SQLALCHEMY_DATABASE_URI=database_uri,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY='test-jwt-secret',
        UPLOAD_FOLDER=upload_folder,
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg', 'gif'},
        INSTAGRAM_URL='https://example.com/instagram',
        YOUTUBE_URL='https://example.com/youtube',
        CONTACT_EMAIL='test@example.com',
    )
    db.init_app(app)
    jwt = JWTManager(app)

    @jwt.user_identity_loader
    def user_identity_lookup(identity):
        return str(identity)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'public.login'

    @app.template_filter('format_datetime')
    def format_datetime(value, format="%d/%m/%Y às %H:%M"):
        if not value:
            return ""
        return value.strftime(format)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    return app


class ProtestExpirationTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix='fullgas-protests-')
        self.db_path = os.path.join(self.temp_dir, 'test_protests.db')
        self.upload_folder = os.path.join(self.temp_dir, 'uploads')
        os.makedirs(self.upload_folder, exist_ok=True)

        self.app = create_test_app(f'sqlite:///{self.db_path}', self.upload_folder)
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            
            # Setup base data
            self.u_admin = User(username='admin_test', email='admin@test.com', role='SUPER_ADM')
            self.u_admin.set_password('pass')
            
            self.u_pilot1 = User(username='pilot1', email='p1@test.com', role='PILOTO')
            self.u_pilot1.set_password('pass')
            self.u_pilot2 = User(username='pilot2', email='p2@test.com', role='PILOTO')
            self.u_pilot2.set_password('pass')
            
            db.session.add_all([self.u_admin, self.u_pilot1, self.u_pilot2])
            db.session.commit()

            self.p1 = PilotProfile(user_id=self.u_pilot1.id, nickname='P1', nome_real='Piloto 1')
            self.p2 = PilotProfile(user_id=self.u_pilot2.id, nickname='P2', nome_real='Piloto 2')
            db.session.add_all([self.p1, self.p2])
            db.session.commit()

            self.grid = GridConfig(nome='GRID 1')
            self.season = Season(nome='Season 1', ativa=True, data_inicio=get_brasilia_now().date())
            db.session.add_all([self.grid, self.season])
            db.session.commit()

            self.race = Race(nome_gp='GP Teste', pista='Interlagos', grid='GRID 1', season_id=self.season.id, grid_id=self.grid.id, data_corrida=get_brasilia_now().date())
            db.session.add(self.race)
            db.session.commit()

            self.race_id = self.race.id
            self.p1_id = self.p1.id
            self.p2_id = self.p2.id
            self.grid_id = self.grid.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_protest_auto_transitions_to_voting_after_48h(self):
        with self.app.app_context():
            agora = get_brasilia_now()
            
            # Protesto com mais de 48h (ex: 50h atrás)
            p_expirado = Protesto(
                etapa_id=self.race_id,
                grid_id=self.grid_id,
                acusador_id=self.p1_id,
                acusado_id=self.p2_id,
                video_link='https://youtube.com/watch?v=123',
                descricao='Toque na curva 1',
                status='AGUARDANDO_DEFESA',
                data_criacao=agora - timedelta(hours=50)
            )
            
            # Protesto recente (ex: 10h atrás)
            p_recente = Protesto(
                etapa_id=self.race_id,
                grid_id=self.grid_id,
                acusador_id=self.p1_id,
                acusado_id=self.p2_id,
                video_link='https://youtube.com/watch?v=456',
                descricao='Toque na curva 2',
                status='AGUARDANDO_DEFESA',
                data_criacao=agora - timedelta(hours=10)
            )
            
            db.session.add_all([p_expirado, p_recente])
            db.session.commit()
            
            p_exp_id = p_expirado.id
            p_rec_id = p_recente.id
            
            # Executa a rotina de atualização
            expirados = ProtestService.atualizar_protestos_expirados()
            
            self.assertEqual(len(expirados), 1)
            self.assertEqual(expirados[0].id, p_exp_id)
            
            # Recarrega do banco
            p_exp_db = db.session.get(Protesto, p_exp_id)
            p_rec_db = db.session.get(Protesto, p_rec_id)
            
            self.assertEqual(p_exp_db.status, 'EM_VOTACAO', "Protesto após 48h deve ir para EM_VOTACAO")
            self.assertEqual(p_rec_db.status, 'AGUARDANDO_DEFESA', "Protesto recente deve continuar AGUARDANDO_DEFESA")

    def test_admin_protests_view_updates_expired(self):
        with self.app.app_context():
            agora = get_brasilia_now()
            p_expirado = Protesto(
                etapa_id=self.race_id,
                grid_id=self.grid_id,
                acusador_id=self.p1_id,
                acusado_id=self.p2_id,
                video_link='https://youtube.com/watch?v=123',
                descricao='Toque na curva 1',
                status='AGUARDANDO_DEFESA',
                data_criacao=agora - timedelta(hours=49)
            )
            db.session.add(p_expirado)
            db.session.commit()
            p_id = p_expirado.id

        # Faz login como admin e acessa /admin/protests
        with self.client:
            self.client.post('/login', data={'email': 'admin@test.com', 'password': 'pass'}, follow_redirects=True)
            res = self.client.get('/admin/protests')
            self.assertEqual(res.status_code, 200)

        with self.app.app_context():
            p_check = db.session.get(Protesto, p_id)
            self.assertEqual(p_check.status, 'EM_VOTACAO', "Ao acessar a Sala dos Juízes, o protesto expirado deve ter sido movido para EM_VOTACAO")


if __name__ == '__main__':
    unittest.main()
