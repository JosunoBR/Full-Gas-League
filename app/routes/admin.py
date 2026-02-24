import os
import secrets
import shutil
from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, case
from app.models import db, User, PilotProfile, Season, Race, RaceResult, Invite, Protesto, VotoComissario, Team, RaceRegistration, SeletivaEntry, News, GridConfig, SeasonChampion, PilotGridPhoto
from app.utils import allowed_file, get_embed_url, PONTUACAO_20, PONTUACAO_22, ORDEM_CARROS

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
    # Pega a temporada ativa mais recente para exibição
    all_active_seasons = Season.query.filter_by(ativa=True).order_by(Season.id.desc()).all()
    
    selected_season_id = request.args.get('s', type=int)
    season_ativa = None
    if selected_season_id:
        season_ativa = next((s for s in all_active_seasons if s.id == selected_season_id), None)
    
    if not season_ativa and all_active_seasons:
        season_ativa = all_active_seasons[0] # Pega a mais recente por padrão
    
    # Determina quais grids exibir: apenas os que têm corridas nesta temporada
    # ou todos os configurados se a temporada for nova (sem corridas ainda)
    if season_ativa:
        grids_com_corrida = [r[0] for r in db.session.query(Race.grid).filter_by(season_id=season_ativa.id).distinct().all()]
        configs = GridConfig.query.order_by(GridConfig.ordem).all()
        
        if not grids_com_corrida:
            if configs:
                grid_names = [c.nome for c in configs]
            else:
                # Fallback inteligente: Busca grids usados pelos pilotos ativos
                all_pilots = PilotProfile.query.filter(PilotProfile.grid != 'SEM_GRID').all()
                found_grids = set()
                for p in all_pilots:
                    p_grids = [g.strip() for g in p.grid.split(',')]
                    for g in p_grids:
                        if g not in ['SEM_GRID', 'RESERVA']:
                            found_grids.add(g)
                
                if found_grids:
                    # Ordena tentando respeitar a hierarquia padrão se existir, senão alfabético
                    default_order = ['ELITE', 'ADVANCED', 'INITIAL']
                    grid_names = sorted(list(found_grids), key=lambda x: (default_order.index(x) if x in default_order else 999, x))
                else:
                    grid_names = ['ELITE', 'ADVANCED', 'INITIAL']
        else:
            # Apenas grids que têm corrida nesta temporada, ordenados pela configuração
            # Isso evita que grids criados na seletiva (para o futuro) apareçam na temporada atual
            all_relevant_grids = sorted(list(set(grids_com_corrida)), 
                                        key=lambda x: next((c.ordem for c in configs if c.nome == x), 999))
            grid_names = all_relevant_grids
    else:
        configs = GridConfig.query.order_by(GridConfig.ordem).all()
        grid_names = [c.nome for c in configs] if configs else ['ELITE', 'ADVANCED', 'INITIAL']

    dados_grids = {name: {'classificacao': [], 'disciplina': []} for name in grid_names}
    
    if season_ativa: # Só busca dados se houver uma temporada ativa selecionada
        # Removemos o filtro de SUPER_ADM para que eles apareçam se tiverem grid definido
        pilotos = PilotProfile.query.join(User).all()
        
        for p in pilotos:
            resultados_season = [r for r in p.race_results if r.race.season_id == season_ativa.id]
            
            # Identifica todos os grids diferentes em que este piloto participou nesta temporada
            if resultados_season:
                grids_participados = set([r.race.grid for r in resultados_season])
            else:
                # Garante que pilotos com múltiplos grids (ex: "ELITE,ADVANCED") sejam lidos corretamente
                grids_participados = set([g.strip() for g in p.grid.split(',') if g.strip()])

            # Busca punições da temporada (Protestos Concluídos com Veredito de Punição)
            punicoes = Protesto.query.join(Race).filter(
                Protesto.acusado_id == p.id,
                Protesto.status == 'CONCLUIDO',
                Protesto.veredito_final.in_(['LEVE', 'MEDIA', 'GRAVE', 'ADVERTENCIA']),
                Race.season_id == season_ativa.id
            ).order_by(Protesto.data_fechamento.desc()).all()

            for gname in grids_participados:
                if gname in dados_grids:
                    # Filtra resultados apenas deste grid específico
                    res_no_grid = [r for r in resultados_season if r.race.grid == gname]
                    pontos = float(sum(r.pontos_ganhos for r in res_no_grid))
                    vitorias = sum(1 for r in res_no_grid if r.posicao == 1 and not r.dsq)
                    podios = sum(1 for r in res_no_grid if r.posicao in [1, 2, 3] and not r.dsq)
                    
                    info = {
                        'piloto': p, 
                        'pontos': pontos, 
                        'vitorias': vitorias, 
                        'podios': podios, 
                        'cnh': p.pontos_cnh, 
                        'advertencias': p.advertencias_acumuladas,
                        'punicoes': punicoes
                    }
                    dados_grids[gname]['classificacao'].append(info)
                    dados_grids[gname]['disciplina'].append(info)
                
        for grid in dados_grids:
            dados_grids[grid]['classificacao'].sort(key=lambda x: x['pontos'], reverse=True)
            dados_grids[grid]['disciplina'].sort(key=lambda x: x['cnh'])
            
    return render_template('admin/overview.html', dados=dados_grids, season=season_ativa, all_active_seasons=all_active_seasons)

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
            new_user = User(username=username[:50], email=email, role=role)
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
        profile.teams.clear() # Remove de todas as equipes
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
            profile.teams.clear()
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

