import os
import secrets
from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from sqlalchemy import func
from app.models import db, User, PilotProfile, Season, Race, RaceResult, Invite, Protesto, VotoComissario, Team, RaceRegistration, SeletivaEntry, News
from app.utils import allowed_file, get_embed_url, PONTUACAO_NORMAL, ORDEM_CARROS

admin_bp = Blueprint('admin', __name__)

# Lista Oficial de Pistas (Referência 2025/2026)
PISTAS_F1 = [
    {"nome": "Circuito Internacional do Bahrein", "gp": "GP do Bahrein"},
    {"nome": "Circuito de Jeddah-Corniche", "gp": "GP da Arábia Saudita"},
    {"nome": "Circuito de Albert Park", "gp": "GP da Austrália"},
    {"nome": "Circuito de Suzuka", "gp": "GP do Japão"},
    {"nome": "Circuito Internacional de Xangai", "gp": "GP da China", "type": "SPRINT"},
    {"nome": "Autódromo Internacional de Miami", "gp": "GP de Miami", "type": "SPRINT"},
    {"nome": "Autódromo Enzo e Dino Ferrari - Imola", "gp": "GP da Emilia-Romagna"},
    {"nome": "Circuito de Mônaco", "gp": "GP de Mônaco"},
    {"nome": "Circuito de Barcelona-Catalunha", "gp": "GP da Espanha"},
    {"nome": "Circuito de Madrid (IFEMA)", "gp": "GP de Madrid"},
    {"nome": "Circuito Gilles Villeneuve", "gp": "GP do Canadá"},
    {"nome": "Red Bull Ring", "gp": "GP da Áustria"},
    {"nome": "Circuito de Silverstone", "gp": "GP da Grã-Bretanha"},
    {"nome": "Hungaroring", "gp": "GP da Hungria"},
    {"nome": "Circuito de Spa-Francorchamps", "gp": "GP da Bélgica", "type": "SPRINT"},
    {"nome": "Circuito de Zandvoort", "gp": "GP da Holanda"},
    {"nome": "Autódromo Nacional de Monza", "gp": "GP da Itália"},
    {"nome": "Circuito Urbano de Baku", "gp": "GP do Azerbaijão"},
    {"nome": "Circuito de Marina Bay", "gp": "GP de Singapura"},
    {"nome": "Circuito das Américas (COTA) - Áustin", "gp": "GP dos Estados Unidos", "type": "SPRINT"},
    {"nome": "Autódromo Hermanos Rodríguez", "gp": "GP da Cidade do México"},
    {"nome": "Autódromo José Carlos Pace", "gp": "GP de São Paulo", "type": "SPRINT"},
    {"nome": "Las Vegas Strip Circuit", "gp": "GP de Las Vegas"},
    {"nome": "Circuito Internacional de Lusail", "gp": "GP do Catar", "type": "SPRINT"},
    {"nome": "Circuito de Yas Marina", "gp": "GP de Abu Dhabi"},
    {"nome": "Autódromo Internacional do Algarve", "gp": "GP de Portugal"},
    {"nome": "Circuito Paul Ricard", "gp": "GP da França"}
]

@admin_bp.before_request
@login_required
def restrict_access():
    if current_user.role not in ['SUPER_ADM', 'ADM']:
        flash('Acesso negado. Área restrita à Direção de Prova.', 'danger')
        return redirect(url_for('public.home'))

# --- DASHBOARD E VISÃO GERAL ---

@admin_bp.route('/dashboard')
def dashboard():
    season_ativa = Season.query.filter_by(ativa=True).first()
    return render_template('admin/dashboard.html', season_ativa=season_ativa)

@admin_bp.route('/overview')
def overview():
    season_ativa = Season.query.filter_by(ativa=True).first()
    dados_grids = {
        'ELITE': {'classificacao': [], 'disciplina': []}, 
        'ADVANCED': {'classificacao': [], 'disciplina': []}, 
        'INITIAL': {'classificacao': [], 'disciplina': []}
    }
    
    if season_ativa:
        # Removemos o filtro de SUPER_ADM para que eles apareçam se tiverem grid definido
        pilotos = PilotProfile.query.join(User).all()
        
        for p in pilotos:
            if p.grid in dados_grids:
                resultados_season = [r for r in p.race_results if r.race.season_id == season_ativa.id]
                pontos = float(sum(r.pontos_ganhos for r in resultados_season))
                vitorias = sum(1 for r in resultados_season if r.posicao == 1 and not r.dsq)
                podios = sum(1 for r in resultados_season if r.posicao in [1, 2, 3] and not r.dsq)
                
                info = {
                    'piloto': p, 
                    'pontos': pontos, 
                    'vitorias': vitorias, 
                    'podios': podios, 
                    'cnh': p.pontos_cnh, 
                    'advertencias': p.advertencias_acumuladas
                }
                dados_grids[p.grid]['classificacao'].append(info)
                dados_grids[p.grid]['disciplina'].append(info)
                
        for grid in dados_grids:
            dados_grids[grid]['classificacao'].sort(key=lambda x: x['pontos'], reverse=True)
            dados_grids[grid]['disciplina'].sort(key=lambda x: x['cnh'])
            
    return render_template('admin/overview.html', dados=dados_grids, season=season_ativa)

@admin_bp.route('/manual')
def manual():
    return render_template('admin/manual.html')

# --- GESTÃO DE NOTÍCIAS ---

@admin_bp.route('/news')
def list_news():
    noticias = News.query.order_by(News.data_publicacao.desc()).all()
    return render_template('admin/news.html', noticias=noticias)

@admin_bp.route('/news/new', methods=['GET', 'POST'])
def create_news():
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        subtitulo = request.form.get('subtitulo')
        texto = request.form.get('texto')
        
        nova_noticia = News(titulo=titulo, subtitulo=subtitulo, texto=texto, autor_id=current_user.id)
        db.session.add(nova_noticia)
        db.session.flush() # Gera o ID para usar no nome do arquivo sem finalizar a transação
        
        if 'foto' in request.files:
            file = request.files['foto']
            if file and file.filename != '' and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                timestamp = int(datetime.utcnow().timestamp())
                nome_arq = f"news_{nova_noticia.id}_{timestamp}.{ext}"
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], nome_arq))
                nova_noticia.imagem_url = nome_arq
        
        db.session.commit()
        flash('Notícia publicada com sucesso!', 'success')
        return redirect(url_for('admin.list_news'))
        
    return render_template('admin/create_news.html')

