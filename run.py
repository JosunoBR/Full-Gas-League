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
from sqlalchemy import text
import os
from datetime import datetime, timezone, timedelta

# Configuração do App
app = Flask(__name__, template_folder='app/templates', static_folder='app/static')
app.config.from_object(Config)

# Copy default pilot profile photo to NP.jpg if it doesn't exist
try:
    static_img_dir = os.path.join(app.static_folder, 'img')
    os.makedirs(static_img_dir, exist_ok=True)
    default_img_path = os.path.join(static_img_dir, 'NP.jpg')
    if not os.path.exists(default_img_path):
        src_image = r"C:\Users\Josué\.gemini\antigravity-ide\brain\8b04a6c0-e451-43f8-ae95-47880bb0dad9\media__1783902550571.jpg"
        if os.path.exists(src_image):
            import shutil
            shutil.copy(src_image, default_img_path)
            print("Successfully copied default pilot profile photo to NP.jpg")
except Exception as e:
    print(f"Error copying default pilot profile photo: {e}")

# Inicialização do Banco de Dados
db.init_app(app)

UPLOAD_FOLDER = app.config.get('UPLOAD_FOLDER')
if UPLOAD_FOLDER:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Habilita o CORS para permitir que o App acesse a API
CORS(app)

# Configuração JWT (Segurança do App)
app.config["JWT_SECRET_KEY"] = "fullgas-app-secret-key-2024"  # Troque por algo seguro em produção
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
    # Criação das Tabelas e Admin Inicial (Executado apenas ao rodar o servidor)
    with app.app_context():
        db.create_all() 

        # Verifica se coluna exibir_home existe na tabela season
        try:
            db.session.execute(text("SELECT exibir_home FROM season LIMIT 1"))
        except Exception:
            db.session.rollback()
            try:
                db.session.execute(text("ALTER TABLE season ADD COLUMN exibir_home INTEGER DEFAULT 1 NOT NULL"))
                db.session.commit()
                print("Successfully added column exibir_home to season table")
            except Exception as e:
                db.session.rollback()
                print(f"Error adding exibir_home column: {e}")
        
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

    app.run(debug=True, host='0.0.0.0')
