from datetime import datetime
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='PILOTO') 
    
    pilot_profile = db.relationship('PilotProfile', backref='user', uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    logo_url = db.Column(db.String(200), nullable=True) 
    grid = db.Column(db.String(20), nullable=False) 
    ativa = db.Column(db.Boolean, default=True) 
    
    pilots = db.relationship('PilotProfile', back_populates='team')
    results = db.relationship('RaceResult', backref='team_snapshot', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'logo': self.logo_url,
            'grid': self.grid
        }

class PilotProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    nickname = db.Column(db.String(50), nullable=False)
    nome_real = db.Column(db.String(100), nullable=False)
    foto_url = db.Column(db.String(200), nullable=True)
    grid = db.Column(db.String(20), nullable=False) 
    
    telefone = db.Column(db.String(20), nullable=True)
    pontos_cnh = db.Column(db.Integer, default=25)
    advertencias_acumuladas = db.Column(db.Integer, default=0)
    
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)
    team = db.relationship('Team', back_populates='pilots')

    race_results = db.relationship('RaceResult', backref='pilot', lazy=True)
    
    def esta_banido(self):
        return self.pontos_cnh <= 0

    def to_dict(self):
        return {
            'id': self.id,
            'nickname': self.nickname,
            'grid': self.grid,
            'telefone': self.telefone,
            'cnh': self.pontos_cnh,
            'equipe': self.team.nome if self.team else 'Sem Equipe',
            'foto': self.foto_url
        }

class Season(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    ativa = db.Column(db.Boolean, default=True)
    data_inicio = db.Column(db.Date, nullable=False)
    races = db.relationship('Race', backref='season', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'ativa': self.ativa
        }

class Race(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('season.id'), nullable=False)
    nome_gp = db.Column(db.String(100), nullable=False)
    pista = db.Column(db.String(100), nullable=False)
    data_corrida = db.Column(db.Date, nullable=True)
    grid = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='Agendada')
    tipo_etapa = db.Column(db.String(20), default='NORMAL')
    
    results = db.relationship('RaceResult', backref='race', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nome_gp': self.nome_gp,
            'pista': self.pista,
            'data': self.data_corrida.strftime('%d/%m/%Y') if self.data_corrida else 'TBA',
            'grid': self.grid,
            'status': self.status,
            'tipo': self.tipo_etapa
        }

class RaceRegistration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(db.Integer, db.ForeignKey('race.id'), nullable=False)
    pilot_id = db.Column(db.Integer, db.ForeignKey('pilot_profile.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    justificativa = db.Column(db.Text, nullable=True)
    data_resposta = db.Column(db.DateTime, default=datetime.utcnow)

class RaceResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(db.Integer, db.ForeignKey('race.id'), nullable=False)
    pilot_id = db.Column(db.Integer, db.ForeignKey('pilot_profile.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)
    
    posicao = db.Column(db.Integer, default=0)
    pontos_ganhos = db.Column(db.Float, default=0.0)
    
    volta_rapida = db.Column(db.Boolean, default=False)
    piloto_do_dia = db.Column(db.Boolean, default=False)
    piloto_torcida = db.Column(db.Boolean, default=False)
    
    dnf = db.Column(db.Boolean, default=False) 
    dsq = db.Column(db.Boolean, default=False)
    ausencia = db.Column(db.String(10), nullable=True)

    def to_dict(self):
        return {
            'posicao': self.posicao,
            'pontos': self.pontos_ganhos,
            'piloto': self.pilot.nickname,
            'equipe': self.team_snapshot.nome if self.team_snapshot else 'N/A',
            'dnf': self.dnf,
            'dsq': self.dsq,
            'vr': self.volta_rapida,
            'dotd': self.piloto_do_dia
        }

class Protesto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    etapa_id = db.Column(db.Integer, db.ForeignKey('race.id'), nullable=False)
    etapa = db.relationship('Race')
    acusador_id = db.Column(db.Integer, db.ForeignKey('pilot_profile.id'), nullable=False)
    acusador = db.relationship('PilotProfile', foreign_keys=[acusador_id])
    acusado_id = db.Column(db.Integer, db.ForeignKey('pilot_profile.id'), nullable=False)
    acusado = db.relationship('PilotProfile', foreign_keys=[acusado_id])
    
    video_link = db.Column(db.String(300), nullable=True)
    minuto = db.Column(db.String(50), nullable=True)
    descricao = db.Column(db.Text, nullable=True)
    video_defesa = db.Column(db.String(300), nullable=True)
    argumento_defesa = db.Column(db.Text, nullable=True)
    
    status = db.Column(db.String(50), default='AGUARDANDO_DEFESA') 
    veredito_final = db.Column(db.String(50), nullable=True)
    justificativa_texto = db.Column(db.Text, nullable=True)
    
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_fechamento = db.Column(db.DateTime, nullable=True)

class VotoComissario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    protesto_id = db.Column(db.Integer, db.ForeignKey('protesto.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    escolha = db.Column(db.String(50), nullable=False)

class Invite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(10), unique=True, nullable=False)
    email = db.Column(db.String(150), nullable=True)
    used = db.Column(db.Boolean, default=False)

class SeletivaEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pilot_id = db.Column(db.Integer, db.ForeignKey('pilot_profile.id'), nullable=False)
    tempo_ms = db.Column(db.Integer, nullable=False) # Tempo em milissegundos para ordenação
    tempo_str = db.Column(db.String(20), nullable=False) # Texto original (ex: 1:35.800)
    data_registro = db.Column(db.DateTime, default=datetime.utcnow)
    
    piloto = db.relationship('PilotProfile', backref='seletivas')

class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    subtitulo = db.Column(db.String(300))
    texto = db.Column(db.Text, nullable=False)
    imagem_url = db.Column(db.String(200)) 
    data_publicacao = db.Column(db.DateTime, default=datetime.utcnow)
    autor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    autor = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'titulo': self.titulo,
            'subtitulo': self.subtitulo,
            'imagem': self.imagem_url,
            'data': self.data_publicacao.strftime('%d/%m/%Y'),
            'texto': self.texto
        }