@admin_bp.route('/news/delete/<int:news_id>', methods=['POST'])
def delete_news(news_id):
    noticia = News.query.get_or_404(news_id)
    if noticia.imagem_url:
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], noticia.imagem_url)
        if os.path.exists(path): os.remove(path)
    db.session.delete(noticia)
    db.session.commit()
    flash('Notícia removida.', 'success')
    return redirect(url_for('admin.list_news'))

# --- GESTÃO DE USUÁRIOS (ADMINS) ---

@admin_bp.route('/users')
def list_admins():
    if current_user.role != 'SUPER_ADM':
        flash('Acesso restrito ao Super Admin.', 'danger')
        return redirect(url_for('admin.dashboard'))
    admins = User.query.filter(User.role.in_(['ADM', 'SUPER_ADM'])).order_by(User.role.desc(), User.username).all()
    return render_template('admin/admin_users.html', admins=admins)

@admin_bp.route('/users/new', methods=['GET', 'POST'])
def create_admin():
    if current_user.role != 'SUPER_ADM':
        flash('Apenas o Dono da Liga pode criar Admins.', 'warning')
        return redirect(url_for('admin.dashboard'))
        
    if request.method == 'POST':
        username = (request.form.get('username') or '')
        email = (request.form.get('email') or '').lower()
        password = request.form.get('password')
        role = request.form.get('role')
        
        if User.query.filter_by(email=email).first():
            flash('Este e-mail já está cadastrado.', 'danger')
        else:
            new_user = User(username=username, email=email, role=role)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.flush() # Gera o ID do usuário sem finalizar a transação
            
            perfil = PilotProfile(user_id=new_user.id, nickname=username[:50], nome_real=username[:100], grid='SEM_GRID')
            db.session.add(perfil)
            db.session.commit() # Salva ambos ou nenhum
                
            flash(f'Usuário Admin {username} criado com sucesso!', 'success')
            return redirect(url_for('admin.list_admins'))
            
    return render_template('admin/create_user.html')

@admin_bp.route('/users/<int:user_id>/reset_password', methods=['POST'])
def reset_admin_password(user_id):
    if current_user.role != 'SUPER_ADM':
        return redirect(url_for('admin.dashboard'))
        
    user = User.query.get_or_404(user_id)
    new_pass = request.form.get('new_password')
    
    if new_pass and new_pass.strip() != "":
        user.set_password(new_pass)
        db.session.commit()
        flash(f'Senha de {user.username} atualizada com sucesso.', 'success')
    else:
        flash('A senha não pode ser vazia.', 'warning')
        
    return redirect(url_for('admin.list_admins'))

@admin_bp.route('/users/<int:user_id>/update_role', methods=['POST'])
def update_admin_role(user_id):
    if current_user.role != 'SUPER_ADM':
        flash('Acesso restrito ao Super Admin.', 'danger')
        return redirect(url_for('admin.dashboard'))
        
    user = User.query.get_or_404(user_id)
    
    # Impede que o Super Admin mude o próprio nível (evita auto-bloqueio)
    if user.id == current_user.id:
        flash('Você não pode alterar seu próprio nível de acesso.', 'warning')
        return redirect(url_for('admin.list_admins'))
        
    new_role = request.form.get('role')
    if new_role in ['ADM', 'SUPER_ADM']:
        user.role = new_role
        db.session.commit()
        flash(f'Nível de acesso de {user.username} atualizado para {new_role}.', 'success')
    else:
        flash('Nível de acesso inválido.', 'danger')
        
    return redirect(url_for('admin.list_admins'))

@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
def delete_admin(user_id):
    if current_user.role != 'SUPER_ADM' or user_id == current_user.id:
        flash('Operação não permitida.', 'danger')
        return redirect(url_for('admin.list_admins'))
    
    # Nota: Para excluir um ADM completamente, idealmente deveria limpar o PilotProfile associado se existir, 
    # mas como é um ADM dummy, deletar o User geralmente resolve se não houver FKs restritivas.
    user = User.query.get_or_404(user_id)
    
    if user.username == 'Admin':
        flash('O Super Admin principal não pode ser excluído.', 'danger')
        return redirect(url_for('admin.list_admins'))

    # Verifica se tem histórico de corrida (para não quebrar pontuação de equipe)
    has_history = False
    if user.pilot_profile:
        if RaceResult.query.filter_by(pilot_id=user.pilot_profile.id).first():
            has_history = True

    if has_history:
        # ANONIMIZAR (Preserva histórico)
        profile = user.pilot_profile
        if profile.foto_url:
            path = os.path.join(current_app.config['UPLOAD_FOLDER'], profile.foto_url)
            if os.path.exists(path): os.remove(path)
            profile.foto_url = None
        
        suffix = secrets.token_hex(4)
        user.username = f"Ex-Admin_{user.id}_{suffix}"
        user.email = f"deleted_{user.id}_{suffix}@fullgas.local"
        user.set_password(secrets.token_hex(16))
        user.role = 'INATIVO'
        
        profile.nickname = "Usuário Removido"
        profile.nome_real = "Dados Removidos"
        profile.team_id = None
        RaceRegistration.query.filter_by(pilot_id=profile.id).delete()
        
        db.session.commit()
        flash('Administrador possuía histórico. Conta anonimizada para preservar pontuação das equipes.', 'warning')
        
    else:
        # EXCLUSÃO TOTAL (Sem histórico)
        if user.pilot_profile:
            profile = user.pilot_profile
            if profile.foto_url:
                path = os.path.join(current_app.config['UPLOAD_FOLDER'], profile.foto_url)
                if os.path.exists(path): os.remove(path)
            
            # Limpa dependências
            profile.team_id = None
            RaceResult.query.filter_by(pilot_id=profile.id).delete()
            RaceRegistration.query.filter_by(pilot_id=profile.id).delete()
            
            protestos = Protesto.query.filter((Protesto.acusador_id == profile.id) | (Protesto.acusado_id == profile.id)).all()
            for p in protestos:
                VotoComissario.query.filter_by(protesto_id=p.id).delete()
                db.session.delete(p)
            
            db.session.delete(profile)
        
        db.session.delete(user)
        db.session.commit()
        flash('Administrador removido.', 'success')
        
    return redirect(url_for('admin.list_admins'))

