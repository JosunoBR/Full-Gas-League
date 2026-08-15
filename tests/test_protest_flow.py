import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta

from flask import Flask
from flask_login import LoginManager
from flask_jwt_extended import JWTManager

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.models import (
    HomeCache,
    GridConfig,
    PilotProfile,
    Protesto,
    Race,
    RaceResult,
    Season,
    SeasonChampion,
    Team,
    User,
    VotoComissario,
    db,
)
from app.routes.admin import admin_bp
from app.routes.public import public_bp
from app.services.discipline_service import DisciplineService
from app.services.scoring_service import ScoringService


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


class ProtestFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix='fullgas-protests-')
        self.db_path = os.path.join(self.temp_dir, 'test_protests.db')
        self.upload_dir = os.path.join(self.temp_dir, 'uploads')
        os.makedirs(self.upload_dir, exist_ok=True)

        self.app = create_test_app(f'sqlite:///{self.db_path}', self.upload_dir)
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            self._seed_base_data()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _seed_base_data(self):
        season = Season(nome='Temporada Teste', ativa=True, data_inicio=date(2026, 3, 1))
        db.session.add(season)
        db.session.flush()

        grid = GridConfig(season_id=season.id, nome='ELITE', vagas=20, ordem=1)
        db.session.add(grid)
        db.session.flush()

        super_admin = User(username='direcao', email='direcao@test.local', role='SUPER_ADM')
        super_admin.set_password('123456')
        accuser_user = User(username='acusador', email='acusador@test.local', role='PILOTO')
        accuser_user.set_password('123456')
        accused_user = User(username='acusado', email='acusado@test.local', role='PILOTO')
        accused_user.set_password('123456')
        voter_user = User(username='comissario', email='comissario@test.local', role='ADM')
        voter_user.set_password('123456')
        db.session.add_all([super_admin, accuser_user, accused_user, voter_user])
        db.session.flush()

        super_admin_profile = PilotProfile(
            user_id=super_admin.id,
            nickname='Direcao',
            nome_real='Direcao de Prova',
            grid='SEM_GRID',
        )
        accuser_profile = PilotProfile(
            user_id=accuser_user.id,
            nickname='Acusador',
            nome_real='Piloto Acusador',
            grid=str(grid.id),
        )
        accused_profile = PilotProfile(
            user_id=accused_user.id,
            nickname='Acusado',
            nome_real='Piloto Acusado',
            grid=str(grid.id),
        )
        voter_profile = PilotProfile(
            user_id=voter_user.id,
            nickname='Comissario',
            nome_real='Comissario ADM',
            grid='SEM_GRID',
        )
        db.session.add_all([super_admin_profile, accuser_profile, accused_profile, voter_profile])
        db.session.flush()

        team = Team(
            nome='Equipe Teste',
            grid='ELITE',
            season_id=season.id,
            grid_id=grid.id,
            ativa=True,
        )
        team.pilots.append(accused_profile)
        team.reserves.append(accuser_profile)
        db.session.add(team)
        db.session.flush()

        race = Race(
            season_id=season.id,
            nome_gp='GP de Teste',
            pista='Interlagos',
            data_corrida=date.today() - timedelta(days=1),
            grid='ELITE',
            grid_id=grid.id,
            status='Concluida',
        )
        db.session.add(race)
        db.session.flush()

        race_result = RaceResult(
            race_id=race.id,
            pilot_id=accused_profile.id,
            team_id=team.id,
            posicao=1,
            pontos_ganhos=18.0,
            status_presenca='OK',
        )
        cache = HomeCache(season_id=season.id, data_json='{}')
        protest = Protesto(
            etapa_id=race.id,
            grid_id=grid.id,
            acusador_id=accuser_profile.id,
            acusado_id=accused_profile.id,
            video_link='https://youtube.com/watch?v=acusacao',
            minuto='12:34',
            descricao='Toque na curva 1',
            status='AGUARDANDO_DEFESA',
            data_criacao=datetime.utcnow(),
        )
        db.session.add_all([race_result, cache, protest])
        db.session.commit()

        self.season_id = season.id
        self.grid_id = grid.id
        self.race_id = race.id
        self.protest_id = protest.id
        self.super_admin_user_id = super_admin.id
        self.accuser_user_id = accuser_user.id
        self.accused_user_id = accused_user.id
        self.voter_user_id = voter_user.id
        self.accuser_pilot_id = accuser_profile.id
        self.accused_pilot_id = accused_profile.id
        self.team_id = team.id

    def _login_as(self, user_id):
        with self.client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True

    def _reload_protest(self):
        with self.app.app_context():
            return db.session.get(Protesto, self.protest_id)

    def test_open_protest_starts_waiting_for_defense_and_copies_grid_id(self):
        with self.app.app_context():
            before_count = Protesto.query.count()

        self._login_as(self.accuser_user_id)
        response = self.client.post(
            '/protestar',
            data={
                'race_id': self.race_id,
                'acusado_id': self.accused_pilot_id,
                'video': 'https://youtube.com/watch?v=novo-protesto',
                'minuto': '03:21',
                'descricao': 'Nova ocorrencia para validar abertura',
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            after_count = Protesto.query.count()
            newest = Protesto.query.order_by(Protesto.id.desc()).first()

        self.assertEqual(after_count, before_count + 1)
        self.assertEqual(newest.grid_id, self.grid_id)
        self.assertEqual(newest.status, 'AGUARDANDO_DEFESA')
        self.assertEqual(newest.acusador_id, self.accuser_pilot_id)

    def test_submit_defense_moves_protest_to_voting(self):
        self._login_as(self.accused_user_id)
        response = self.client.post(
            f'/defender/{self.protest_id}',
            data={
                'video_defesa': 'https://youtube.com/watch?v=defesa',
                'argumento_defesa': 'Houve perda de aderencia, sem dolo.',
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)

        protest = self._reload_protest()
        self.assertEqual(protest.status, 'EM_VOTACAO')
        self.assertEqual(protest.video_defesa, 'https://youtube.com/watch?v=defesa')
        self.assertEqual(protest.argumento_defesa, 'Houve perda de aderencia, sem dolo.')

    def test_super_admin_can_vote_close_with_current_form_names_and_reopen(self):
        with self.app.app_context():
            protest = db.session.get(Protesto, self.protest_id)
            protest.video_defesa = 'https://youtube.com/watch?v=defesa'
            protest.argumento_defesa = 'Defesa apresentada.'
            protest.status = 'EM_VOTACAO'
            db.session.commit()

        self._login_as(self.voter_user_id)
        vote_response = self.client.post(
            f'/admin/protests/{self.protest_id}',
            data={'voto': 'MEDIA'},
            follow_redirects=False,
        )
        self.assertEqual(vote_response.status_code, 302)

        with self.app.app_context():
            votes = VotoComissario.query.filter_by(protesto_id=self.protest_id).all()
        self.assertEqual(len(votes), 1)
        self.assertEqual(votes[0].escolha, 'MEDIA')

        self._login_as(self.super_admin_user_id)
        close_response = self.client.post(
            f'/admin/protests/{self.protest_id}',
            data={
                'encerrar': 'true',
                'veredito_final': 'MEDIA',
                'justificativa': 'Responsavel pelo toque e pela perda de posicao.',
            },
            follow_redirects=False,
        )
        self.assertEqual(close_response.status_code, 302)
        self.assertIn('/admin/protests', close_response.headers.get('Location', ''))

        with self.app.app_context():
            protest = db.session.get(Protesto, self.protest_id)
            cache_count = HomeCache.query.filter_by(season_id=self.season_id).count()
            closed_points = ScoringService.calculate_pilot_total_points(
                self.accused_pilot_id, self.season_id, self.grid_id
            )
            closed_discipline = DisciplineService.get_pilot_discipline_stats(
                self.accused_pilot_id, self.season_id, self.grid_id
            )
            closed_quali_ban = DisciplineService.is_quali_banned(self.accused_pilot_id, self.grid_id)

        self.assertEqual(protest.status, 'CONCLUIDO')
        self.assertEqual(protest.veredito_final, 'MEDIA')
        self.assertIsNotNone(protest.data_fechamento)
        self.assertEqual(cache_count, 0)
        self.assertEqual(closed_points, 13.0)
        self.assertEqual(closed_discipline['cnh'], 20)
        self.assertEqual(closed_discipline['advertencias'], 0)
        self.assertTrue(closed_quali_ban)

        reopen_response = self.client.post(
            f'/admin/protests/{self.protest_id}',
            data={'reabrir': 'true'},
            follow_redirects=False,
        )
        self.assertEqual(reopen_response.status_code, 302)

        with self.app.app_context():
            reopened = db.session.get(Protesto, self.protest_id)
            reopened_points = ScoringService.calculate_pilot_total_points(
                self.accused_pilot_id, self.season_id, self.grid_id
            )
            reopened_discipline = DisciplineService.get_pilot_discipline_stats(
                self.accused_pilot_id, self.season_id, self.grid_id
            )
            reopened_quali_ban = DisciplineService.is_quali_banned(self.accused_pilot_id, self.grid_id)

        self.assertEqual(reopened.status, 'EM_VOTACAO')
        self.assertIsNone(reopened.veredito_final)
        self.assertIsNone(reopened.justificativa_texto)
        self.assertIsNone(reopened.data_fechamento)
        self.assertEqual(reopened_points, 18.0)
        self.assertEqual(reopened_discipline['cnh'], 25)
        self.assertEqual(reopened_discipline['advertencias'], 0)
        self.assertFalse(reopened_quali_ban)

    def test_close_requires_valid_verdict(self):
        self._login_as(self.super_admin_user_id)
        response = self.client.post(
            f'/admin/protests/{self.protest_id}',
            data={
                'encerrar': 'true',
                'veredito_final': 'INVALIDO',
                'justificativa': 'Tentativa invalida.',
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)

        protest = self._reload_protest()
        self.assertEqual(protest.status, 'AGUARDANDO_DEFESA')
        self.assertIsNone(protest.veredito_final)
        self.assertIsNone(protest.data_fechamento)

    def test_close_season_blocks_when_protest_is_still_open(self):
        self._login_as(self.super_admin_user_id)
        response = self.client.post(
            f'/admin/season/{self.season_id}/close',
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(f'/admin/seasons/{self.season_id}', response.headers.get('Location', ''))

        with self.app.app_context():
            season = db.session.get(Season, self.season_id)
            team = db.session.get(Team, self.team_id)
            accused = db.session.get(PilotProfile, self.accused_pilot_id)
            champions_count = SeasonChampion.query.filter_by(season_id=self.season_id).count()

        self.assertTrue(season.ativa)
        self.assertEqual(champions_count, 0)
        self.assertTrue(team.ativa)
        self.assertEqual(accused.grid, str(self.grid_id))
        self.assertIn(team.id, [t.id for t in accused.teams])

    def test_close_season_unlinks_team_and_grid_after_protests_are_resolved(self):
        with self.app.app_context():
            protest = db.session.get(Protesto, self.protest_id)
            protest.status = 'CONCLUIDO'
            protest.veredito_final = 'INOCENTE'
            protest.justificativa_texto = 'Caso encerrado para liberar fechamento.'
            protest.data_fechamento = datetime.utcnow()
            db.session.commit()

        self._login_as(self.super_admin_user_id)
        response = self.client.post(
            f'/admin/season/{self.season_id}/close',
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/seasons', response.headers.get('Location', ''))

        with self.app.app_context():
            season = db.session.get(Season, self.season_id)
            team = db.session.get(Team, self.team_id)
            accused = db.session.get(PilotProfile, self.accused_pilot_id)
            accuser = db.session.get(PilotProfile, self.accuser_pilot_id)
            champions_count = SeasonChampion.query.filter_by(season_id=self.season_id).count()
            accused_team_ids = [t.id for t in accused.teams]
            accuser_reserve_team_ids = [t.id for t in accuser.reserve_teams]

        self.assertFalse(season.ativa)
        self.assertFalse(team.ativa)
        self.assertEqual(accused.grid, 'SEM_GRID')
        self.assertEqual(accuser.grid, 'SEM_GRID')
        self.assertEqual(accused_team_ids, [])
        self.assertEqual(accuser_reserve_team_ids, [])
        self.assertGreater(champions_count, 0)

    def test_open_protest_rejects_closed_season_even_with_direct_post(self):
        with self.app.app_context():
            season = db.session.get(Season, self.season_id)
            season.ativa = False
            db.session.commit()
            before_count = Protesto.query.count()

        self._login_as(self.accuser_user_id)
        response = self.client.post(
            '/protestar',
            data={
                'race_id': self.race_id,
                'acusado_id': self.accused_pilot_id,
                'video': 'https://youtube.com/watch?v=fechado',
                'minuto': '09:99',
                'descricao': 'Nao deveria abrir em temporada fechada',
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            after_count = Protesto.query.count()

        self.assertEqual(after_count, before_count)


if __name__ == '__main__':
    unittest.main()