@admin_bp.route('/seasons/new', methods=['GET', 'POST'])
def create_season():
    if request.method == 'POST':
        nome = request.form.get('nome')
        
        # Cria a temporada
        nova = Season(nome=nome, ativa=True, data_inicio=datetime.utcnow().date())
        db.session.add(nova)
        
        # Processa os Grids Dinâmicos
        # O formulário envia listas: grid_name[], grid_vagas[], grid_ordem[], grid_lastro[]
        names = request.form.getlist('grid_name[]')
        vagas = request.form.getlist('grid_vagas[]')
        ordens = request.form.getlist('grid_ordem[]')
        lastros = request.form.getlist('grid_lastro[]') # Vem como "1" ou "0"

        # Limpa configurações globais anteriores (GridConfig define a estrutura atual do site)
        GridConfig.query.delete()
        
        for i in range(len(names)):
            if names[i].strip():
                novo_grid = GridConfig(
                    nome=names[i].strip(),
                    vagas=int(vagas[i]),
                    ordem=int(ordens[i]),
                    exibir_lastro=(lastros[i] == '1')
                )
                db.session.add(novo_grid)
                
        db.session.commit()
        flash(f'Temporada {nome} criada e grids configurados com sucesso!', 'success')
        return redirect(url_for('admin.seasons'))
    
    # Se for GET, exibe o formulário completo
    return render_template('admin/new_season.html')

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
        
    # CORREÇÃO: Exibir grids históricos da temporada + grids atuais
    # 1. Busca configuração atual
    current_configs = GridConfig.query.order_by(GridConfig.ordem).all()
    
    # 2. Busca grids que JÁ existem nas corridas dessa temporada (Histórico)
    grids_in_season = [r[0] for r in db.session.query(Race.grid).filter_by(season_id=season.id).distinct().all()]
    
    final_grids = []
    seen_names = set()
    
    # LÓGICA CORRIGIDA: Filosofia de temporadas paralelas
    # Se a temporada tem corridas, usamos APENAS os grids dessas corridas.
    # Se a temporada está vazia (nova), usamos o GridConfig global.
    if not grids_in_season:
        final_grids = current_configs
    else:
        # Filtra configs atuais: Só inclui se o nome estiver no histórico da temporada
        for cfg in current_configs:
            if cfg.nome in grids_in_season:
                final_grids.append(cfg)
                seen_names.add(cfg.nome)
        
        # Adiciona grids do histórico que não estão na config atual
        for g_name in grids_in_season:
            if g_name not in seen_names:
                final_grids.append(type('HistoricalGrid', (object,), {'id': 0, 'nome': g_name, 'vagas': 20, 'ordem': 999, 'exibir_lastro': True})())
                seen_names.add(g_name)
            
    final_grids.sort(key=lambda x: x.ordem if hasattr(x, 'ordem') else 999)
    return render_template('admin/season_detail.html', season=season, pistas=PISTAS_F1, grid_configs=final_grids)