# --- GESTÃO DE TEMPORADAS E CORRIDAS ---

@admin_bp.route('/seasons')
def seasons():
    seasons = Season.query.order_by(Season.id.desc()).all()
    return render_template('admin/seasons.html', seasons=seasons)

@admin_bp.route('/seasons/new', methods=['POST'])
def create_season():
    nome = request.form.get('nome')
    nova = Season(nome=nome, ativa=True, data_inicio=datetime.utcnow().date())
    db.session.add(nova)
    db.session.commit()
    flash(f'Temporada {nome} criada!', 'success')
    return redirect(url_for('admin.seasons'))

@admin_bp.route('/seasons/<int:season_id>', methods=['GET', 'POST'])
def manage_season(season_id):
    season = Season.query.get_or_404(season_id)
    if request.method == 'POST':
        if not season.ativa:
            flash('Não é possível modificar uma temporada encerrada.', 'danger')
            return redirect(url_for('admin.manage_season', season_id=season.id))
            
        nome_gp = request.form.get('nome_gp')
        pista = request.form.get('pista')
        grid = request.form.get('grid')
        tipo_etapa = request.form.get('tipo_etapa')
        data_str = request.form.get('data')
        try:
            data_obj = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else None
        except ValueError:
            flash('Formato de data inválido.', 'danger')
            return redirect(url_for('admin.manage_season', season_id=season.id))
        
        nova_race = Race(season_id=season.id, nome_gp=nome_gp, pista=pista, grid=grid, data_corrida=data_obj, tipo_etapa=tipo_etapa)
        db.session.add(nova_race)
        db.session.commit()
        flash('Corrida adicionada ao calendário!', 'success')
        return redirect(url_for('admin.manage_season', season_id=season.id))
        
    return render_template('admin/season_detail.html', season=season, pistas=PISTAS_F1)

@admin_bp.route('/season/<int:season_id>/close', methods=['POST'])
def close_season(season_id):
    if current_user.role != 'SUPER_ADM':
        flash('Apenas o Super ADM pode encerrar temporadas.', 'danger')
        return redirect(url_for('admin.seasons'))
    
    season = Season.query.get_or_404(season_id)
    season.ativa = False
    
    # 1. Resetar Disciplina e Demitir Pilotos (Exceto Super ADM)
    pilotos = PilotProfile.query.join(User).filter(User.role != 'SUPER_ADM').all()
    for p in pilotos:
        p.pontos_cnh = 25
        p.advertencias_acumuladas = 0
        p.team_id = None # Todos viram Free Agents
        p.grid = 'SEM_GRID'
        
    # 2. Arquivar Equipes
    equipes = Team.query.all()
    for t in equipes:
        t.ativa = False
        
    db.session.commit()
    flash(f'Temporada {season.nome} encerrada! Equipes arquivadas e pilotos liberados.', 'success')
    return redirect(url_for('admin.seasons'))

