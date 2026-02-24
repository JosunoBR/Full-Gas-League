import os
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import check_password_hash
from sqlalchemy import func, case
from app.models import db, Season, Race, PilotProfile, Protesto, RaceResult, VotoComissario, Team, RaceRegistration, User, Invite, News, GridConfig, SeasonChampion, PilotGridPhoto
from app.utils import allowed_file, get_embed_url, ORDEM_CARROS

public_bp = Blueprint('public', __name__)

# --- ROTAS PRINCIPAIS (HOME E LOGIN) ---

@public_bp.route('/')
def home():
    all_active_seasons = Season.query.filter_by(ativa=True).order_by(Season.id.asc()).all()
    
    # Permite selecionar a temporada via parâmetro 's' na URL
    selected_season_id = request.args.get('s', type=int)
    season_ativa = None
    if selected_season_id:
        season_ativa = next((s for s in all_active_seasons if s.id == selected_season_id), None)
    
    # Se nenhuma temporada foi selecionada ou a selecionada não é ativa, usa a mais recente como padrão
    if not season_ativa and all_active_seasons:
        season_ativa = all_active_seasons[0]
    
    # Filtra os grids que realmente possuem atividade nesta temporada
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
    
    standings = { name: [] for name in grid_names }
    constructors = { name: [] for name in grid_names }
    calendar = { name: [] for name in grid_names }
    last_races = { name: None for name in grid_names }
    noticias = News.query.order_by(News.data_publicacao.desc()).limit(5).all()
    pilots_by_grid = { name: [] for name in grid_names }
    
    if season_ativa: # Só busca dados se houver uma temporada ativa selecionada
        # 1. Calcular Pontos dos Pilotos
        pilotos = PilotProfile.query.join(User).all()
        for p in pilotos:
            resultados = [r for r in p.race_results if r.race.season_id == season_ativa.id]
            
            # Lógica ajustada: Apenas pilotos titulares aparecem na tabela (Reservas pontuam apenas para equipe)
            p_grids = set([g.strip() for g in p.grid.split(',') if g.strip()])

            for gname in p_grids:
                if gname in standings:
                    # Filtra resultados apenas deste grid específico
                    res_no_grid = [r for r in resultados if r.race.grid == gname]
                    pontos_totais = float(sum(r.pontos_ganhos for r in res_no_grid)) - float(p.penalidade_campeonato or 0)
                    vitorias = sum(1 for r in res_no_grid if r.posicao == 1 and not r.dsq)
                    
                    # Lógica de Quali Ban
                    ultimo_p = Protesto.query.filter_by(acusado_id=p.id, status='CONCLUIDO')\
                        .order_by(Protesto.data_fechamento.desc()).first()
                    quali_ban = False
                    if ultimo_p and ultimo_p.veredito_final in ['MEDIA', 'GRAVE']:
                        ultima_res = RaceResult.query.join(Race).filter(RaceResult.pilot_id == p.id, Race.status == 'Concluida').order_by(Race.data_corrida.desc()).first()
                        if not ultima_res or ultimo_p.data_fechamento.date() >= ultima_res.race.data_corrida:
                            quali_ban = True

                    # Verifica se existe foto específica para este grid
                    foto_final = p.foto_url
                    for gp in p.grid_photos:
                        if gp.grid == gname:
                            foto_final = gp.foto_url
                            break

                    # Busca a equipe do piloto para este grid
                    team = next((t for t in p.teams if t.grid == gname), None)
                    is_reserve = False

                    # Se não for titular, verifica se é reserva oficial
                    if not team:
                        reserve_team = next((t for t in p.reserve_teams if t.grid == gname), None)
                        if reserve_team:
                            team = reserve_team
                            is_reserve = True
                    
                    team_name = team.nome if team else 'Sem Equipe'

                    standings[gname].append({'piloto': p, 'pontos': pontos_totais, 'vitorias': vitorias, 'carro': '', 'quali_ban': quali_ban, 'foto_url': foto_final, 'team_name': team_name, 'is_reserve': is_reserve})
        
        # 2. Ordenar e Aplicar Lastro (Carro)
        # Cria mapa de configs para acesso rápido
        grid_configs_map = {c.nome: c for c in GridConfig.query.all()}

        for grid in standings: 
            standings[grid].sort(key=lambda x: (x['pontos'], x['vitorias']), reverse=True)
            
            # Verifica se o grid exibe lastro
            cfg = grid_configs_map.get(grid)
            exibir_lastro = cfg.exibir_lastro if cfg and hasattr(cfg, 'exibir_lastro') else True

            # Distribui os carros baseados na posição
            for i, item in enumerate(standings[grid]):
                if exibir_lastro:
                    if i < len(ORDEM_CARROS):
                        item['carro'] = ORDEM_CARROS[i]
                    else:
                        item['carro'] = "McLaren (Extra)"
                else:
                    item['carro'] = "-"

        # 3. Calcular Construtores
        # Otimização: Agregação no banco de dados para evitar N+1 queries
        stats_query = db.session.query(
            RaceResult.team_id,
            func.sum(RaceResult.pontos_ganhos).label('total_pontos'),
            func.sum(case(( (RaceResult.posicao == 1) & (RaceResult.dsq == False), 1 ), else_=0)).label('total_vitorias')
        ).join(Race).filter(
            Race.season_id == season_ativa.id,
            RaceResult.team_id != None
        ).group_by(RaceResult.team_id).all()
        
        team_stats = { s.team_id: {'pontos': float(s.total_pontos or 0), 'vitorias': int(s.total_vitorias or 0)} for s in stats_query }

        teams = Team.query.filter_by(ativa=True).all()
        for t in teams:
            if t.grid in constructors:
                stats = team_stats.get(t.id, {'pontos': 0.0, 'vitorias': 0})
                
                # Subtrai penalidades administrativas dos pilotos ATUAIS da equipe
                penalidades_pilotos = sum(float(p.penalidade_campeonato or 0) for p in t.pilots)
                pontos_finais = stats['pontos'] - penalidades_pilotos
                
                constructors[t.grid].append({'equipe': t, 'pontos': pontos_finais, 'vitorias': stats['vitorias']})
        
        for grid in constructors: constructors[grid].sort(key=lambda x: (x['pontos'], x['vitorias']), reverse=True)
        
        # 4. Calendário e Últimas Corridas (Pódio)
        all_races = Race.query.filter_by(season_id=season_ativa.id).order_by(Race.data_corrida).all()
        for r in all_races:
            if r.grid in calendar:
                calendar[r.grid].append(r)
        
        # Identifica a última corrida concluída de cada grid para o destaque
        for grid in last_races:
            concluidas = [r for r in calendar[grid] if r.status == 'Concluida']
            if concluidas:
                last_races[grid] = concluidas[-1] # Pega a última da lista (mais recente)
        
        # 5. Lista de Pilotos por Grid (Exclui Reservas)
        # Busca todos os pilotos (mesmo SEM_GRID, pois podem ter equipe em temporada antiga)
        all_pilots_query = PilotProfile.query.join(User).order_by(PilotProfile.nickname).all()
        
        for g in grid_names:
            for p in all_pilots_query:
                # Verifica se o piloto pertence ao grid (via texto do perfil OU associação de equipe)
                p_grids = [x.strip() for x in p.grid.split(',')]
                
                # Busca a equipe do piloto para este grid
                team = next((t for t in p.teams if t.grid == g), None)
                
                # Pertence ao grid se: Está no perfil OU tem equipe titular
                if g in p_grids or team:
                    # Verifica se existe foto específica para este grid
                    foto_final = p.foto_url
                    for gp in p.grid_photos:
                        if gp.grid == g:
                            foto_final = gp.foto_url
                            break
                    
                    # Verifica se é reserva oficial (para excluir do carrossel principal)
                    reserve_team = next((t for t in p.reserve_teams if t.grid == g), None)

                    # FIX: Verifica se o piloto já está na lista deste grid para evitar duplicatas (P1, P1...)
                    # Inclui Titulares OU Pilotos Sem Equipe (Exclui apenas Reservas Oficiais)
                    if (team or not reserve_team) and not any(item['data'].id == p.id for item in pilots_by_grid[g]):
                        pilots_by_grid[g].append({'data': p, 'foto_url': foto_final, 'team': team})

    return render_template('home.html', standings=standings, constructors=constructors, calendar=calendar, last_races=last_races, season_ativa=season_ativa, noticias=noticias, pilots_by_grid=pilots_by_grid, grid_names=grid_names, all_active_seasons=all_active_seasons)

