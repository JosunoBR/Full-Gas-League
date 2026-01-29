import os

# Pega o caminho absoluto da pasta onde este arquivo (config.py) está
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-super-secreta-fullgas-2026'
    
    # No SQLite, o prefixo 'sqlite:///' seguido de um caminho absoluto (que começa com / no Linux) 
    # resulta nas 4 barras necessárias para o PythonAnywhere.
    db_path = os.path.join(basedir, 'f1_league.db')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{db_path}'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # --- CONFIGURAÇÃO DE UPLOAD ---
    # Define a pasta onde as fotos vão ficar
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads')
    # Tamanho máximo do arquivo (ex: 2MB)
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024 
    # Extensões permitidas
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}