@admin_bp.route('/race/<int:race_id>/edit', methods=['GET', 'POST'])
def edit_race(race_id):
    race = Race.query.get_or_404(race_id)
    if request.method == 'POST':
        if not race.season.ativa:
            flash('Não é possível editar corridas de temporadas arquivadas.', 'danger')
            return redirect(url_for('admin.manage_season', season_id=race.season_id))
            
        race.nome_gp = request.form.get('nome_gp')
        race.pista = request.form.get('pista')
        race.grid = request.form.get('grid')
        race.tipo_etapa = request.form.get('tipo_etapa')
        
        data_str = request.form.get('data')
        if data_str:
            try:
                race.data_corrida = datetime.strptime(data_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Data inválida.', 'danger')
                return redirect(url_for('admin.edit_race', race_id=race.id))
            
        db.session.commit()
        flash('Corrida atualizada com sucesso!', 'success')
        return redirect(url_for('admin.manage_season', season_id=race.season_id))
        
    return render_template('admin/edit_race.html', race=race, pistas=PISTAS_F1)

@admin_bp.route('/race/<int:race_id>/delete', methods=['POST'])
def delete_race(race_id):
    race = Race.query.get_or_404(race_id)
    season_id = race.season_id
    
    if not race.season.ativa:
        flash('Não é possível apagar corridas de temporadas arquivadas.', 'danger')
        return redirect(url_for('admin.manage_season', season_id=season_id))
        
    # FIX: Estornar punições de W.O. (FNJ) antes de apagar a corrida
    resultados = RaceResult.query.filter_by(race_id=race.id).all()
    for res in resultados:
        if res.ausencia == 'FNJ':
            piloto = PilotProfile.query.get(res.pilot_id)
            if piloto:
                piloto.pontos_cnh += 5

    RaceResult.query.filter_by(race_id=race.id).delete()
    RaceRegistration.query.filter_by(race_id=race.id).delete() # Limpa check-ins
    
    # Limpa votos antes de apagar protestos
    protestos = Protesto.query.filter_by(etapa_id=race.id).all()
    for p in protestos:
        VotoComissario.query.filter_by(protesto_id=p.id).delete()
        db.session.delete(p)
        
    db.session.delete(race)
    db.session.commit()
    flash('Corrida removida.', 'success')
    return redirect(url_for('admin.manage_season', season_id=season_id))

@admin_bp.route('/race/<int:race_id>/generate_grid')
def generate_grid_text(race_id):
    race = Race.query.get_or_404(race_id)
    season = race.season
    corridas_grid = Race.query.filter_by(season_id=season.id, grid=race.grid).order_by(Race.data_corrida).all()
    
    try:
        index_etapa = corridas_grid.index(race)
        numero_etapa = index_etapa + 1
        total_etapas = len(corridas_grid)
    except:
        numero_etapa = 1
        total_etapas = 10
        
    usar_lastro = True
    if numero_etapa == 1 or numero_etapa == total_etapas:
        usar_lastro = False
        
    # Remove filtro de SUPER_ADM para gerar grid se ele estiver na categoria
    pilotos = PilotProfile.query.join(User).filter(PilotProfile.grid == race.grid).all()
    ranking = []
    
    for p in pilotos:
        pts = sum(r.pontos_ganhos for r in p.race_results if r.race.season_id == season.id)
        vitorias = sum(1 for r in p.race_results if r.race.season_id == season.id and r.posicao == 1)
        ranking.append({'piloto': p, 'pontos': pts, 'vitorias': vitorias})
        
    ranking.sort(key=lambda x: (x['pontos'], x['vitorias']), reverse=True)
    
    lista_final = []
    for i, item in enumerate(ranking):
        if not usar_lastro: 
            carro = "Desempenho Igual (Livre)"
        else:
            if i < len(ORDEM_CARROS): 
                carro = ORDEM_CARROS[i]
            else: 
                carro = "McLaren (Extra)"
        lista_final.append({'pos': i + 1, 'nickname': item['piloto'].nickname, 'carro': carro})
        
    return render_template('admin/grid_text.html', race=race, lista=lista_final, usar_lastro=usar_lastro)

# --- RESULTADOS DA CORRIDA (COM CHECK-IN, BÔNUS E RESERVAS) ---

@admin_bp.route('/race/<int:race_id>/results', methods=['GET', 'POST'])
def race_results(race_id):
    race = Race.query.get_or_404(race_id)
    if request.method == 'POST':
        if not race.season.ativa:
            flash('Temporada encerrada.', 'warning')
            return redirect(url_for('admin.manage_season', season_id=race.season_id))
        
        # FIX: Estornar punições de W.O. (FNJ) anteriores para evitar duplicidade ao editar
        resultados_anteriores = RaceResult.query.filter_by(race_id=race.id).all()
        for res in resultados_anteriores:
            if res.ausencia == 'FNJ':
                piloto_afetado = PilotProfile.query.get(res.pilot_id)
                if piloto_afetado:
                    piloto_afetado.pontos_cnh += 5

        # FIX: Snapshot dos times usados nesta corrida antes de apagar
        # Isso impede que, ao editar uma corrida antiga, o piloto "mude de equipe" retroativamente
        team_snapshot = { r.pilot_id: r.team_id for r in resultados_anteriores }

        # Limpa resultados anteriores
        RaceResult.query.filter_by(race_id=race.id).delete()
        
        # 1. PROCESSAR TITULARES
        titulares_ids = request.form.getlist('titular_id')
        for pid in titulares_ids:
            try:
                posicao = int(request.form.get(f'pos_{pid}') or 0)
            except ValueError:
                posicao = 0

            status_presenca = request.form.get(f'status_{pid}') # OK, FJ, FNJ
            piloto = PilotProfile.query.get(pid)
            
            equipe_id = team_snapshot.get(int(pid))
            if equipe_id is None:
                equipe_id = piloto.team_id
            
            if status_presenca == 'OK':
                posicao = int(request.form.get(f'pos_{pid}') or 0)
                dnf = request.form.get(f'dnf_{pid}') == 'on'
                dsq = request.form.get(f'dsq_{pid}') == 'on'
                vr = request.form.get(f'vr_{pid}') == 'on'
                dotd = request.form.get(f'dotd_{pid}') == 'on'
                fan = request.form.get(f'fan_{pid}') == 'on' # Bônus Torcida
                
                pontos = 0.0
                if not dsq:
                    if not dnf and posicao > 0: pontos = float(PONTUACAO_NORMAL.get(posicao, 0))
                    if race.tipo_etapa == 'SPRINT': pontos *= 0.5
                    elif race.tipo_etapa == 'FINAL': pontos *= 2.0
                    if vr and not dnf: pontos += 1.0
                    if dotd: pontos += 1.0
                    if fan: pontos += 1.0 # Soma Bônus Torcida
                
                db.session.add(RaceResult(
                    race_id=race.id, pilot_id=pid, team_id=equipe_id,
                    posicao=posicao, pontos_ganhos=pontos,
                    dnf=dnf, dsq=dsq, volta_rapida=vr, piloto_do_dia=dotd,
                    piloto_torcida=fan,
                    ausencia=None
                ))
            else:
                # FJ ou FNJ
                if status_presenca == 'FNJ':
                    piloto.pontos_cnh -= 5 # Punição W.O.
                
                db.session.add(RaceResult(
                    race_id=race.id, pilot_id=pid, team_id=equipe_id,
                    posicao=0, pontos_ganhos=0, ausencia=status_presenca
                ))

        # 2. PROCESSAR RESERVAS
        reserva_pids = request.form.getlist('reserva_pilot')
        reserva_teams = request.form.getlist('reserva_team')
        reserva_pos = request.form.getlist('reserva_pos')
        
        for i, r_pid in enumerate(reserva_pids):
            if r_pid and r_pid.strip() != "":
                # Tratamento seguro para ID da equipe (evita erro com string vazia)
                r_team_val = reserva_teams[i] if i < len(reserva_teams) else None
                
                if not r_team_val or not r_team_val.strip():
                    flash(f'Erro: É obrigatório selecionar uma equipe para o piloto reserva (Linha {i+1}).', 'danger')
                    db.session.rollback()
                    return redirect(url_for('admin.race_results', race_id=race.id))

                r_team_id = int(r_team_val)
                
                try:
                    r_pos_val = reserva_pos[i] if i < len(reserva_pos) else 0
                    r_pos = int(r_pos_val) if r_pos_val else 0
                except ValueError:
                    r_pos = 0
                
                r_dnf = request.form.get(f'reserva_dnf_{i}') == 'on'
                r_dsq = request.form.get(f'reserva_dsq_{i}') == 'on'
                r_vr = request.form.get(f'reserva_vr_{i}') == 'on'
                r_dotd = request.form.get(f'reserva_dotd_{i}') == 'on'
                r_fan = request.form.get(f'reserva_fan_{i}') == 'on' # Bônus Reserva
                
                r_pontos = 0.0
                if not r_dsq:
                    if not r_dnf and r_pos > 0: r_pontos = float(PONTUACAO_NORMAL.get(r_pos, 0))
                    if race.tipo_etapa == 'SPRINT': r_pontos *= 0.5
                    elif race.tipo_etapa == 'FINAL': r_pontos *= 2.0
                    if r_vr and not r_dnf: r_pontos += 1.0
                    if r_dotd: r_pontos += 1.0
                    if r_fan: r_pontos += 1.0
                
                db.session.add(RaceResult(
                    race_id=race.id, pilot_id=r_pid, team_id=r_team_id,
                    posicao=r_pos, pontos_ganhos=r_pontos,
                    dnf=r_dnf, dsq=r_dsq, volta_rapida=r_vr, piloto_do_dia=r_dotd,
                    piloto_torcida=r_fan,
                    ausencia=None
                ))

        race.status = 'Concluida'
        db.session.commit()
        flash('Resultados salvos com sucesso!', 'success')
        return redirect(url_for('admin.manage_season', season_id=race.season_id))

    # --- GET: Preparar dados ---
    
    # 1. Titulares: Apenas do GRID da corrida, COM EQUIPE (Inclui ADMs se tiverem equipe)
    titulares = PilotProfile.query.join(User).filter(
        PilotProfile.grid == race.grid, 
        PilotProfile.team_id != None
    ).order_by(PilotProfile.nickname).all()
    
    # 2. Reservas: QUALQUER piloto SEM EQUIPE (Inclui ADMs para correrem de reserva)
    reservas_disponiveis = PilotProfile.query.join(User).filter(
        PilotProfile.team_id == None
    ).order_by(PilotProfile.nickname).all()
    
    # 3. Equipes Ativas (para selecionar onde o reserva correu)
    equipes = Team.query.filter_by(ativa=True, grid=race.grid).all()
    
    # 4. Check-ins (Carrega as respostas)
    checkins = RaceRegistration.query.filter_by(race_id=race.id).all()
    checkin_map = { r.pilot_id: r for r in checkins }
    
    # 5. Resultados já gravados (Para edição/visualização)
    resultados_existentes = RaceResult.query.filter_by(race_id=race.id).all()
    results_map = { r.pilot_id: r for r in resultados_existentes }
    
    # Identificar reservas que correram (não são titulares do grid)
    titulares_ids = [t.id for t in titulares]
    reservas_que_correram = [r for r in resultados_existentes if r.pilot_id not in titulares_ids]
    
    return render_template('admin/race_results.html', 
                           race=race, 
                           titulares=titulares, 
                           reservas=reservas_disponiveis,
                           equipes=equipes,
                           checkin_map=checkin_map,
                           results_map=results_map,
                           reservas_que_correram=reservas_que_correram)

# --- GESTÃO DE PILOTOS E CONVITES ---

@admin_bp.route('/pilots')
def list_pilots():
    # Mostra todos os pilotos, inclusive ADMs, para gestão de Grid/CNH
    pilots = PilotProfile.query.join(User).order_by(PilotProfile.nickname).all()

    # Agrupar pilotos por grid para facilitar a exibição em abas
    pilots_by_grid = {
        'ELITE': [],
        'ADVANCED': [],
        'INITIAL': [],
        'RESERVA': [],
        'SEM_GRID': []
    }

    for p in pilots:
        grid_key = p.grid if p.grid in pilots_by_grid else 'SEM_GRID'
        pilots_by_grid[grid_key].append(p)

    return render_template('admin/pilots.html', pilots_by_grid=pilots_by_grid, total_count=len(pilots))

@admin_bp.route('/pilots/edit/<int:pilot_id>', methods=['GET', 'POST'])
def edit_pilot(pilot_id):
    pilot = PilotProfile.query.get_or_404(pilot_id)
    
    # Segurança: Impede que um ADM comum edite um SUPER ADM
    if pilot.user.role == 'SUPER_ADM' and current_user.role != 'SUPER_ADM':
        flash('Apenas Super Admins podem editar perfis da Direção de Prova.', 'warning')
        return redirect(url_for('admin.list_pilots'))
        
    if request.method == 'POST':
        new_nickname = (request.form.get('nickname') or '')[:50]
        pilot.nickname = new_nickname
        pilot.user.username = new_nickname # Sincroniza o login do usuário
        pilot.nome_real = request.form.get('nome_real')[:100] # Garante salvar Nome Real
        pilot.grid = request.form.get('grid')           # Garante salvar Grid
        pilot.telefone = request.form.get('telefone')[:20] if request.form.get('telefone') else None
        
        pontos = request.form.get('pontos_cnh')
        try:
            if pontos: pilot.pontos_cnh = int(pontos)
        except ValueError:
            flash('Valor de CNH inválido.', 'danger')

        # --- PENALIDADE ADMINISTRATIVA (NOVO) ---
        penalidade = request.form.get('penalidade_campeonato')
        try:
            pilot.penalidade_campeonato = float(penalidade or 0)
            pilot.motivo_penalidade = request.form.get('motivo_penalidade')
        except ValueError:
            flash('Valor de penalidade inválido.', 'danger')
        
        # --- RESET DE SENHA (NOVO) ---
        nova_senha = request.form.get('nova_senha')
        if nova_senha and nova_senha.strip() != "":
            # FIX: Bloquear alteração de senha de ADMs por ADMs comuns
            if pilot.user.role in ['ADM', 'SUPER_ADM'] and current_user.role != 'SUPER_ADM':
                flash('Apenas o Super Admin pode alterar senhas de outros administradores.', 'danger')
            else:
                pilot.user.set_password(nova_senha)
                flash(f'Senha alterada com sucesso para: {nova_senha}', 'info')
        
        if 'foto' in request.files:
            file = request.files['foto']
            if file and file.filename != '' and allowed_file(file.filename):
                if pilot.foto_url:
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], pilot.foto_url)
                    if os.path.exists(old_path): os.remove(old_path)
                    
                ext = file.filename.rsplit('.', 1)[1].lower()
                timestamp = int(datetime.utcnow().timestamp())
                nome = f"piloto_{pilot.id}_{timestamp}.{ext}"
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], nome))
                pilot.foto_url = nome
                
        db.session.commit()
        flash('Perfil atualizado com sucesso.', 'success')
        return redirect(url_for('admin.list_pilots'))
        
    return render_template('admin/edit_pilot.html', pilot=pilot)