@public_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'PILOTO':
            return redirect(url_for('public.my_profile'))
        elif current_user.role in ['SUPER_ADM', 'ADM']:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('public.home'))

    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash('Login inválido. Verifique suas credenciais.', 'danger')
            return redirect(url_for('public.login'))

        login_user(user, remember=remember)

        if user.role == 'PILOTO':
            return redirect(url_for('public.my_profile'))
        elif user.role in ['SUPER_ADM', 'ADM']:
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('public.home'))

    return render_template('login.html')

@public_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('public.home'))

    if request.method == 'POST':
        token_input = request.form.get('token')
        email = (request.form.get('email') or '').strip().lower()
        nickname = (request.form.get('nickname') or '')
        telefone = request.form.get('telefone')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not token_input:
            flash('O código de convite é obrigatório.', 'warning')
            return redirect(url_for('public.register'))
            
        invite = Invite.query.filter_by(token=token_input, used=False).first()
        if not invite:
            flash('Código de convite inválido ou já utilizado.', 'danger')
            return redirect(url_for('public.register'))

        if not nickname or nickname.strip() == "":
            flash('O campo Nickname é obrigatório.', 'danger')
            return redirect(url_for('public.register'))

        if password != confirm_password:
            flash('As senhas não conferem.', 'danger')
            return redirect(url_for('public.register'))

        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash('Este e-mail já está cadastrado.', 'warning')
            return redirect(url_for('public.register'))
        
        new_user = User(email=email, username=nickname[:50], role='PILOTO')
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.flush()

        new_profile = PilotProfile(
            user_id=new_user.id, 
            nickname=nickname[:50], 
            nome_real=nickname[:100], 
            grid='SEM_GRID',
            telefone=telefone[:20] if telefone else None
        )
        db.session.add(new_profile)
        invite.used = True
        db.session.commit()

        flash('Conta criada com sucesso! Faça login para continuar.', 'success')
        return redirect(url_for('public.login'))

    return render_template('register.html')

