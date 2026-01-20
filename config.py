import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-super-secreta-fullgas-2026'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'f1_league.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # --- CONFIGURAÇÃO DE UPLOAD ---
    # Define a pasta onde as fotos vão ficar
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads')
    # Tamanho máximo do arquivo (ex: 2MB)
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024 
    # Extensões permitidas
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}