# --- NOVO: ROTA DE EXCLUSÃO DE PILOTO ---
@admin_bp.route('/pilots/delete/<int:pilot_id>', methods=['POST'])
def delete_pilot(pilot_id):
    if current_user.role != 'SUPER_ADM':
        flash('Apenas o Super Admin pode excluir contas.', 'danger')
        return redirect(url_for('admin.list_pilots'))

    profile = PilotProfile.query.get_or_404(pilot_id)
    user = profile.user

    if user.role == 'SUPER_ADM' or user.username == 'Admin':
        flash('Não é possível excluir o Super Admin.', 'danger')
        return redirect(url_for('admin.list_pilots'))

    # Verifica histórico de corridas
    tem_historico = RaceResult.query.filter_by(pilot_id=profile.id).first()

    if tem_historico:
        # ANONIMIZAR
        if profile.foto_url:
            path = os.path.join(current_app.config['UPLOAD_FOLDER'], profile.foto_url)
            if os.path.exists(path): os.remove(path)
            profile.foto_url = None
            
        suffix = secrets.token_hex(4)
        user.username = f"Ex-Piloto_{user.id}_{suffix}"
        user.email = f"deleted_{user.id}_{suffix}@fullgas.local"
        user.set_password(secrets.token_hex(16))
        user.role = 'INATIVO'
        
        profile.nickname = "Piloto Removido"
        profile.nome_real = "Dados Removidos"
        profile.team_id = None
        profile.pontos_cnh = 0
        
        RaceRegistration.query.filter_by(pilot_id=profile.id).delete()
        
        db.session.commit()
        flash('Piloto possuía histórico. Conta anonimizada para preservar a pontuação das equipes.', 'warning')
    else:
        # EXCLUSÃO TOTAL
        if profile.foto_url:
            path = os.path.join(current_app.config['UPLOAD_FOLDER'], profile.foto_url)
            if os.path.exists(path): os.remove(path)

        profile.team_id = None
        RaceResult.query.filter_by(pilot_id=profile.id).delete()
        RaceRegistration.query.filter_by(pilot_id=profile.id).delete()
        
        protestos_envolvidos = Protesto.query.filter((Protesto.acusador_id == profile.id) | (Protesto.acusado_id == profile.id)).all()
        for p in protestos_envolvidos:
            VotoComissario.query.filter_by(protesto_id=p.id).delete()
            db.session.delete(p)

        db.session.delete(profile)
        db.session.delete(user)
        db.session.commit()
        
        flash('Conta do usuário e perfil de piloto excluídos permanentemente.', 'success')
        
    return redirect(url_for('admin.list_pilots'))

