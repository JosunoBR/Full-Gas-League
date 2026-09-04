import os

# Pega o caminho absoluto da pasta onde este arquivo (config.py) está
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-super-secreta-fullgas-2026'
    # JWT do App (mantem consistente independente do entrypoint)
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'fullgas-league-jwt-secret-key-2026-production'
    
    # Busca dinâmica do banco f1_league.db (compatível com local e PythonAnywhere)
    db_filename = 'f1_league.db'
    possible_paths = [
        os.path.join(basedir, db_filename),
        os.path.join('/home/fullgasleague/Full-Gas-League', db_filename),
        os.path.join('/home/fullgasleague', db_filename),
    ]
    db_path = next((p for p in possible_paths if os.path.exists(p)), os.path.join(basedir, db_filename))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{db_path}'

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Aumenta a tolerância de espera do SQLite para evitar "database is locked"
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'timeout': 60,
            'check_same_thread': False
        }
    }
    
    # --- CONFIGURAÇÃO DE UPLOAD ---
    # Define a pasta onde as fotos vão ficar
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads')
    # Tamanho máximo do arquivo (ex: 2MB)
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024 
    # Extensões permitidas
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

    # --- CONFIGURAÇÃO DE CACHE DE ESTATÍSTICOS / NAVEGADOR ---
    SEND_FILE_MAX_AGE_DEFAULT = 31536000 # 1 ano de cache para assets estáticos no navegador

    # --- REDES SOCIAIS E CONTATO ---
    INSTAGRAM_URL = 'https://www.instagram.com/fullgasleagueofficial/'
    YOUTUBE_URL = 'https://www.youtube.com/@FullGasLeagueF1Oficial'
    CONTACT_EMAIL = 'fullgasracingf1@gmail.com'

    # --- CONFIGURAÇÃO DE E-MAILS (RESEND / SMTP) ---
    RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
    # Remetente padrão oficial (utilize seu domínio configurado no Resend)
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'FullGas League <contato@fullgasleague.com.br>'
    # Para onde vão as respostas quando o piloto clicar em "Responder":
    MAIL_REPLY_TO = os.environ.get('MAIL_REPLY_TO') or 'fullgasracingf1@gmail.com'
    # URL base da aplicação para links em e-mails
    BASE_URL = os.environ.get('BASE_URL') or 'https://fullgasleague.com.br'