@public_bp.route('/logout')
def logout():
    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('public.home'))

@public_bp.route('/regulamento')
def rules():
    return render_template('public/regulamento.html')

@public_bp.route('/transparencia')
def transparency():
    return render_template('public/how_it_works.html')

@public_bp.route('/hall-of-fame')
def hall_of_fame():
    # Busca temporadas encerradas que tenham campeões registrados
    seasons_ids = db.session.query(SeasonChampion.season_id).distinct().all()
    ids = [s[0] for s in seasons_ids]
    seasons = Season.query.filter(Season.id.in_(ids)).order_by(Season.id.desc()).all()
    
    data = {}
    for s in seasons:
        champs = SeasonChampion.query.filter_by(season_id=s.id).all()
        grids = list(set([c.grid for c in champs]))
        data[s.id] = {}
        for g in grids:
            data[s.id][g] = [c for c in champs if c.grid == g]
            
    return render_template('public/hall_of_fame.html', seasons=seasons, data=data)

@public_bp.route('/news/<int:news_id>')
def news_detail(news_id):
    noticia = News.query.get_or_404(news_id)
    return render_template('public/news_detail.html', noticia=noticia)

# --- PERFIL DO PILOTO ---

@public_bp.route('/piloto/<int:pilot_id>')
def public_profile(pilot_id):
    perfil = PilotProfile.query.get_or_404(pilot_id)
    
    # Se for o próprio dono vendo seu perfil público, redireciona para o privado (com controles)
    if current_user.is_authenticated and current_user.pilot_profile and current_user.pilot_profile.id == perfil.id:
        return redirect(url_for('public.my_profile'))

    # Identifica contextos (Temporada + Grid) ativos para este piloto
    active_seasons = Season.query.filter_by(ativa=True).order_by(Season.id.desc()).all()
    available_contexts = []
    p_grids = [g.strip() for g in perfil.grid.split(',')] if perfil.grid else []

    for s in active_seasons:
        # Grids onde o piloto já tem resultados nesta temporada
        grids_res = db.session.query(Race.grid).join(RaceResult).filter(
            RaceResult.pilot_id == perfil.id,
            Race.season_id == s.id
        ).distinct().all()
        grids = [g[0] for g in grids_res]
        
        # Filtra grids válidos para esta temporada (evita mostrar grids de outras temporadas)
        season_races_grids = [r[0] for r in db.session.query(Race.grid).filter_by(season_id=s.id).distinct().all()]
        valid_season_grids = set(season_races_grids)
        if not season_races_grids:
             configs = GridConfig.query.all()
             if configs:
                 valid_season_grids = set(c.nome for c in configs)
             else:
                 valid_season_grids = set(p_grids)

        # Inclui todos os grids onde o piloto está registrado
        for pg in p_grids:
            if pg not in grids and pg in valid_season_grids:
                grids.append(pg)
        
        for g in grids:
            available_contexts.append({'season_id': s.id, 'season_nome': s.nome, 'grid': g})

    sel_season_id = request.args.get('s', type=int) # Mantém o 's' para seleção de temporada
    sel_grid = request.args.get('g')
    
    current_context = None
    if sel_season_id and sel_grid:
        current_context = next((c for c in available_contexts if c['season_id'] == sel_season_id and c['grid'] == sel_grid), None)
    
    if not current_context and available_contexts:
        default_grid = p_grids[0] if p_grids else 'SEM_GRID' # Tenta usar o primeiro grid do perfil como padrão
        current_context = next((c for c in available_contexts if c['grid'] == default_grid), available_contexts[0])
    
    # Substituição dinâmica da foto baseada no contexto (Grid)
    if current_context:
        for gp in perfil.grid_photos:
            if gp.grid == current_context['grid']:
                perfil.foto_url = gp.foto_url # Substitui temporariamente no objeto (sem commit) para exibição
    
    # Determina a equipe para o contexto atual
    current_team = None
    if current_context:
        current_team = next((t for t in perfil.teams if t.grid == current_context['grid']), None)
        if not current_team:
            current_team = next((t for t in perfil.reserve_teams if t.grid == current_context['grid']), None)
    
    # Cálculo dinâmico de CNH e Advertências para o contexto atual
    if current_context:
        cnh_info = perfil.get_cnh_info(current_context['season_id'], current_context['grid'])
        perfil.pontos_cnh = cnh_info['cnh'] # Atualiza objeto em memória para exibição
        perfil.advertencias_acumuladas = cnh_info['advertencias']

    # Estatísticas da Temporada
    meus_pontos_camp = 0
    desempenho_temporada = []
    if current_context:
        s_id = current_context['season_id']
        g_name = current_context['grid']
        
        resultados_contexto = [r for r in perfil.race_results if r.race.season_id == s_id and r.race.grid == g_name]
        meus_pontos_camp = float(sum(r.pontos_ganhos for r in resultados_contexto)) - float(perfil.penalidade_campeonato or 0)
        
        corridas = Race.query.filter_by(season_id=s_id, grid=g_name).order_by(Race.data_corrida).all()
        for race in corridas:
            resultado = next((r for r in race.results if r.pilot_id == perfil.id), None)
            desempenho_temporada.append({
                'gp': race.nome_gp, 'data': race.data_corrida, 'status_corrida': race.status,
                'participou': True if resultado and not resultado.ausencia else False,
                'posicao': resultado.posicao if resultado else 0,
                'pontos': resultado.pontos_ganhos if resultado else 0,
                'dnf': resultado.dnf if resultado else False, 'dsq': resultado.dsq if resultado else False
            })

    # Verificação de Quali Ban para o Perfil Público
    ultimo_p = Protesto.query.filter_by(acusado_id=perfil.id, status='CONCLUIDO')\
        .order_by(Protesto.data_fechamento.desc()).first()
    quali_ban = False
    if ultimo_p and ultimo_p.veredito_final in ['MEDIA', 'GRAVE']:
        ultima_res = RaceResult.query.join(Race).filter(RaceResult.pilot_id == perfil.id, Race.status == 'Concluida').order_by(Race.data_corrida.desc()).first()
        if not ultima_res or ultimo_p.data_fechamento.date() >= ultima_res.race.data_corrida:
            quali_ban = True

    # Histórico de Carreira
    seasons_fechadas = Season.query.filter_by(ativa=False).order_by(Season.id.desc()).all()
    historico_carreira = []
    for s in seasons_fechadas:
        resultados_na_season = [r for r in perfil.race_results if r.race.season_id == s.id]
        if resultados_na_season:
            pts = sum(r.pontos_ganhos for r in resultados_na_season)
            vitorias = sum(1 for r in resultados_na_season if r.posicao == 1 and not r.dsq)
            grids_corridos = [r.race.grid for r in resultados_na_season]
            grid_predominante = max(set(grids_corridos), key=grids_corridos.count) if grids_corridos else "N/A"
            historico_carreira.append({'season_nome': s.nome, 'grid': grid_predominante, 'pontos': pts, 'vitorias': vitorias})

    return render_template('pilot/profile.html', 
                           perfil=perfil, 
                           is_owner=False,
                           meus_pontos_camp=meus_pontos_camp, 
                           desempenho_temporada=desempenho_temporada, 
                           meus_protestos=[], 
                           defesas_pendentes=[], 
                           historico=[],
                           total_punicoes=0,
                           historico_carreira=historico_carreira,
                           checkin_race=None,
                           registro_atual=None,
                           quali_ban=quali_ban,
                           available_contexts=available_contexts,
                           current_context=current_context,
                           current_team=current_team)