@admin_bp.route('/invites', methods=['GET', 'POST'])
def invites():
    if request.method == 'POST':
        email = request.form.get('email')
        if User.query.filter_by(email=email).first():
            flash('Email já existe.', 'warning')
        else:
            token = secrets.token_hex(3).upper()
            novo = Invite(email=email, token=token)
            db.session.add(novo)
            db.session.commit()
            flash(f'Token: {token}', 'success')
    active = Invite.query.filter_by(used=False).order_by(Invite.id.desc()).all()
    return render_template('admin/invites.html', invites=active)

@admin_bp.route('/invites/delete/<int:invite_id>', methods=['POST'])
def delete_invite(invite_id):
    if current_user.role != 'SUPER_ADM':
        flash('Apenas o Super Admin pode excluir convites.', 'danger')
        return redirect(url_for('admin.invites'))
    invite = Invite.query.get_or_404(invite_id)
    db.session.delete(invite)
    db.session.commit()
    flash('Convite removido com sucesso.', 'success')
    return redirect(url_for('admin.invites'))

# --- GESTÃO DE EQUIPES ---

@admin_bp.route('/teams')
def list_teams():
    teams = Team.query.order_by(Team.ativa.desc(), Team.grid, Team.nome).all()
    return render_template('admin/teams.html', teams=teams)

@admin_bp.route('/teams/new', methods=['GET', 'POST'])
def create_team():
    if request.method == 'POST':
        nome = request.form.get('nome')
        grid = request.form.get('grid')
        
        nova_equipe = Team(nome=nome, grid=grid, ativa=True)
        db.session.add(nova_equipe)
        db.session.flush() # Gera o ID para usar no nome do arquivo
        
        if 'foto' in request.files:
            file = request.files['foto']
            if file and file.filename != '' and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                timestamp = int(datetime.utcnow().timestamp())
                nome_arq = f"team_{nova_equipe.id}_{timestamp}.{ext}"
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], nome_arq))
                nova_equipe.logo_url = nome_arq
        
        db.session.commit()
        flash(f'Equipe {nome} criada!', 'success')
        return redirect(url_for('admin.edit_team', team_id=nova_equipe.id))
        
    return render_template('admin/create_team.html')

@admin_bp.route('/teams/edit/<int:team_id>', methods=['GET', 'POST'])
def edit_team(team_id):
    team = Team.query.get_or_404(team_id)
    if request.method == 'POST':
        team.nome = request.form.get('nome')
        team.grid = request.form.get('grid')
        team.ativa = True if request.form.get('ativa') == 'on' else False
        
        if 'foto' in request.files:
            file = request.files['foto']
            if file and file.filename != '' and allowed_file(file.filename):
                if team.logo_url:
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], team.logo_url)
                    if os.path.exists(old_path): os.remove(old_path)
                    
                ext = file.filename.rsplit('.', 1)[1].lower()
                timestamp = int(datetime.utcnow().timestamp())
                nome_arq = f"team_{team.id}_{timestamp}.{ext}"
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], nome_arq))
                team.logo_url = nome_arq
        
        # Limpa pilotos atuais
        for p in team.pilots:
            p.team_id = None
            
        pilot1_id = request.form.get('pilot1')
        pilot2_id = request.form.get('pilot2')
        
        if pilot1_id:
            p1 = PilotProfile.query.get(pilot1_id)
            if p1: p1.team_id = team.id
        if pilot2_id:
            p2 = PilotProfile.query.get(pilot2_id)
            if p2: p2.team_id = team.id
            
        db.session.commit()
        flash('Equipe atualizada!', 'success')
        return redirect(url_for('admin.list_teams'))

    # LÓGICA: Apenas pilotos que já pertencem ao MESMO GRID da equipe aparecem aqui (incluindo ADMs).
    pilotos_disponiveis = PilotProfile.query.join(User).filter(
        PilotProfile.grid == team.grid, # Filtro estrito por Grid
        (PilotProfile.team_id == None) | (PilotProfile.team_id == team.id) # Disponíveis ou já na equipe
    ).all()
    
    return render_template('admin/edit_team.html', team=team, pilots=pilotos_disponiveis)

