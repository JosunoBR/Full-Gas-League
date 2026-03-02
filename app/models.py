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

# Tabela de Associação (Muitos-para-Muitos) entre Pilotos e Equipes
pilot_teams = db.Table('pilot_teams',
    db.Column('pilot_id', db.Integer, db.ForeignKey('pilot_profile.id'), primary_key=True),
    db.Column('team_id', db.Integer, db.ForeignKey('team.id'), primary_key=True)
)

# Tabela de Associação para Reservas Oficiais
pilot_reserves = db.Table('pilot_reserves',
    db.Column('pilot_id', db.Integer, db.ForeignKey('pilot_profile.id'), primary_key=True),
    db.Column('team_id', db.Integer, db.ForeignKey('team.id'), primary_key=True)
)

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    logo_url = db.Column(db.String(200), nullable=True) 
    grid = db.Column(db.String(20), nullable=False) 
    season_id = db.Column(db.Integer, db.ForeignKey('season.id'), nullable=True) # Vincula equipe à temporada
    
    # NOVA ESTRUTURA: Grid via ID
    grid_id = db.Column(db.Integer, db.ForeignKey('grid_config.id'), nullable=True)
    ativa = db.Column(db.Boolean, default=True) 
    
    results = db.relationship('RaceResult', backref='team_snapshot', lazy=True)
    
    # Relacionamento para Reservas (separado dos titulares)
    reserves = db.relationship('PilotProfile', secondary=pilot_reserves, lazy='subquery',
        backref=db.backref('reserve_teams', lazy=True))
        
    # Relacionamento com a Configuração do Grid
    grid_config = db.relationship('GridConfig', backref='teams')

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
    grid = db.Column(db.String(200), nullable=False, default='SEM_GRID') 
    
    telefone = db.Column(db.String(20), nullable=True)
    pontos_cnh = db.Column(db.Integer, default=25)
    advertencias_acumuladas = db.Column(db.Integer, default=0)
    
    penalidade_campeonato = db.Column(db.Float, default=0.0)
    motivo_penalidade = db.Column(db.Text, nullable=True)

    # Relacionamento Muitos-para-Muitos (Um piloto pode ter várias equipes, uma por grid)
    # O backref 'pilots' permite acessar team.pilots
    teams = db.relationship('Team', secondary=pilot_teams, lazy='subquery',
        backref=db.backref('pilots', lazy=True))

    race_results = db.relationship('RaceResult', backref='pilot', lazy=True, cascade="all, delete-orphan")
    grid_photos = db.relationship('PilotGridPhoto', backref='pilot', lazy=True)
    
    def esta_banido(self):
        return self.pontos_cnh <= 0

    def get_cnh_info(self, season_id, grid_id):
        """
        Calcula a CNH e Advertências para um contexto específico (Temporada + Grid).
        Retorna um dicionário: {'cnh': int, 'advertencias': int}
        """
        # Imports locais para evitar dependência circular
        from app.models import Protesto, RaceResult, Race
        
        cnh = 25
        adv_count = 0
        
        # 1. Protestos (Punições e Advertências)
        protestos = Protesto.query.join(Race).filter(
            Protesto.acusado_id == self.id,
            Protesto.status == 'CONCLUIDO',
            Race.season_id == season_id,
            Race.grid_id == grid_id
        ).all()
        
        for p in protestos:
            v = p.veredito_final
            if v == 'LEVE': cnh -= 3
            elif v == 'MEDIA': cnh -= 5
            elif v == 'GRAVE': cnh -= 10
            elif v == 'ADVERTENCIA': adv_count += 1
            
        # Regra de Advertência: A cada 3 acumuladas, perde 3 pontos
        cnh -= (adv_count // 3) * 3
        
        # 2. Descontos por W.O. (FNJ)
        fnjs = RaceResult.query.join(Race).filter(RaceResult.pilot_id == self.id, RaceResult.ausencia == 'FNJ', Race.season_id == season_id, Race.grid_id == grid_id).count()
        cnh -= (fnjs * 2)
        
        return {'cnh': cnh, 'advertencias': adv_count}

    def to_dict(self):
        return {
            'id': self.id,
            'nickname': self.nickname,
            'grid': self.grid,
            'telefone': self.telefone,
            'cnh': self.pontos_cnh,
            'equipes': [t.nome for t in self.teams],
            'foto': self.foto_url
        }

class PilotGridPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pilot_id = db.Column(db.Integer, db.ForeignKey('pilot_profile.id'), nullable=False)
    grid = db.Column(db.String(50), nullable=False)
    foto_url = db.Column(db.String(200), nullable=False)

class Season(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    ativa = db.Column(db.Boolean, default=True)
    data_inicio = db.Column(db.Date, nullable=False)
    races = db.relationship('Race', backref='season', lazy=True, cascade="all, delete-orphan")
    # FIX: Equipes agora são filhas da temporada. Se apagar a temporada, apaga as equipes.
    teams = db.relationship('Team', backref='season', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'ativa': self.ativa
        }

class SeasonChampion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('season.id'), nullable=False)
    grid = db.Column(db.String(50), nullable=False)
    
    # NOVA ESTRUTURA
    grid_id = db.Column(db.Integer, db.ForeignKey('grid_config.id'), nullable=True)
    category = db.Column(db.String(20), nullable=False) # 'PILOT' ou 'CONSTRUCTOR'
    position = db.Column(db.Integer, nullable=False) # 1, 2, 3
    
    # Dados Congelados (Snapshot)
    name = db.Column(db.String(100), nullable=False) # Nickname ou Nome da Equipe
    team_name = db.Column(db.String(100), nullable=True) # Para pilotos
    image_url = db.Column(db.String(200), nullable=True) # Foto Piloto ou Logo Equipe
    team_logo_url = db.Column(db.String(200), nullable=True) # Logo da equipe do piloto
    
    pontos = db.Column(db.Float, default=0.0)
    vitorias = db.Column(db.Integer, default=0)
    grid_config = db.relationship('GridConfig')
    
    season = db.relationship('Season', backref='champions', cascade="all, delete")

class Race(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('season.id'), nullable=False)
    nome_gp = db.Column(db.String(100), nullable=False)
    pista = db.Column(db.String(100), nullable=False)
    data_corrida = db.Column(db.Date, nullable=True)
    grid = db.Column(db.String(20), nullable=False)
    
    # NOVA ESTRUTURA: Grid via ID
    grid_id = db.Column(db.Integer, db.ForeignKey('grid_config.id'), nullable=True)
    status = db.Column(db.String(20), default='Agendada')
    tipo_etapa = db.Column(db.String(20), default='NORMAL')
    
    results = db.relationship('RaceResult', backref='race', lazy=True, cascade="all, delete-orphan")
    
    # Relacionamentos para garantir limpeza em cascata
    registrations = db.relationship('RaceRegistration', backref='race_parent', lazy=True, cascade="all, delete-orphan")
    protestos = db.relationship('Protesto', back_populates='etapa', lazy=True, cascade="all, delete-orphan")

    grid_config = db.relationship('GridConfig', backref='races')

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
    etapa = db.relationship('Race', back_populates='protestos')
    grid_id = db.Column(db.Integer, db.ForeignKey('grid_config.id'), nullable=True)
    grid_rel = db.relationship('GridConfig')
    acusador_id = db.Column(db.Integer, db.ForeignKey('pilot_profile.id'), nullable=False)
    acusador = db.relationship('PilotProfile', foreign_keys=[acusador_id], backref=db.backref('protestos_feitos', cascade="all, delete-orphan"))
    acusado_id = db.Column(db.Integer, db.ForeignKey('pilot_profile.id'), nullable=False)
    acusado = db.relationship('PilotProfile', foreign_keys=[acusado_id], backref=db.backref('protestos_recebidos', cascade="all, delete-orphan"))
    
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

    votos = db.relationship('VotoComissario', backref='protesto_rel', lazy=True, cascade="all, delete-orphan")

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



class GridConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('season.id'), nullable=True)
    nome = db.Column(db.String(50), nullable=False)
    vagas = db.Column(db.Integer, nullable=False, default=20)
    ordem = db.Column(db.Integer, default=0)
    exibir_lastro = db.Column(db.Boolean, default=True)

    season_rel = db.relationship('Season', backref=db.backref('grid_configs', cascade="all, delete-orphan"))


# === REGISTRO DOS LISTENERS DE AUDITORIA ===
# agora que todo modelo foi definido, associamos os eventos
for _cls in (PilotProfile, Team, Race, Protesto, Season, GridConfig):
    event.listen(_cls, 'after_insert', _log_insert)
    event.listen(_cls, 'after_update', _log_update)
    event.listen(_cls, 'after_delete', _log_delete)