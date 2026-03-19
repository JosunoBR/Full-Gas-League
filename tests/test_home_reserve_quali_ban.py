import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime

from flask import Flask
from flask_login import LoginManager
from flask_jwt_extended import JWTManager

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.models import GridConfig, PilotProfile, Protesto, Race, Season, Team, User, db
from app.routes.admin import admin_bp
from app.routes.public import public_bp
from app.services.standings_service import StandingsService


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

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    return app


class HomeReserveQualiBanTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix='fullgas-home-quali-')
        self.db_path = os.path.join(self.temp_dir, 'test_home.db')
        self.upload_dir = os.path.join(self.temp_dir, 'uploads')
        os.makedirs(self.upload_dir, exist_ok=True)

        self.app = create_test_app(f'sqlite:///{self.db_path}', self.upload_dir)
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            self._seed_data()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _seed_data(self):
        season = Season(nome='Temporada Home Teste', ativa=True, data_inicio=date(2026, 3, 1))
        db.session.add(season)
        db.session.flush()

        grid = GridConfig(season_id=season.id, nome='RIVALS', vagas=20, ordem=1)
        db.session.add(grid)
        db.session.flush()

        reserve_user = User(username='reservaqb', email='reservaqb@test.local', role='PILOTO')
        reserve_user.set_password('123456')
        db.session.add(reserve_user)
        db.session.flush()

        reserve_pilot = PilotProfile(
            user_id=reserve_user.id,
            nickname='Reserva QB',
            nome_real='Piloto Reserva',
            grid=str(grid.id),
        )
        db.session.add(reserve_pilot)
        db.session.flush()

        team = Team(
            nome='Equipe Reserva',
            grid='RIVALS',
            grid_id=grid.id,
            season_id=season.id,
            ativa=True,
        )
        db.session.add(team)
        db.session.flush()
        team.reserves.append(reserve_pilot)

        race = Race(
            season_id=season.id,
            nome_gp='GP Home Teste',
            pista='Bahrain',
            data_corrida=date(2026, 3, 10),
            grid='RIVALS',
            grid_id=grid.id,
            status='Concluida',
        )
        db.session.add(race)
        db.session.flush()

        protest = Protesto(
            etapa_id=race.id,
            grid_id=grid.id,
            acusador_id=reserve_pilot.id,
            acusado_id=reserve_pilot.id,
            video_link='https://youtube.com/watch?v=teste',
            minuto='01:23',
            descricao='Punição para ativar Quali Ban',
            status='CONCLUIDO',
            veredito_final='MEDIA',
            justificativa_texto='Teste de Quali Ban para reserva',
            data_criacao=datetime.utcnow(),
            data_fechamento=datetime.utcnow(),
        )
        db.session.add(protest)
        db.session.commit()

        self.season_id = season.id
        self.grid_id = grid.id
        self.pilot_id = reserve_pilot.id

    def test_reserve_quali_ban_is_present_in_home_data_and_page(self):
        with self.app.app_context():
            home_data = StandingsService.get_home_data(self.season_id)
            reserve_row = next(
                row for row in home_data['standings'][self.grid_id]
                if row['piloto']['id'] == self.pilot_id
            )
            carousel_row = next(
                item for item in home_data['pilots_by_grid'][self.grid_id]
                if item['data']['id'] == self.pilot_id
            )

        self.assertTrue(reserve_row['is_reserve'])
        self.assertTrue(reserve_row['quali_ban'])
        self.assertTrue(carousel_row['is_reserve'])
        self.assertTrue(carousel_row['quali_ban'])

        response = self.client.get(f'/?s={self.season_id}')
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Reserva QB', html)
        self.assertIn('QUALI BAN', html)
        self.assertIn('RESERVA', html)


if __name__ == '__main__':
    unittest.main()