@admin_bp.route('/season/<int:season_id>/close', methods=['POST'])
def close_season(season_id):
    if current_user.role != 'SUPER_ADM':
        flash('Apenas o Super ADM pode encerrar temporadas.', 'danger')
        return redirect(url_for('admin.seasons'))
    
    season = Season.query.get_or_404(season_id)
    season.ativa = False
    
    # --- HALL OF FAME SNAPSHOT (CONGELAMENTO) ---
    # Identifica grids usados na temporada
    grids_season_rows = db.session.query(Race.grid).filter_by(season_id=season.id).distinct().all()
    grids_in_season = set([r[0] for r in grids_season_rows])

    upload_folder = current_app.config['UPLOAD_FOLDER']

    for grid_name in grids_in_season:
        # 1. TOP 3 PILOTOS
        # Calcula pontuação total
        results = db.session.query(
            RaceResult.pilot_id,
            func.sum(RaceResult.pontos_ganhos).label('total_pts'),
            func.sum(case(( (RaceResult.posicao == 1) & (RaceResult.dsq == False), 1 ), else_=0)).label('total_wins')
        ).join(Race).filter(
            Race.season_id == season.id,
            Race.grid == grid_name
        ).group_by(RaceResult.pilot_id).all()

        # Ordena e pega Top 3
        sorted_pilots = sorted(results, key=lambda x: (x.total_pts or 0, x.total_wins or 0), reverse=True)[:3]

        for i, res in enumerate(sorted_pilots):
            pilot = PilotProfile.query.get(res.pilot_id)
            # Busca a equipe do piloto específica para este grid
            team = next((t for t in pilot.teams if t.grid == grid_name), None)
            
            # Copia a foto para preservar histórico (Snapshot)
            champ_img = None
            if pilot.foto_url:
                ext = pilot.foto_url.split('.')[-1]
                champ_img = f"champ_{season.id}_{grid_name}_{i+1}_{secrets.token_hex(4)}.{ext}"
                try:
                    shutil.copy(os.path.join(upload_folder, pilot.foto_url), os.path.join(upload_folder, champ_img))
                except:
                    champ_img = None # Falha na cópia, fica sem foto

            db.session.add(SeasonChampion(
                season_id=season.id, grid=grid_name, category='PILOT', position=i+1,
                name=pilot.nickname, team_name=team.nome if team else 'Sem Equipe',
                image_url=champ_img, team_logo_url=team.logo_url if team else None,
                pontos=res.total_pts, vitorias=res.total_wins
            ))

        # 2. CAMPEÃO DE CONSTRUTORES (TOP 1)
        team_results = db.session.query(
            RaceResult.team_id,
            func.sum(RaceResult.pontos_ganhos).label('total_pts'),
            func.sum(case(( (RaceResult.posicao == 1) & (RaceResult.dsq == False), 1 ), else_=0)).label('total_wins')
        ).join(Race).filter(
            Race.season_id == season.id,
            Race.grid == grid_name,
            RaceResult.team_id != None
        ).group_by(RaceResult.team_id).all()

        if team_results:
            champion_team_stats = sorted(team_results, key=lambda x: (x.total_pts or 0, x.total_wins or 0), reverse=True)[0]
            team = Team.query.get(champion_team_stats.team_id)
            
            # Copia logo da equipe
            champ_logo = None
            if team.logo_url:
                ext = team.logo_url.split('.')[-1]
                champ_logo = f"champ_team_{season.id}_{grid_name}_{secrets.token_hex(4)}.{ext}"
                try:
                    shutil.copy(os.path.join(upload_folder, team.logo_url), os.path.join(upload_folder, champ_logo))
                except:
                    champ_logo = None

            db.session.add(SeasonChampion(
                season_id=season.id, grid=grid_name, category='CONSTRUCTOR', position=1,
                name=team.nome, image_url=champ_logo,
                pontos=champion_team_stats.total_pts, vitorias=champion_team_stats.total_wins
            ))
    # --------------------------------------------

    # LIMPEZA INTELIGENTE DE GRIDS:
    # Remove do perfil dos pilotos apenas os grids que pertencem EXCLUSIVAMENTE à temporada encerrada.
    # Se um grid (ex: 'ELITE') for usado em outra temporada ativa, ele é mantido.

    # 2. Identifica grids usados em outras temporadas que continuam ATIVAS
    other_active_ids = [s.id for s in Season.query.filter(Season.id != season.id, Season.ativa == True).all()]
    grids_other_active = set()
    if other_active_ids:
        grids_other_rows = db.session.query(Race.grid).filter(Race.season_id.in_(other_active_ids)).distinct().all()
        grids_other_active = set([r[0] for r in grids_other_rows])

    # 3. Grids que devem ser removidos (Exclusivos da temporada fechada)
    grids_to_remove = grids_in_season - grids_other_active

    if grids_to_remove:
        pilots = PilotProfile.query.filter(PilotProfile.grid != 'SEM_GRID').all()
        for p in pilots:
            current_grids = set([g.strip() for g in p.grid.split(',')])
            # Remove apenas os grids exclusivos da temporada fechada
            new_grids = current_grids - grids_to_remove
            
            if not new_grids:
                p.grid = 'SEM_GRID'
            else:
                p.grid = ",".join(sorted(list(new_grids)))
        
    db.session.commit()
    flash(f'Temporada {season.nome} encerrada. Grids exclusivos desta temporada foram removidos dos perfis.', 'success')
    return redirect(url_for('admin.seasons'))

