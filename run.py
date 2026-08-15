import os
from datetime import datetime, timedelta, timezone
from flask import Flask, request
from flask_login import LoginManager, current_user
from flask_migrate import Migrate  # NOVO
from flask_cors import CORS # Essencial para o App
from flask_jwt_extended import JWTManager # NOVO: Autenticação do App
from app.models import db, User, PilotProfile, AccessLog
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
            db.create_all()
        except Exception:
            pass
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
        'contact_email': app.config.get('CONTACT_EMAIL'),
        'timedelta': timedelta
    }

@app.template_filter('format_datetime')
def format_datetime(value, format="%d/%m/%Y às %H:%M"):
    if value is None:
        return ""
    return value.strftime(format)



@app.before_request
def log_user_access():
    path = request.path
    if path.startswith('/static/') or path.endswith('.ico') or path.endswith('.png') or path.endswith('.jpg'):
        return

    x_platform = request.headers.get('X-Platform', '')
    user_agent = request.headers.get('User-Agent', '')

    if x_platform == 'MobileApp' or 'FullGasApp' in user_agent or path.startswith('/api/'):
        platform = 'APP'
    else:
        platform = 'WEB'

    if path.startswith('/admin/analytics') or '/static/' in path:
        return

    try:
        u_id = current_user.id if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated else None
        
        # Se nao estiver logado na Web, tenta identificar pelo Token JWT do App Mobile
        if not u_id:
            auth_header = request.headers.get('Authorization', '')
            if auth_header and auth_header.startswith('Bearer '):
                try:
                    from flask_jwt_extended import decode_token
                    token = auth_header.split(' ')[1]
                    decoded = decode_token(token)
                    sub = decoded.get('sub')
                    if sub and str(sub).isdigit():
                        u_id = int(sub)
                except Exception:
                    pass

        ip_addr = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip_addr and ',' in ip_addr:
            ip_addr = ip_addr.split(',')[0].strip()

        log_entry = AccessLog(
            platform=platform,
            route=path[:100],
            user_id=u_id,
            ip_address=ip_addr[:45] if ip_addr else None
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception:
        db.session.rollback()


# Registro das Rotas (Blueprints)
app.register_blueprint(public_bp)
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(api_bp, url_prefix='/api')

# Executa inicialização de schema e tabelas no carregamento do WSGI
init_schema()

if __name__ == '__main__':
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

