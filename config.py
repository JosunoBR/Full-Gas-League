import os

# Pega o caminho absoluto da pasta onde este arquivo (config.py) está
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-super-secreta-fullgas-2026'
    # JWT do App (mantem consistente independente do entrypoint)
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'fullgas-app-secret-key-2024'
    
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

    # --- REDES SOCIAIS E CONTATO ---
    INSTAGRAM_URL = 'https://www.instagram.com/fullgasleagueofficial/'
    YOUTUBE_URL = 'https://www.youtube.com/@FullGasLeagueF1Oficial'
    CONTACT_EMAIL = 'fullgasracingf1@gmail.com'