@admin_bp.route('/season/<int:season_id>/delete', methods=['POST'])
def delete_season(season_id):
    if current_user.role != 'SUPER_ADM':
        flash('Apenas o Super ADM pode excluir temporadas.', 'danger')
        return redirect(url_for('admin.seasons'))
    
    season = Season.query.get_or_404(season_id)
    
    # --- LIMPEZA DE GRIDS DOS PILOTOS ---
    # Antes de apagar as corridas, identificamos quais grids pertencem a esta temporada
    # e removemos esses grids dos pilotos, a menos que estejam ativos em outra temporada.
    grids_season_rows = db.session.query(Race.grid).filter_by(season_id=season.id).distinct().all()
    grids_in_season = set([r[0] for r in grids_season_rows])

    other_active_ids = [s.id for s in Season.query.filter(Season.id != season.id, Season.ativa == True).all()]
    grids_other_active = set()
    if other_active_ids:
        grids_other_rows = db.session.query(Race.grid).filter(Race.season_id.in_(other_active_ids)).distinct().all()
        grids_other_active = set([r[0] for r in grids_other_rows])

    grids_to_remove = grids_in_season - grids_other_active

    if grids_to_remove:
        pilots = PilotProfile.query.filter(PilotProfile.grid != 'SEM_GRID').all()
        for p in pilots:
            current_grids = set([g.strip() for g in p.grid.split(',')])
            new_grids = current_grids - grids_to_remove
            p.grid = ",".join(sorted(list(new_grids))) if new_grids else 'SEM_GRID'
    # ------------------------------------

    # Limpar dependências de todas as corridas da temporada antes de excluí-la
    for race in season.races:
        RaceResult.query.filter_by(race_id=race.id).delete()
        RaceRegistration.query.filter_by(race_id=race.id).delete()
        
        protestos = Protesto.query.filter_by(etapa_id=race.id).all()
        for p in protestos:
            VotoComissario.query.filter_by(protesto_id=p.id).delete()
            db.session.delete(p)
        
        db.session.delete(race)
    
    db.session.delete(season)
    db.session.commit()
    
    flash(f'Temporada "{season.nome}" excluída permanentemente.', 'success')
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
        
    # CORREÇÃO: Mesma lógica de grids históricos para a edição
    current_configs = GridConfig.query.order_by(GridConfig.ordem).all()
    grids_in_season = [r[0] for r in db.session.query(Race.grid).filter_by(season_id=race.season_id).distinct().all()]
    
    final_grids = []
    seen_names = set()
    
    if not grids_in_season:
        final_grids = current_configs
    else:
        for cfg in current_configs:
            if cfg.nome in grids_in_season:
                final_grids.append(cfg)
                seen_names.add(cfg.nome)
                
        for g_name in grids_in_season:
            if g_name not in seen_names:
                final_grids.append(type('HistoricalGrid', (object,), {'id': 0, 'nome': g_name, 'vagas': 20, 'ordem': 999, 'exibir_lastro': True})())
                seen_names.add(g_name)
            
    final_grids.sort(key=lambda x: x.ordem if hasattr(x, 'ordem') else 999)
    
    return render_template('admin/edit_race.html', race=race, pistas=PISTAS_F1, grid_configs=final_grids)