@admin_bp.route('/teams/delete/<int:team_id>', methods=['POST'])
def delete_team(team_id):
    if current_user.role != 'SUPER_ADM':
        flash('Permissão negada.', 'danger')
        return redirect(url_for('admin.list_teams'))
        
    team = Team.query.get_or_404(team_id)
    
    # Verifica se a equipe tem histórico (resultados de corrida)
    tem_historico = RaceResult.query.filter_by(team_id=team.id).first()
    
    for p in team.pilots:
        p.team_id = None
        
    if tem_historico:
        team.ativa = False
        db.session.commit()
        flash('Equipe arquivada para preservar o histórico de temporadas passadas.', 'warning')
    else:
        if team.logo_url:
            path = os.path.join(current_app.config['UPLOAD_FOLDER'], team.logo_url)
            if os.path.exists(path): os.remove(path)
            
        db.session.delete(team)
        db.session.commit()
        flash('Equipe excluída permanentemente.', 'success')
        
    return redirect(url_for('admin.list_teams'))

# --- MÓDULO DE SELETIVA (TIME TRIAL) ---

@admin_bp.route('/seletiva', methods=['GET', 'POST'])
def seletiva():
    if current_user.role not in ['SUPER_ADM', 'ADM']:
        return redirect(url_for('admin.dashboard'))
        
    if Season.query.filter_by(ativa=True).first():
        flash('não é permitido criar uma seletiva com uma season em andamento', 'danger')
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        # Adicionar Tempo
        pilot_id = request.form.get('pilot_id')
        tempo_input = request.form.get('tempo') # Esperado: 1:35.800
        
        if not pilot_id or not tempo_input:
            flash('Selecione um piloto e informe o tempo.', 'warning')
            return redirect(url_for('admin.seletiva'))
            
        # Parser de Tempo (1:35.800 -> ms)
        try:
            # Remove tudo que não é dígito para garantir
            digits = "".join(filter(str.isdigit, tempo_input))
            # Assume formato M:SS.mmm (6 ou 7 dígitos). Ex: 135800
            if len(digits) < 4: raise ValueError("Tempo muito curto")
            
            ms = int(digits[-3:])
            sec = int(digits[-5:-3])
            min = int(digits[:-5]) if len(digits) > 5 else 0
            
            total_ms = (min * 60 * 1000) + (sec * 1000) + ms
            
            # Verifica se já existe entrada para este piloto (Atualiza ou Cria)
            entry = SeletivaEntry.query.filter_by(pilot_id=pilot_id).first()
            if not entry:
                entry = SeletivaEntry(pilot_id=pilot_id)
                db.session.add(entry)
            
            entry.tempo_str = tempo_input
            entry.tempo_ms = total_ms
            entry.data_registro = datetime.utcnow()
            
            db.session.commit()
            flash(f'Tempo de {entry.piloto.nickname} registrado: {tempo_input}', 'success')
            
        except Exception as e:
            flash('Formato de tempo inválido. Use o formato 1:35.800', 'danger')
            
        return redirect(url_for('admin.seletiva'))

    # LÓGICA: Aqui aparecem TODOS os pilotos que ainda não foram classificados (SEM_GRID)
    pilotos_sem_grid = PilotProfile.query.filter_by(grid='SEM_GRID').order_by(PilotProfile.nickname).all()
    entradas = SeletivaEntry.query.order_by(SeletivaEntry.tempo_ms.asc()).all()
    
    return render_template('admin/seletiva.html', pilotos=pilotos_sem_grid, entradas=entradas)

@admin_bp.route('/seletiva/delete/<int:entry_id>', methods=['POST'])
def delete_seletiva_entry(entry_id):
    entry = SeletivaEntry.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()
    flash('Tempo removido.', 'info')
    return redirect(url_for('admin.seletiva'))

@admin_bp.route('/seletiva/close', methods=['POST'])
def close_seletiva():
    if current_user.role != 'SUPER_ADM':
        flash('Apenas Super Admin pode aplicar o grid.', 'danger')
        return redirect(url_for('admin.seletiva'))
        
    entradas = SeletivaEntry.query.order_by(SeletivaEntry.tempo_ms.asc()).all()
    
    for i, entry in enumerate(entradas):
        pos = i + 1
        if pos <= 20: entry.piloto.grid = 'ELITE'
        elif pos <= 40: entry.piloto.grid = 'ADVANCED'
        elif pos <= 60: entry.piloto.grid = 'INITIAL'
        else: entry.piloto.grid = 'RESERVA'
        
    # Opcional: Limpar a tabela de seletiva após aplicar?
    # Por segurança, vamos manter os dados lá. O admin pode limpar manualmente se quiser.
    
    db.session.commit()
    flash(f'Seletiva encerrada! {len(entradas)} pilotos foram alocados em seus grids.', 'success')
    return redirect(url_for('admin.list_pilots'))

# --- TRIBUNAL DE PUNIÇÕES (CORRIGIDO: BUSCA NO BANCO) ---

@admin_bp.route('/protests')
def protests():
    # Conta o total de administradores aptos a votar
    total_admins = User.query.filter(User.role.in_(['ADM', 'SUPER_ADM'])).count()

    # Obtém a lista de IDs de protestos onde o administrador atual já votou
    voted_protest_ids = [v.protesto_id for v in VotoComissario.query.filter_by(admin_id=current_user.id).all()]

    aguardando = Protesto.query.filter_by(status='AGUARDANDO_DEFESA').order_by(Protesto.data_criacao.desc()).all()
    em_votacao = Protesto.query.filter_by(status='EM_VOTACAO').order_by(Protesto.data_criacao.desc()).all()
    concluidos = Protesto.query.filter_by(status='CONCLUIDO').order_by(Protesto.data_fechamento.desc()).limit(10).all()
    
    return render_template('admin/protests.html', 
                           aguardando=aguardando, 
                           pendentes=em_votacao, 
                           concluidos=concluidos,
                           total_admins=total_admins,
                           voted_protest_ids=voted_protest_ids)

