import os
from datetime import datetime, timedelta, timezone
from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate  # NOVO
from flask_cors import CORS # Essencial para o App
from flask_jwt_extended import JWTManager # NOVO: Autenticação do App
from app.models import db, User, PilotProfile
from app.routes.public import public_bp
from app.routes.admin import admin_bp
from app.routes.api import api_bp # Importa a nova API
from config import Config
from sqlalchemy import text, event
from sqlalchemy.engine import Engine

# Inicialização da aplicação Flask
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, 
            template_folder=os.path.join(basedir, 'app', 'templates'), 
            static_folder=os.path.join(basedir, 'app', 'static'))
app.config.from_object(Config)

# Previne 'database is locked' configurando WAL e timeout no conector do SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if type(dbapi_connection).__module__ in ('sqlite3', 'pysqlite2.dbapi2'):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=DELETE")
            cursor.execute("PRAGMA busy_timeout=30000")
        except Exception:
            pass
        finally:
            cursor.close()

# Inicialização do Banco de Dados
db.init_app(app)

def init_schema():
    with app.app_context():
        try:
            # Verifica se coluna exibir_home existe na tabela season
            try:
                db.session.execute(text("SELECT exibir_home FROM season LIMIT 1"))
            except Exception:
                db.session.rollback()
                try:
                    db.session.execute(text("ALTER TABLE season ADD COLUMN exibir_home INTEGER DEFAULT 1 NOT NULL"))
                    db.session.commit()
                except Exception:
                    db.session.rollback()

            novas_colunas = [
                ("grid_largada", "INTEGER"),
                ("tempo_total", "VARCHAR(30)"),
                ("melhor_volta", "VARCHAR(20)"),
                ("tempo_qualy", "VARCHAR(20)"),
                ("pit_stops", "INTEGER DEFAULT 0"),
                ("pneus_stints", "VARCHAR(50)"),
                ("penalidades_texto", "VARCHAR(100)"),
                ("posicao_sprint", "INTEGER"),
                ("pontos_sprint", "FLOAT DEFAULT 0.0"),
                ("tempo_sprint", "VARCHAR(30)"),
                ("melhor_volta_sprint", "VARCHAR(20)")
            ]
            for col_nome, col_tipo in novas_colunas:
                try:
                    db.session.execute(text(f"SELECT {col_nome} FROM race_result LIMIT 1"))
                except Exception:
                    db.session.rollback()
                    try:
                        db.session.execute(text(f"ALTER TABLE race_result ADD COLUMN {col_nome} {col_tipo}"))
                        db.session.commit()
                    except Exception:
                        db.session.rollback()

            race_novas_colunas = [
                ("sc_vsc_info", "VARCHAR(255)"),
                ("clima_temp", "VARCHAR(100)"),
                ("total_voltas", "INTEGER"),
                ("lobby_settings_json", "TEXT")
            ]
            for col_nome, col_tipo in race_novas_colunas:
                try:
                    db.session.execute(text(f"SELECT {col_nome} FROM race LIMIT 1"))
                except Exception:
                    db.session.rollback()
                    try:
                        db.session.execute(text(f"ALTER TABLE race ADD COLUMN {col_nome} {col_tipo}"))
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
        finally:
            db.session.remove()


UPLOAD_FOLDER = app.config.get('UPLOAD_FOLDER')
if UPLOAD_FOLDER:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Habilita o CORS para permitir que o App acesse a API
CORS(app)

# Configuração JWT (Segurança do App)
app.config["JWT_SECRET_KEY"] = os.environ.get('JWT_SECRET_KEY') or "fullgas-league-jwt-secret-key-2026-production"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=30) # App manterá login por 30 dias
jwt = JWTManager(app)

# Converte o ID do usuário para String ao gerar o Token (Exigência do PyJWT)
@jwt.user_identity_loader
def user_identity_lookup(identity):
    return str(identity)

# Inicialização das Migrações (NOVO)
migrate = Migrate(app, db)

# Configuração de Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'public.login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.context_processor
def inject_now():
    return {
        'now_year': datetime.now(timezone.utc).year,
        'instagram_url': app.config.get('INSTAGRAM_URL'),
        'youtube_url': app.config.get('YOUTUBE_URL'),
        'contact_email': app.config.get('CONTACT_EMAIL')
    }

@app.template_filter('format_datetime')
def format_datetime(value, format="%d/%m/%Y às %H:%M"):
    if value is None:
        return ""
    # Converte de UTC para horário de Brasília (UTC-3)
    local_val = value - timedelta(hours=3)
    return local_val.strftime(format)


# Registro das Rotas (Blueprints)
app.register_blueprint(public_bp)
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(api_bp, url_prefix='/api') # Registra com prefixo /api

if __name__ == '__main__':
    init_schema()
    # Criação das Tabelas e Admin Inicial (Executado apenas ao rodar o servidor)
    with app.app_context():
        # db.create_all() garante que tabelas novas (como pilot_teams) sejam criadas
        db.create_all() 
        
        # Verifica se existe pasta de upload
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])

        # Cria Super Admin se não existir
        admin_user = User.query.filter_by(email='admin@fullgas.com').first()
        if not admin_user:
            admin_user = User(username='Admin', email='admin@fullgas.com', role='SUPER_ADM')
            admin_user.set_password('admin123') # Define a senha ANTES de salvar no banco
            db.session.add(admin_user)
            db.session.flush()
            
            perfil_admin = PilotProfile(user_id=admin_user.id, nickname='Direção de Prova', nome_real='Admin', grid='SEM_GRID')
            db.session.add(perfil_admin)
        
        db.session.commit()
        print("Acesso Admin garantido: admin@fullgas.com / admin123")

        # Aquecimento de Cache da Home para temporadas ativas
        try:
            from app.models import Season
            from app.services.standings_service import StandingsService
            active_seasons = Season.query.filter_by(ativa=True).all()
            for s in active_seasons:
                StandingsService.get_home_data(s.id)
            print("Cache da Home pré-aquecido com sucesso!")
        except Exception as e:
            print(f"Aviso no pré-aquecimento do cache: {e}")

    app.run(debug=True, host='0.0.0.0')