@admin_bp.route('/race/<int:race_id>/delete', methods=['POST'])
def delete_race(race_id):
    race = Race.query.get_or_404(race_id)
    season_id = race.season_id
    
    if not race.season.ativa:
        flash('Não é possível apagar corridas de temporadas arquivadas.', 'danger')
        return redirect(url_for('admin.manage_season', season_id=season_id))
        
    # FIX: Estornar punições de W.O. (FNJ) antes de apagar a corrida
    resultados = RaceResult.query.filter_by(race_id=race.id).all()
    # Nota: Estorno global de CNH removido (cálculo dinâmico).
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
        
    # Verifica configuração do grid para ver se lastro está habilitado
    grid_cfg = GridConfig.query.filter_by(nome=race.grid).first()
    if grid_cfg and hasattr(grid_cfg, 'exibir_lastro') and not grid_cfg.exibir_lastro:
        usar_lastro = False

    # FIX: Busca pilotos corretamente mesmo se tiverem múltiplos grids (ex: "ELITE, ADVANCED")
    all_pilots = PilotProfile.query.join(User).all()
    pilotos = [p for p in all_pilots if race.grid in [g.strip() for g in p.grid.split(',')]]
    
    ranking = []
    
    for p in pilotos:
        # FIX: Calcula pontos APENAS do grid da corrida e desconta penalidades
        resultados_grid = [r for r in p.race_results if r.race.season_id == season.id and r.race.grid == race.grid]
        
        pts = sum(r.pontos_ganhos for r in resultados_grid)
        pts -= float(p.penalidade_campeonato or 0)
        
        vitorias = sum(1 for r in resultados_grid if r.posicao == 1 and not r.dsq)
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
                    piloto_afetado.pontos_cnh += 2

        # FIX: Snapshot dos times usados nesta corrida antes de apagar
        # Isso impede que, ao editar uma corrida antiga, o piloto "mude de equipe" retroativamente
        team_snapshot = { r.pilot_id: r.team_id for r in resultados_anteriores }

        # Limpa resultados anteriores
        RaceResult.query.filter_by(race_id=race.id).delete()
        
        # --- DEFINIÇÃO DA PONTUAÇÃO (20 ou 22) ---
        # Verifica se o grid está configurado para mais de 20 vagas
        grid_config = GridConfig.query.filter_by(nome=race.grid).first()
        pontuacao_ativa = PONTUACAO_20 # Padrão
        
        if grid_config and grid_config.vagas > 20:
            pontuacao_ativa = PONTUACAO_22
        # -----------------------------------------

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
                # Busca a equipe atual do piloto para o grid desta corrida
                team = next((t for t in piloto.teams if t.grid == race.grid), None)
                equipe_id = team.id if team else None
            
            if status_presenca == 'OK':
                posicao = int(request.form.get(f'pos_{pid}') or 0)
                dnf = request.form.get(f'dnf_{pid}') == 'on'
                dsq = request.form.get(f'dsq_{pid}') == 'on'
                vr = request.form.get(f'vr_{pid}') == 'on'
                dotd = request.form.get(f'dotd_{pid}') == 'on'
                fan = request.form.get(f'fan_{pid}') == 'on' # Bônus Torcida
                
                pontos = 0.0
                if not dsq:
                    if not dnf and posicao > 0: pontos = float(pontuacao_ativa.get(posicao, 0))
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
                    pass # A punição de 2 pontos na CNH agora é calculada dinamicamente pelo 'get_cnh_info'
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
                    if not r_dnf and r_pos > 0: r_pontos = float(pontuacao_ativa.get(r_pos, 0))
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
    # FIX: Filtragem exata via Python para evitar falsos positivos com nomes de grid parecidos
    # Com M2M, verificamos se o piloto tem alguma equipe associada
    all_pilots = PilotProfile.query.join(User).order_by(PilotProfile.nickname).all()
    all_pilots_with_team = [p for p in all_pilots if p.teams]
    titulares = [p for p in all_pilots_with_team if race.grid in [g.strip() for g in p.grid.split(',')]]
    
    # 2. Reservas: QUALQUER piloto SEM EQUIPE (Inclui ADMs para correrem de reserva)
    # Reservas são aqueles que não têm equipe NO GRID DA CORRIDA (ou nenhuma equipe)
    # Mas simplificando: Reservas gerais
    reservas_disponiveis = [p for p in all_pilots if not p.teams]
    
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
    
    configs = GridConfig.query.order_by(GridConfig.ordem).all()
    grid_names = [c.nome for c in configs]
    if not grid_names: grid_names = ['ELITE', 'ADVANCED', 'INITIAL']
    
    # Organiza pilotos por grid (um piloto pode aparecer em vários)
    pilots_by_grid = {name: [] for name in grid_names + ['RESERVA', 'SEM_GRID']}

    for p in pilots:
        p_grids = [g.strip() for g in p.grid.split(',') if g.strip()] if p.grid else []
        if not p_grids: p_grids = ['SEM_GRID']
        
        for g in p_grids:
            if g not in pilots_by_grid:
                pilots_by_grid[g] = []
            pilots_by_grid[g].append(p)

    # Reconstrói as abas para incluir grids extras encontrados nos pilotos
    found_grids = list(pilots_by_grid.keys())
    
    sorted_tabs = []
    for g in grid_names:
        if g in found_grids:
            sorted_tabs.append(g)
            found_grids.remove(g)
            
    specials = ['RESERVA', 'SEM_GRID']
    others = sorted([g for g in found_grids if g not in specials])
    
    all_tabs = sorted_tabs + others + specials

    return render_template('admin/pilots.html', 
                           pilots_by_grid=pilots_by_grid, 
                           total_count=len(pilots),
                           all_pilots=pilots,
                           grid_tabs=all_tabs)

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
        grids = request.form.getlist('grids')
        pilot.grid = ",".join(grids) if grids else 'SEM_GRID'
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
        
        # --- FOTOS ESPECÍFICAS POR GRID ---
        # Upload de nova foto específica
        grid_photo_target = request.form.get('grid_photo_target')
        if grid_photo_target and 'grid_photo_file' in request.files:
            g_file = request.files['grid_photo_file']
            if g_file and g_file.filename != '' and allowed_file(g_file.filename):
                # Remove foto anterior desse grid se existir
                old_gp = PilotGridPhoto.query.filter_by(pilot_id=pilot.id, grid=grid_photo_target).first()
                if old_gp:
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], old_gp.foto_url)
                    if os.path.exists(old_path): os.remove(old_path)
                    db.session.delete(old_gp)
                
                ext = g_file.filename.rsplit('.', 1)[1].lower()
                timestamp = int(datetime.utcnow().timestamp())
                nome_gp = f"piloto_{pilot.id}_{grid_photo_target}_{timestamp}.{ext}"
                g_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], nome_gp))
                
                new_gp = PilotGridPhoto(pilot_id=pilot.id, grid=grid_photo_target, foto_url=nome_gp)
                db.session.add(new_gp)

        # Exclusão de foto específica
        delete_gp_id = request.form.get('delete_grid_photo_id')
        if delete_gp_id:
            gp_to_del = PilotGridPhoto.query.get(delete_gp_id)
            if gp_to_del and gp_to_del.pilot_id == pilot.id:
                path = os.path.join(current_app.config['UPLOAD_FOLDER'], gp_to_del.foto_url)
                if os.path.exists(path): os.remove(path)
                db.session.delete(gp_to_del)
                
        db.session.commit()
        flash('Perfil atualizado com sucesso.', 'success')
        return redirect(url_for('admin.list_pilots'))
        
    # Get all unique grid names from GridConfig
    configured_grids = [c.nome for c in GridConfig.query.order_by(GridConfig.ordem).all()]

    # Get all unique grid names from races in active seasons
    active_season_ids = [s.id for s in Season.query.filter_by(ativa=True).all()]
    race_grids = []
    if active_season_ids:
        race_grids = [r[0] for r in db.session.query(Race.grid).filter(Race.season_id.in_(active_season_ids)).distinct().all()]

    # Combine all unique grid names, ensuring 'SEM_GRID' and 'RESERVA' are always present
    all_available_grids = sorted(list(set(configured_grids + race_grids + ['SEM_GRID', 'RESERVA'])))

    # Busca histórico de punições para exibir no admin
    historico_punicoes = Protesto.query.filter(
        Protesto.acusado_id == pilot.id, 
        Protesto.status == 'CONCLUIDO'
    ).order_by(Protesto.data_fechamento.desc()).all()

    return render_template('admin/edit_pilot.html', pilot=pilot, all_available_grids=all_available_grids, historico=historico_punicoes)