@public_bp.route('/meu-perfil')
@login_required
def my_profile():
    if current_user.pilot_profile:
        perfil = current_user.pilot_profile
    elif current_user.role in ['ADM', 'SUPER_ADM']:
        perfil = PilotProfile(user_id=current_user.id, nickname=current_user.username[:50], nome_real=current_user.username[:100], grid='SEM_GRID')
        db.session.add(perfil)
        db.session.commit()
        flash('Perfil de piloto ativado para Administrador.', 'success')
    else:
        return redirect(url_for('public.home'))

    # Identifica contextos (Temporada + Grid) ativos para este piloto
    active_seasons = Season.query.filter_by(ativa=True).order_by(Season.id.desc()).all()
    available_contexts = []
    p_grids = [g.strip() for g in perfil.grid.split(',')] if perfil.grid else []

    for s in active_seasons:
        # Grids onde o piloto já tem resultados nesta temporada
        grids_res = db.session.query(Race.grid).join(RaceResult).filter(
            RaceResult.pilot_id == perfil.id,
            Race.season_id == s.id
        ).distinct().all()
        grids = [g[0] for g in grids_res]
        
        # Filtra grids válidos para esta temporada (evita mostrar grids de outras temporadas)
        season_races_grids = [r[0] for r in db.session.query(Race.grid).filter_by(season_id=s.id).distinct().all()]
        valid_season_grids = set(season_races_grids)
        if not season_races_grids:
             configs = GridConfig.query.all()
             if configs:
                 valid_season_grids = set(c.nome for c in configs)
             else:
                 valid_season_grids = set(p_grids)

        # Inclui todos os grids onde o piloto está registrado
        for pg in p_grids:
            if pg not in grids and pg in valid_season_grids:
                grids.append(pg)
        
        for g in grids:
            available_contexts.append({'season_id': s.id, 'season_nome': s.nome, 'grid': g})

    sel_season_id = request.args.get('s', type=int) # Mantém o 's' para seleção de temporada
    sel_grid = request.args.get('g')
    
    current_context = None
    if sel_season_id and sel_grid:
        current_context = next((c for c in available_contexts if c['season_id'] == sel_season_id and c['grid'] == sel_grid), None)
    
    if not current_context and available_contexts:
        default_grid = p_grids[0] if p_grids else 'SEM_GRID' # Tenta usar o primeiro grid do perfil como padrão
        current_context = next((c for c in available_contexts if c['grid'] == default_grid), available_contexts[0])
    
    # Substituição dinâmica da foto baseada no contexto (Grid)
    if current_context:
        for gp in perfil.grid_photos:
            if gp.grid == current_context['grid']:
                perfil.foto_url = gp.foto_url # Substitui temporariamente para exibição
    
    # Determina a equipe para o contexto atual
    current_team = None
    if current_context:
        current_team = next((t for t in perfil.teams if t.grid == current_context['grid']), None)
        if not current_team:
            current_team = next((t for t in perfil.reserve_teams if t.grid == current_context['grid']), None)

    # Cálculo dinâmico de CNH e Advertências para o contexto atual
    if current_context:
        cnh_info = perfil.get_cnh_info(current_context['season_id'], current_context['grid'])
        perfil.pontos_cnh = cnh_info['cnh'] # Atualiza objeto em memória para exibição
        perfil.advertencias_acumuladas = cnh_info['advertencias']

    if perfil.esta_banido():
        flash('ALERTA: Sua CNH está zerada ou negativa. Você está suspenso das atividades de pista.', 'danger')
    
    checkin_race = None
    registro_atual = None
    
    # Lógica de Check-in vinculada ao contexto selecionado
    hoje = datetime.utcnow().date()
    if current_context:
        # Verifica se o piloto pertence ao grid atual ou é reserva. 
        # Pilotos 'SEM_GRID' com histórico antigo não devem receber check-in.
        pode_ver_checkin = (current_context['grid'] in p_grids) or ('RESERVA' in p_grids)

        if pode_ver_checkin:
            proxima = Race.query.filter(
                Race.season_id == current_context['season_id'],
                Race.grid == current_context['grid'],
                Race.status != 'Concluida',
                Race.data_corrida >= hoje
            ).order_by(Race.data_corrida).first()

            if proxima and proxima.data_corrida and (proxima.data_corrida - hoje).days <= 2:
                reg = RaceRegistration.query.filter_by(race_id=proxima.id, pilot_id=perfil.id).first()
                # Só exibe o bloco de check-in se ainda não houver resposta confirmada ou justificada
                if not reg or reg.status not in ['CONFIRMADO', 'JUSTIFICADO']:
                    checkin_race = proxima
                    registro_atual = reg

    # Estatísticas da Temporada
    meus_pontos_camp = 0
    desempenho_temporada = []
    if current_context:
        s_id = current_context['season_id']
        g_name = current_context['grid']
        
        resultados_contexto = [r for r in perfil.race_results if r.race.season_id == s_id and r.race.grid == g_name]
        meus_pontos_camp = float(sum(r.pontos_ganhos for r in resultados_contexto)) - float(perfil.penalidade_campeonato or 0)
        
        corridas = Race.query.filter_by(season_id=s_id, grid=g_name).order_by(Race.data_corrida).all()
        for race in corridas:
            resultado = next((r for r in race.results if r.pilot_id == perfil.id), None)
            desempenho_temporada.append({
                'gp': race.nome_gp, 'data': race.data_corrida, 'status_corrida': race.status,
                'participou': True if resultado and not resultado.ausencia else False,
                'posicao': resultado.posicao if resultado else 0,
                'pontos': resultado.pontos_ganhos if resultado else 0,
                'dnf': resultado.dnf if resultado else False, 'dsq': resultado.dsq if resultado else False
            })

    # Protestos e Defesas
    meus_protestos = Protesto.query.filter_by(acusador_id=perfil.id).order_by(Protesto.data_criacao.desc()).all()
    
    # Busca defesas onde o piloto é o acusado, o caso não está concluído e ele ainda não enviou o argumento
    defesas_pendentes = Protesto.query.filter(
        Protesto.acusado_id == perfil.id,
        Protesto.status.in_(['AGUARDANDO_DEFESA', 'EM_VOTACAO']),
        Protesto.argumento_defesa == None
    ).all()
    
    # Histórico de Punições e Cálculo Total
    historico_punicoes = Protesto.query.filter(Protesto.acusado_id == perfil.id, Protesto.status != 'AGUARDANDO_DEFESA').order_by(Protesto.data_fechamento.desc()).all()
    
    total_punicoes = 0
    for h in historico_punicoes:
        if h.veredito_final == 'LEVE': total_punicoes += 3
        elif h.veredito_final == 'MEDIA': total_punicoes += 5
        elif h.veredito_final == 'GRAVE': total_punicoes += 10

    # Histórico de Carreira (Temporadas Passadas)
    seasons_fechadas = Season.query.filter_by(ativa=False).order_by(Season.id.desc()).all()
    historico_carreira = []
    for s in seasons_fechadas:
        resultados_na_season = [r for r in perfil.race_results if r.race.season_id == s.id]
        if resultados_na_season:
            pts = sum(r.pontos_ganhos for r in resultados_na_season)
            vitorias = sum(1 for r in resultados_na_season if r.posicao == 1 and not r.dsq)
            grids_corridos = [r.race.grid for r in resultados_na_season]
            grid_predominante = max(set(grids_corridos), key=grids_corridos.count) if grids_corridos else "N/A"
            historico_carreira.append({'season_nome': s.nome, 'grid': grid_predominante, 'pontos': pts, 'vitorias': vitorias})

    # Verificação de Quali Ban para o Perfil Privado
    ultimo_p = Protesto.query.filter_by(acusado_id=perfil.id, status='CONCLUIDO')\
        .order_by(Protesto.data_fechamento.desc()).first()
    quali_ban = False
    if ultimo_p and ultimo_p.veredito_final in ['MEDIA', 'GRAVE']:
        ultima_res = RaceResult.query.join(Race).filter(RaceResult.pilot_id == perfil.id, Race.status == 'Concluida').order_by(Race.data_corrida.desc()).first()
        if not ultima_res or ultimo_p.data_fechamento.date() >= ultima_res.race.data_corrida:
            quali_ban = True

    return render_template('pilot/profile.html', 
                           perfil=perfil,
                           is_owner=True,
                           meus_pontos_camp=meus_pontos_camp, 
                           desempenho_temporada=desempenho_temporada, 
                           meus_protestos=meus_protestos, 
                           defesas_pendentes=defesas_pendentes, 
                           historico=historico_punicoes,
                           total_punicoes=total_punicoes,
                           historico_carreira=historico_carreira,
                           checkin_race=checkin_race,
                           registro_atual=registro_atual,
                           quali_ban=quali_ban,
                           available_contexts=available_contexts,
                           current_context=current_context,
                           current_team=current_team)