@admin_bp.route('/protests/<int:protest_id>', methods=['GET', 'POST'])
def view_protest(protest_id):
    protesto = Protesto.query.get_or_404(protest_id)
    meu_voto = VotoComissario.query.filter_by(protesto_id=protesto.id, admin_id=current_user.id).first()
    
    embed_acusacao = get_embed_url(protesto.video_link)
    embed_defesa = get_embed_url(protesto.video_defesa)

    votos_resumo = db.session.query(VotoComissario.escolha, func.count(VotoComissario.escolha))\
        .filter_by(protesto_id=protesto.id).group_by(VotoComissario.escolha).all()

    if request.method == 'POST':
        if 'voto' in request.form and protesto.status in ['EM_VOTACAO', 'AGUARDANDO_DEFESA']:
            # Impedir que partes envolvidas votem no próprio processo (exceto Super Admin)
            if current_user.pilot_profile and (current_user.pilot_profile.id == protesto.acusado_id or current_user.pilot_profile.id == protesto.acusador_id) and current_user.role != 'SUPER_ADM':
                flash('Conflito de interesse: Você é parte envolvida neste protesto e não pode votar.', 'danger')
                return redirect(url_for('admin.view_protest', protest_id=protesto.id))

            escolha = request.form.get('voto')
            if meu_voto: meu_voto.escolha = escolha
            else:
                novo = VotoComissario(protesto_id=protesto.id, admin_id=current_user.id, escolha=escolha)
                db.session.add(novo)
            
            if protesto.status == 'AGUARDANDO_DEFESA':
                protesto.status = 'EM_VOTACAO'
                
            db.session.commit()
            flash('Seu voto foi registrado.', 'success')
            return redirect(url_for('admin.view_protest', protest_id=protesto.id))

        if 'encerrar' in request.form and current_user.role == 'SUPER_ADM':
            veredito = request.form.get('veredito_final')
            texto = request.form.get('justificativa')
            
            protesto.veredito_final = veredito
            protesto.justificativa_texto = texto
            protesto.status = 'CONCLUIDO'
            protesto.data_fechamento = datetime.utcnow()
            
            piloto = protesto.acusado
            resultado_corrida = RaceResult.query.filter_by(race_id=protesto.etapa_id, pilot_id=piloto.id).first()
            
            pontos_perda = 0
            if veredito == 'LEVE': pontos_perda = 3
            elif veredito == 'MEDIA': pontos_perda = 5
            elif veredito == 'GRAVE': pontos_perda = 10
            elif veredito == 'ADVERTENCIA':
                piloto.advertencias_acumuladas += 1
                if piloto.advertencias_acumuladas > 0 and piloto.advertencias_acumuladas % 3 == 0:
                    flash(f'Piloto atingiu {piloto.advertencias_acumuladas} advertências. Punição automática aplicada (-3 pts).', 'warning')
                    pontos_perda = 3
            
            if pontos_perda > 0:
                piloto.pontos_cnh -= pontos_perda
                if resultado_corrida:
                    resultado_corrida.pontos_ganhos -= pontos_perda
            
            db.session.commit()
            flash('Caso encerrado e punições aplicadas.', 'success')
            return redirect(url_for('admin.protests'))
            
        if 'reabrir' in request.form and current_user.role == 'SUPER_ADM':
            piloto = protesto.acusado
            veredito_anterior = protesto.veredito_final
            resultado_corrida = RaceResult.query.filter_by(race_id=protesto.etapa_id, pilot_id=piloto.id).first()
            
            pontos_devolver = 0
            if veredito_anterior == 'LEVE': pontos_devolver = 3
            elif veredito_anterior == 'MEDIA': pontos_devolver = 5
            elif veredito_anterior == 'GRAVE': pontos_devolver = 10
            elif veredito_anterior == 'ADVERTENCIA':
                if piloto.advertencias_acumuladas > 0 and piloto.advertencias_acumuladas % 3 == 0:
                    pontos_devolver = 3
                if piloto.advertencias_acumuladas > 0: piloto.advertencias_acumuladas -= 1
            
            if pontos_devolver > 0:
                piloto.pontos_cnh += pontos_devolver
                if resultado_corrida:
                    resultado_corrida.pontos_ganhos += pontos_devolver

            protesto.status = 'EM_VOTACAO'
            protesto.veredito_final = None
            db.session.commit()
            flash('Caso reaberto! Pontos estornados.', 'warning')
            return redirect(url_for('admin.view_protest', protest_id=protesto.id))

    return render_template('admin/view_protest.html', 
                           protesto=protesto, 
                           meu_voto=meu_voto, 
                           votos_resumo=votos_resumo,
                           embed_acusacao=embed_acusacao,
                           embed_defesa=embed_defesa)

@admin_bp.route('/protests/<int:protest_id>/delete', methods=['POST'])
def delete_protest_admin(protest_id):
    if current_user.role != 'SUPER_ADM':
        flash('Apenas o Super Admin pode excluir protestos.', 'danger')
        return redirect(url_for('admin.protests'))
        
    protesto = Protesto.query.get_or_404(protest_id)
    
    # Reverter punições se o caso já estava concluído
    if protesto.status == 'CONCLUIDO':
        piloto = protesto.acusado
        veredito = protesto.veredito_final
        resultado_corrida = RaceResult.query.filter_by(race_id=protesto.etapa_id, pilot_id=piloto.id).first()
        
        pontos_devolver = 0
        if veredito == 'LEVE': pontos_devolver = 3
        elif veredito == 'MEDIA': pontos_devolver = 5
        elif veredito == 'GRAVE': pontos_devolver = 10
        elif veredito == 'ADVERTENCIA':
            # Se atingiu múltiplo de 3, devolve os 3 pontos que foram tirados automaticamente
            if piloto.advertencias_acumuladas > 0 and piloto.advertencias_acumuladas % 3 == 0:
                pontos_devolver = 3
            # Remove a advertência do histórico
            if piloto.advertencias_acumuladas > 0: 
                piloto.advertencias_acumuladas -= 1
        
        if pontos_devolver > 0:
            piloto.pontos_cnh += pontos_devolver
            if resultado_corrida:
                resultado_corrida.pontos_ganhos += pontos_devolver

    # Limpa votos associados para evitar erro de integridade (FK)
    VotoComissario.query.filter_by(protesto_id=protesto.id).delete()
    
    db.session.delete(protesto)
    db.session.commit()
    
    flash('Pedido de punição removido e punições revertidas com sucesso.', 'success')
    return redirect(url_for('admin.protests'))