@admin_bp.route('/pilots/reset/<int:pilot_id>', methods=['POST'])
def reset_pilot_status(pilot_id):
    if current_user.role != 'SUPER_ADM':
        flash('Apenas o Super Admin pode realizar reset absoluto.', 'danger')
        return redirect(url_for('admin.list_pilots'))

    pilot = PilotProfile.query.get_or_404(pilot_id)
    
    # Reset Absoluto: Remove de grids, equipe e restaura CNH
    pilot.grid = 'SEM_GRID'
    pilot.teams.clear()
    pilot.pontos_cnh = 25
    pilot.advertencias_acumuladas = 0
    pilot.penalidade_campeonato = 0.0
    pilot.motivo_penalidade = None
    
    db.session.commit()
    flash('Reset Absoluto realizado: Grid, Equipe e CNH reiniciados.', 'warning')
    return redirect(url_for('admin.edit_pilot', pilot_id=pilot.id))

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
        profile.teams.clear()
        profile.pontos_cnh = 0
        
        RaceRegistration.query.filter_by(pilot_id=profile.id).delete()
        
        db.session.commit()
        flash('Piloto possuía histórico. Conta anonimizada para preservar a pontuação das equipes.', 'warning')
    else:
        # EXCLUSÃO TOTAL
        if profile.foto_url:
            path = os.path.join(current_app.config['UPLOAD_FOLDER'], profile.foto_url)
            if os.path.exists(path): os.remove(path)

        profile.teams.clear()
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
    # 1. Seleção de Temporada
    all_active_seasons = Season.query.filter_by(ativa=True).order_by(Season.id.desc()).all()
    selected_season_id = request.args.get('s', type=int)
    
    season_ativa = None
    if selected_season_id:
        season_ativa = next((s for s in all_active_seasons if s.id == selected_season_id), None)
    
    if not season_ativa and all_active_seasons:
        season_ativa = all_active_seasons[0]

    teams = Team.query.order_by(Team.ativa.desc(), Team.grid, Team.nome).all()
    
    # Busca grids configurados para gerar as abas dinamicamente
    configs = GridConfig.query.order_by(GridConfig.ordem).all()
    grid_names = []

    if season_ativa:
        # Tenta pegar grids das corridas da temporada selecionada
        grids_com_corrida = [r[0] for r in db.session.query(Race.grid).filter_by(season_id=season_ativa.id).distinct().all()]
        
        if grids_com_corrida:
            # Ordena usando a ordem do GridConfig se disponível, senão alfabético
            grid_names = sorted(list(set(grids_com_corrida)), 
                                key=lambda x: next((c.ordem for c in configs if c.nome == x), 999))
        else:
            # Se não tem corridas (ex: temporada recém criada), usa o GridConfig global
            grid_names = [c.nome for c in configs]

    if not grid_names:
        # Fallback final
        grid_names = [c.nome for c in configs] if configs else ['ELITE', 'ADVANCED', 'INITIAL']

    return render_template('admin/teams.html', teams=teams, grid_names=grid_names, season_ativa=season_ativa, all_active_seasons=all_active_seasons)