# --- AÇÕES DE CHECK-IN ---

@public_bp.route('/checkin/confirm/<int:race_id>', methods=['POST'])
@login_required
def checkin_confirm(race_id):
    if not current_user.pilot_profile: return redirect(url_for('public.home'))
    
    if current_user.pilot_profile.esta_banido():
        flash('Você está com a CNH Suspensa/Banida e não pode correr.', 'danger')
        return redirect(url_for('public.my_profile'))
        
    registro = RaceRegistration.query.filter_by(race_id=race_id, pilot_id=current_user.pilot_profile.id).first()
    if not registro:
        registro = RaceRegistration(race_id=race_id, pilot_id=current_user.pilot_profile.id)
        db.session.add(registro)
    
    registro.status = 'CONFIRMADO'
    registro.justificativa = None
    registro.data_resposta = datetime.utcnow()
    db.session.commit()
    flash('Presença confirmada! Boa corrida!', 'success')
    return redirect(url_for('public.my_profile'))

@public_bp.route('/checkin/absent/<int:race_id>', methods=['POST'])
@login_required
def checkin_absent(race_id):
    if not current_user.pilot_profile: return redirect(url_for('public.home'))
    motivo = request.form.get('justificativa')
    if not motivo:
        flash('É obrigatório informar o motivo da ausência.', 'warning')
        return redirect(url_for('public.my_profile'))

    registro = RaceRegistration.query.filter_by(race_id=race_id, pilot_id=current_user.pilot_profile.id).first()
    if not registro:
        registro = RaceRegistration(race_id=race_id, pilot_id=current_user.pilot_profile.id)
        db.session.add(registro)
    
    registro.status = 'JUSTIFICADO'
    registro.justificativa = motivo
    registro.data_resposta = datetime.utcnow()
    db.session.commit()
    flash('Ausência registrada. Agradecemos o aviso.', 'info')
    return redirect(url_for('public.my_profile'))

