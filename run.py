from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate  # NOVO
from flask_cors import CORS # Essencial para o App
from app.models import db, User, PilotProfile
from app.routes.public import public_bp
from app.routes.admin import admin_bp
from app.routes.api import api_bp # Importa a nova API
from config import Config
import os
from datetime import datetime, timezone

# Configuração do App
app = Flask(__name__, template_folder='app/templates', static_folder='app/static')
app.config.from_object(Config)

# Inicialização do Banco de Dados
db.init_app(app)

# Habilita o CORS para permitir que o App acesse a API
CORS(app)

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
    return {'now_year': datetime.now(timezone.utc).year}

# Registro das Rotas (Blueprints)
app.register_blueprint(public_bp)
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(api_bp, url_prefix='/api') # Registra com prefixo /api

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
        
        # Força a senha padrão para garantir o acesso em ambiente de teste
        # admin_user.set_password('admin123') 
        db.session.commit()
        print("Acesso Admin garantido: admin@fullgas.com / admin123")

    app.run(debug=True)