@admin_bp.route('/teams/new', methods=['GET', 'POST'])
def create_team():
    if request.method == 'POST':
        nome = request.form.get('nome')
        grid = request.form.get('grid')
        
        nova_equipe = Team(nome=nome[:50], grid=grid, ativa=True)
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
        
    grid_configs = GridConfig.query.order_by(GridConfig.ordem).all()
    return render_template('admin/create_team.html', grid_configs=grid_configs)

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
        team.pilots.clear()
        team.reserves.clear()
            
        pilot1_id = request.form.get('pilot1')
        pilot2_id = request.form.get('pilot2')
        
        if pilot1_id:
            p1 = PilotProfile.query.get(pilot1_id)
            if p1: team.pilots.append(p1)
        if pilot2_id:
            p2 = PilotProfile.query.get(pilot2_id)
            if p2: team.pilots.append(p2)
            
        reserve1_id = request.form.get('reserve_pilot_1')
        if reserve1_id:
            r1 = PilotProfile.query.get(reserve1_id)
            if r1: team.reserves.append(r1)
            
        reserve2_id = request.form.get('reserve_pilot_2')
        if reserve2_id:
            r2 = PilotProfile.query.get(reserve2_id)
            if r2: team.reserves.append(r2)
            
        db.session.commit()
        flash('Equipe atualizada!', 'success')
        return redirect(url_for('admin.list_teams'))

    # LÓGICA: Apenas pilotos que já pertencem ao MESMO GRID da equipe aparecem aqui (incluindo ADMs).
    # E que não estejam em outra equipe DO MESMO GRID
    all_pilots = PilotProfile.query.join(User).order_by(PilotProfile.nickname).all()
    
    # Filtra pilotos que já estão em OUTRA equipe deste mesmo grid
    final_pilots = []
    for p in all_pilots:
        # Verifica se o piloto participa deste grid (lidando com múltiplos grids "ELITE, ADVANCED")
        p_grids = [g.strip() for g in p.grid.split(',')]
        if team.grid in p_grids:
            # Verifica se já tem equipe NESTE grid (e se não é a própria equipe atual)
            team_in_grid = next((t for t in p.teams if t.grid == team.grid), None)
            # Permite se não tiver equipe, ou se for desta equipe (titular ou reserva)
            is_reserve_here = next((t for t in p.reserve_teams if t.grid == team.grid and t.id == team.id), None)
            
            if (team_in_grid is None or team_in_grid.id == team.id) or is_reserve_here:
                final_pilots.append(p)

    grid_configs = GridConfig.query.order_by(GridConfig.ordem).all()
    return render_template('admin/edit_team.html', team=team, pilots=final_pilots, grid_configs=grid_configs)

@admin_bp.route('/teams/delete/<int:team_id>', methods=['POST'])
def delete_team(team_id):
    if current_user.role != 'SUPER_ADM':
        flash('Permissão negada.', 'danger')
        return redirect(url_for('admin.list_teams'))
        
    team = Team.query.get_or_404(team_id)
    
    # Verifica se a equipe tem histórico (resultados de corrida)
    tem_historico = RaceResult.query.filter_by(team_id=team.id).first()
    
    team.pilots.clear()
    team.reserves.clear()
        
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

    if request.method == 'POST' and 'action' in request.form:
        action = request.form.get('action')
        if action == 'config_grid':
            nome = request.form.get('nome')
            vagas_input = int(request.form.get('vagas') or 20)
            vagas = vagas_input if vagas_input in [20, 22] else 20
            ordem = int(request.form.get('ordem') or 0)
            exibir_lastro = True if request.form.get('exibir_lastro') == 'on' else False
            
            existing = GridConfig.query.filter_by(nome=nome).first()
            if existing:
                existing.vagas = vagas
                existing.ordem = ordem
                existing.exibir_lastro = exibir_lastro
            else:
                db.session.add(GridConfig(nome=nome, vagas=vagas, ordem=ordem, exibir_lastro=exibir_lastro))
            
            db.session.commit()
            flash(f'Configuração do grid {nome} salva.', 'success')
            return redirect(url_for('admin.seletiva'))

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

    # LÓGICA: Agora aparecem TODOS os pilotos, pois podem participar de múltiplos grids
    pilotos = PilotProfile.query.order_by(PilotProfile.nickname).all()
    entradas = SeletivaEntry.query.order_by(SeletivaEntry.tempo_ms.asc()).all()
    grid_configs = GridConfig.query.order_by(GridConfig.ordem).all()
    
    return render_template('admin/seletiva.html', pilotos=pilotos, entradas=entradas, grid_configs=grid_configs)

@admin_bp.route('/seletiva/delete/<int:entry_id>', methods=['POST'])
def delete_seletiva_entry(entry_id):
    entry = SeletivaEntry.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()
    flash('Tempo removido.', 'info')
    return redirect(url_for('admin.seletiva'))

@admin_bp.route('/seletiva/grid/<int:config_id>/delete', methods=['POST'])
def delete_grid_config(config_id):
    if current_user.role not in ['SUPER_ADM', 'ADM']:
        return redirect(url_for('admin.dashboard'))
    
    config = GridConfig.query.get_or_404(config_id)
    db.session.delete(config)
    db.session.commit()
    flash(f'Configuração do grid {config.nome} removida.', 'info')
    return redirect(url_for('admin.seletiva'))