# --- PÁGINAS DE EQUIPE E OUTRAS ---

@public_bp.route('/equipe/<int:team_id>')
def team_profile(team_id):
    team = Team.query.get_or_404(team_id)
    
    # FIX: Suporte a Temporadas Paralelas
    # Permite selecionar qual temporada visualizar (padrão: a mais recente ativa)
    all_active_seasons = Season.query.filter_by(ativa=True).order_by(Season.id.desc()).all()
    selected_season_id = request.args.get('s', type=int)
    
    season_ativa = next((s for s in all_active_seasons if s.id == selected_season_id), None)
    if not season_ativa and all_active_seasons:
        season_ativa = all_active_seasons[0]

    total_pontos = 0
    total_vitorias = 0
    stats_pilotos = []
    if season_ativa:
        for piloto in team.pilots:
            pts = sum(r.pontos_ganhos for r in piloto.race_results if r.race.season_id == season_ativa.id)
            wins = sum(1 for r in piloto.race_results if r.race.season_id == season_ativa.id and r.posicao == 1 and not r.dsq)
            
            # Aplica penalidade administrativa ao piloto individualmente
            pts_liquidos = pts - float(piloto.penalidade_campeonato or 0)
            
            stats_pilotos.append({'piloto': piloto, 'pontos': pts_liquidos, 'vitorias': wins})
            
            # Soma ao total da equipe
            total_pontos += pts_liquidos
            total_vitorias += wins
            
    return render_template('public/team_profile.html', team=team, total_pontos=total_pontos, total_vitorias=total_vitorias, stats_pilotos=stats_pilotos, season_ativa=season_ativa, all_active_seasons=all_active_seasons)

# --- AÇÕES DO PILOTO (DEFESA, ATUALIZAR PERFIL, PROTESTAR) ---

@public_bp.route('/defender/<int:protest_id>', methods=['GET', 'POST'])
@login_required
def submit_defense(protest_id):
    protesto = Protesto.query.get_or_404(protest_id)
    if protesto.acusado_id != current_user.pilot_profile.id: return redirect(url_for('public.my_profile'))
    if protesto.status == 'CONCLUIDO': return redirect(url_for('public.my_profile'))
    if request.method == 'POST':
        protesto.video_defesa = request.form.get('video_defesa')
        protesto.argumento_defesa = request.form.get('argumento_defesa')
        if protesto.status == 'AGUARDANDO_DEFESA': protesto.status = 'EM_VOTACAO'
        db.session.commit()
        return redirect(url_for('public.my_profile'))
    return render_template('pilot/defense.html', protesto=protesto)

@public_bp.route('/protesto/<int:protest_id>/delete', methods=['POST'])
@login_required
def delete_protest(protest_id):
    protesto = Protesto.query.get_or_404(protest_id)
    if protesto.acusador_id != current_user.pilot_profile.id: return redirect(url_for('public.my_profile'))
    if protesto.status == 'CONCLUIDO': return redirect(url_for('public.my_profile'))
    VotoComissario.query.filter_by(protesto_id=protesto.id).delete()
    db.session.delete(protesto)
    db.session.commit()
    return redirect(url_for('public.my_profile'))