@admin_bp.route('/seletiva/close', methods=['POST'])
def close_seletiva():
    if current_user.role != 'SUPER_ADM':
        flash('Apenas Super Admin pode aplicar o grid.', 'danger')
        return redirect(url_for('admin.seletiva'))
        
    season_name = request.form.get('season_name')
    if not season_name:
        flash('O nome da temporada é obrigatório para encerrar a seletiva.', 'danger')
        return redirect(url_for('admin.seletiva'))

    # 1. Criar a nova temporada (sem desativar as anteriores)
    nova_season = Season(
        nome=season_name, 
        ativa=True, 
        data_inicio=datetime.utcnow().date()
    )
    db.session.add(nova_season)

    entradas = SeletivaEntry.query.order_by(SeletivaEntry.tempo_ms.asc()).all()
    configs = GridConfig.query.order_by(GridConfig.ordem).all()
    
    if not configs:
        # Fallback para o comportamento antigo se não houver configs
        for i, entry in enumerate(entradas):
            pos = i + 1
            # Preserva grids anteriores
            grids_atuais = set([g.strip() for g in entry.piloto.grid.split(',')]) if entry.piloto.grid and entry.piloto.grid != 'SEM_GRID' else set()
            
            if pos <= 20: grids_atuais.add('ELITE')
            elif pos <= 40: grids_atuais.add('ADVANCED')
            elif pos <= 60: grids_atuais.add('INITIAL')
            else: grids_atuais.add('RESERVA')
            
            if 'SEM_GRID' in grids_atuais and len(grids_atuais) > 1: grids_atuais.remove('SEM_GRID')
            entry.piloto.grid = ",".join(sorted(list(grids_atuais)))
    else:
        # Lógica dinâmica baseada nas vagas configuradas
        for i, entry in enumerate(entradas):
            pos = i + 1
            alocado = False
            vagas_acumuladas = 0
            
            # Preserva grids anteriores
            grids_atuais = set([g.strip() for g in entry.piloto.grid.split(',')]) if entry.piloto.grid and entry.piloto.grid != 'SEM_GRID' else set()

            for config in configs:
                vagas_acumuladas += config.vagas
                if pos <= vagas_acumuladas:
                    grids_atuais.add(config.nome)
                    alocado = True
                    break
            if not alocado:
                grids_atuais.add('RESERVA')
            
            if 'SEM_GRID' in grids_atuais and len(grids_atuais) > 1: grids_atuais.remove('SEM_GRID')
            entry.piloto.grid = ",".join(sorted(list(grids_atuais)))

    # 2. Limpar a tabela de seletiva para o próximo ciclo
    SeletivaEntry.query.delete()
    
    db.session.commit()
    flash(f'Temporada "{season_name}" criada e {len(entradas)} pilotos alocados com sucesso!', 'success')
    return redirect(url_for('admin.seasons'))

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
    
    # Alerta se houver link mas não for embedável (ex: Clips)
    if protesto.video_link and not embed_acusacao:
        flash('O vídeo de acusação é um Clip ou link não suportado para player. Use o link direto.', 'info')
    if protesto.video_defesa and not embed_defesa:
        flash('O vídeo de defesa é um Clip ou link não suportado para player. Use o link direto.', 'info')

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
            if protesto.status == 'CONCLUIDO':
                flash('Este caso já foi encerrado anteriormente. Para alterar o veredito, primeiro REABRA o caso.', 'warning')
                return redirect(url_for('admin.view_protest', protest_id=protesto.id))

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
            elif veredito == 'ADVERTENCIA': pontos_perda = 0 # Advertência é contada dinamicamente
            
            if pontos_perda > 0:
                if resultado_corrida:
                    resultado_corrida.pontos_ganhos -= pontos_perda
            
            db.session.commit()
            flash('Caso encerrado e punições aplicadas.', 'success')
            return redirect(url_for('admin.protests'))
            
        if 'reabrir' in request.form and current_user.role == 'SUPER_ADM':
            if protesto.status != 'CONCLUIDO':
                flash('Este caso não está concluído para ser reaberto.', 'warning')
                return redirect(url_for('admin.view_protest', protest_id=protesto.id))

            piloto = protesto.acusado
            veredito_anterior = protesto.veredito_final
            resultado_corrida = RaceResult.query.filter_by(race_id=protesto.etapa_id, pilot_id=piloto.id).first()
            
            pontos_devolver = 0
            if veredito_anterior == 'LEVE': pontos_devolver = 3
            elif veredito_anterior == 'MEDIA': pontos_devolver = 5
            elif veredito_anterior == 'GRAVE': pontos_devolver = 10
            
            if pontos_devolver > 0:
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
        
        if pontos_devolver > 0:
            if resultado_corrida:
                resultado_corrida.pontos_ganhos += pontos_devolver

    # Limpa votos associados para evitar erro de integridade (FK)
    VotoComissario.query.filter_by(protesto_id=protesto.id).delete()
    
    db.session.delete(protesto)
    db.session.commit()
    
    flash('Pedido de punição removido e punições revertidas com sucesso.', 'success')
    return redirect(url_for('admin.protests'))