@public_bp.route('/perfil/update', methods=['POST'])
@login_required
def update_profile():
    if not current_user.pilot_profile: return redirect(url_for('public.home'))
    new_nickname = (request.form.get('nickname') or '')[:50]
    current_user.pilot_profile.nome_real = request.form.get('nome_real')[:100]
    current_user.pilot_profile.nickname = new_nickname
    current_user.username = new_nickname # Mantém o login em sincronia
    current_user.pilot_profile.telefone = request.form.get('telefone')[:20] if request.form.get('telefone') else None
    
    # TROCA DE SENHA PELO USUÁRIO
    nova_senha = request.form.get('password')
    confirma = request.form.get('confirm_password')
    if nova_senha and nova_senha.strip() != "":
        if nova_senha == confirma:
            current_user.set_password(nova_senha)
            flash('Sua senha foi atualizada.', 'success')
        else:
            flash('As senhas não conferem.', 'danger')

    if 'foto' in request.files:
        file = request.files['foto']
        if file and file.filename != '' and allowed_file(file.filename):
            if current_user.pilot_profile.foto_url:
                old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_user.pilot_profile.foto_url)
                if os.path.exists(old_path): os.remove(old_path)
                
            ext = file.filename.rsplit('.', 1)[1].lower()
            timestamp = int(datetime.utcnow().timestamp())
            nome = f"piloto_{current_user.pilot_profile.id}_{timestamp}.{ext}"
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], nome))
            current_user.pilot_profile.foto_url = nome
            
    # --- FOTOS ESPECÍFICAS POR GRID ---
    grid_photo_target = request.form.get('grid_photo_target')
    if grid_photo_target and 'grid_photo_file' in request.files:
        # Validação: Piloto deve pertencer ao grid para adicionar foto
        p_grids = [g.strip() for g in current_user.pilot_profile.grid.split(',')]
        if grid_photo_target in p_grids:
            g_file = request.files['grid_photo_file']
            if g_file and g_file.filename != '' and allowed_file(g_file.filename):
                # Remove foto anterior desse grid se existir
                old_gp = PilotGridPhoto.query.filter_by(pilot_id=current_user.pilot_profile.id, grid=grid_photo_target).first()
                if old_gp:
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], old_gp.foto_url)
                    if os.path.exists(old_path): os.remove(old_path)
                    db.session.delete(old_gp)
                
                ext = g_file.filename.rsplit('.', 1)[1].lower()
                timestamp = int(datetime.utcnow().timestamp())
                nome_gp = f"piloto_{current_user.pilot_profile.id}_{grid_photo_target}_{timestamp}.{ext}"
                g_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], nome_gp))
                
                new_gp = PilotGridPhoto(pilot_id=current_user.pilot_profile.id, grid=grid_photo_target, foto_url=nome_gp)
                db.session.add(new_gp)

    delete_gp_id = request.form.get('delete_grid_photo_id')
    if delete_gp_id:
        gp_to_del = PilotGridPhoto.query.get(delete_gp_id)
        if gp_to_del and gp_to_del.pilot_id == current_user.pilot_profile.id:
            path = os.path.join(current_app.config['UPLOAD_FOLDER'], gp_to_del.foto_url)
            if os.path.exists(path): os.remove(path)
            db.session.delete(gp_to_del)

    db.session.commit()
    return redirect(url_for('public.my_profile'))

@public_bp.route('/protestar', methods=['GET', 'POST'])
@login_required
def open_protest():
    if not current_user.pilot_profile: return redirect(url_for('public.home'))
    if request.method == 'POST':
        novo = Protesto(
            etapa_id=request.form.get('race_id'),
            acusador_id=current_user.pilot_profile.id,
            acusado_id=request.form.get('acusado_id'),
            video_link=request.form.get('video'),
            minuto=request.form.get('minuto'),
            descricao=request.form.get('descricao'),
            status='AGUARDANDO_DEFESA',
            data_criacao=datetime.utcnow()
        )
        db.session.add(novo)
        db.session.commit()
        return redirect(url_for('public.my_profile'))
    
    # LÓGICA REVISADA: Filtragem robusta por contexto do piloto
    active_seasons_ids = [s.id for s in Season.query.filter_by(ativa=True).all()]
    user_profile = current_user.pilot_profile
    
    # 1. Determina os grids do usuário (Texto do Perfil + Equipes Titulares/Reservas)
    user_grids = set([g.strip() for g in user_profile.grid.split(',') if g.strip()])
    for t in user_profile.teams:
        user_grids.add(t.grid)
    for t in user_profile.reserve_teams:
        user_grids.add(t.grid)
        
    # Remove 'SEM_GRID' se houver outros grids reais
    if 'SEM_GRID' in user_grids and len(user_grids) > 1:
        user_grids.remove('SEM_GRID')

    # 2. Verifica se é um piloto "Global" (Reserva Geral ou Admin sem grid específico)
    # Se tiver apenas 'RESERVA' ou 'SEM_GRID', vê tudo.
    is_global = False
    if not user_grids or user_grids.issubset({'RESERVA', 'SEM_GRID'}):
        is_global = True

    if is_global:
        races = Race.query.filter(Race.season_id.in_(active_seasons_ids)).order_by(Race.data_corrida.desc()).all()
        pilots = PilotProfile.query.filter(PilotProfile.id != user_profile.id).order_by(PilotProfile.nickname).all()
    else:
        # Filtra corridas: Apenas dos grids que o piloto participa
        races = Race.query.filter(
            Race.season_id.in_(active_seasons_ids), 
            Race.grid.in_(user_grids)
        ).order_by(Race.data_corrida.desc()).all()
        
        # Filtra pilotos: Apenas aqueles que compartilham algum grid com o usuário
        all_pilots = PilotProfile.query.filter(PilotProfile.id != user_profile.id).all()
        pilots = []
        for p in all_pilots:
            # Grids do piloto alvo (Perfil + Equipes)
            p_grids = set([g.strip() for g in p.grid.split(',') if g.strip()])
            for t in p.teams: p_grids.add(t.grid)
            
            # Se houver interseção (grids em comum), adiciona na lista
            if not user_grids.isdisjoint(p_grids):
                pilots.append(p)
        
        pilots.sort(key=lambda x: x.nickname)

    return render_template('pilot/protest.html', races=races, pilots=pilots)