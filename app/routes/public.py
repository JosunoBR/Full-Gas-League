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
    
    # Fallback: Se não houver temporadas ativas, busca todas
    if not all_active_seasons:
        all_active_seasons = Season.query.order_by(Season.id.desc()).all()
    
    selected_season_id = request.args.get('s', type=int)
    season_ativa = None
    if selected_season_id:
        season_ativa = next((s for s in all_active_seasons if s.id == selected_season_id), None)
    
    if not season_ativa and all_active_seasons:
        season_ativa = all_active_seasons[0]
    
    # LÓGICA 100% ID: Busca as configurações de grid da temporada selecionada
    grid_configs = []
    if season_ativa:
        grid_configs = GridConfig.query.filter_by(season_id=season_ativa.id).order_by(GridConfig.ordem).all()

    # Dicionários indexados por grid_id
    standings = { g.id: [] for g in grid_configs }
    constructors = { g.id: [] for g in grid_configs }
    calendar = { g.id: [] for g in grid_configs }
    last_races = { g.id: None for g in grid_configs }
    pilots_by_grid = { g.id: [] for g in grid_configs }
    noticias = News.query.order_by(News.data_publicacao.desc()).limit(5).all()
    
    if season_ativa:
        pilotos = PilotProfile.query.join(User).all()
        all_season_teams = Team.query.filter_by(season_id=season_ativa.id).all()
        
        # Pré-carrega todas as punições concluídas da temporada para performance
        punicoes_temporada = Protesto.query.join(Race).filter(
            Race.season_id == season_ativa.id,
            Protesto.status == 'CONCLUIDO'
        ).all()
        
        def calcular_perda(veredito):
            if veredito == 'LEVE': return 3
            if veredito == 'MEDIA': return 5
            if veredito == 'GRAVE': return 10
            return 0

        for p in pilotos:
            resultados = [r for r in p.race_results if r.race.season_id == season_ativa.id]
            grids_ids_participacao = set()

            # 1. Identifica Grids via Equipe Titular (ID com Fallback)
            teams_season = [t for t in all_season_teams if any(pilot.id == p.id for pilot in t.pilots)]
            for t in teams_season:
                if t.grid_id: grids_ids_participacao.add(t.grid_id)
                else:
                    # Fallback: Busca o ID da config pelo nome do grid da equipe
                    cfg = next((c for c in grid_configs if c.nome.upper() == t.grid.upper()), None)
                    if cfg: grids_ids_participacao.add(cfg.id)
            
            # 2. Identifica Grids via Equipe Reserva (ID com Fallback)
            reserves_season = [t for t in all_season_teams if any(pilot.id == p.id for pilot in t.reserves)]
            for t in reserves_season:
                if t.grid_id: grids_ids_participacao.add(t.grid_id)
                else:
                    cfg = next((c for c in grid_configs if c.nome.upper() == t.grid.upper()), None)
                    if cfg: grids_ids_participacao.add(cfg.id)
            
            # 3. Identifica Grids via Perfil (Caso o piloto ainda não tenha equipe na temporada)
            p_grid_entries = [x.strip().upper() for x in p.grid.split(',')]
            for g_cfg in grid_configs:
                if str(g_cfg.id) in p_grid_entries or g_cfg.nome.upper() in p_grid_entries:
                    grids_ids_participacao.add(g_cfg.id)

            for g_id in grids_ids_participacao:
                if g_id in standings:
                    # Filtra resultados comparando ID ou Nome (Fallback)
                    g_cfg_atual = next(c for c in grid_configs if c.id == g_id)
                    res_no_grid = [r for r in resultados if r.race.grid_id == g_id or 
                                   (not r.race.grid_id and r.race.grid.upper() == g_cfg_atual.nome.upper())]

                    # Soma pontos das corridas
                    pontos_corridas = float(sum(r.pontos_ganhos for r in res_no_grid))
                    # Soma punições do tribunal para este grid específico
                    total_punicoes_tribunal = sum(calcular_perda(pr.veredito_final) for pr in punicoes_temporada if pr.acusado_id == p.id and pr.grid_id == g_id)
                    
                    pontos_totais = pontos_corridas - total_punicoes_tribunal - float(p.penalidade_campeonato or 0)
                    vitorias = sum(1 for r in res_no_grid if r.posicao == 1 and not r.dsq)

                    # Verificação de Quali Ban
                    ultimo_p = Protesto.query.filter_by(acusado_id=p.id, status='CONCLUIDO')\
                        .order_by(Protesto.data_fechamento.desc()).first()
                    quali_ban = False
                    if ultimo_p and ultimo_p.veredito_final in ['MEDIA', 'GRAVE']:
                        ultima_res = RaceResult.query.join(Race).filter(RaceResult.pilot_id == p.id, Race.status == 'Concluida').order_by(Race.data_corrida.desc()).first()
                        if not ultima_res or ultimo_p.data_fechamento.date() >= ultima_res.race.data_corrida:
                            quali_ban = True

                    # Foto por Grid (Filtro pelo nome do contexto atual)
                    g_cfg = next(c for c in grid_configs if c.id == g_id)
                    foto_final = p.foto_url
                    for gp in p.grid_photos:
                        if gp.grid.upper() == g_cfg.nome.upper():
                            foto_final = gp.foto_url
                            break

                    # Equipe (ID ou Nome)
                    team = next((t for t in teams_season if t.grid_id == g_id or 
                                 (not t.grid_id and t.grid.upper() == g_cfg.nome.upper())), None)
                    is_reserve = False

                    if not team:
                        reserve_team = next((t for t in all_season_teams if any(pilot.id == p.id for pilot in t.reserves) and (t.grid_id == g_id or (not t.grid_id and t.grid.upper() == g_cfg.nome.upper()))), None)
                        if reserve_team:
                            team = reserve_team
                            is_reserve = True

                    team_name = team.nome if team else 'Sem Equipe'
                    standings[g_id].append({'piloto': p, 'pontos': pontos_totais, 'vitorias': vitorias, 'carro': '', 'quali_ban': quali_ban, 'foto_url': foto_final, 'team_name': team_name, 'is_reserve': is_reserve})

        # 3. Ordenação e Lastro (ID)
        for g in grid_configs:
            standings[g.id].sort(key=lambda x: (x['pontos'], x['vitorias']), reverse=True)
            # Limita a exibição ao número de vagas configurado para o grid (ex: 20 ou 22)
            standings[g.id] = standings[g.id][:g.vagas]
            for i, item in enumerate(standings[g.id]):
                if g.exibir_lastro:
                    item['carro'] = ORDEM_CARROS[i] if i < len(ORDEM_CARROS) else "McLaren (Extra)"
                else:
                    item['carro'] = "-"

        # 4. Classificação de Construtores
        stats_query = db.session.query(
            RaceResult.team_id,
            func.sum(RaceResult.pontos_ganhos).label('total_pontos'),
            func.sum(case(( (RaceResult.posicao == 1) & (RaceResult.dsq == False), 1 ), else_=0)).label('total_vitorias')
        ).join(Race).filter(
            Race.season_id == season_ativa.id,
            RaceResult.team_id != None
        ).group_by(RaceResult.team_id).all()

        team_stats = { s.team_id: {'pontos': float(s.total_pontos or 0), 'vitorias': int(s.total_vitorias or 0)} for s in stats_query }

        legacy_results_query = db.session.query(
            RaceResult.pilot_id,
            func.sum(RaceResult.pontos_ganhos).label('total_pontos'),
            func.sum(case(( (RaceResult.posicao == 1) & (RaceResult.dsq == False), 1 ), else_=0)).label('total_vitorias')
        ).join(Race).filter(
            Race.season_id == season_ativa.id,
            RaceResult.team_id.is_(None)
        ).group_by(RaceResult.pilot_id).all()

        legacy_stats_by_pilot = { s.pilot_id: {'pontos': float(s.total_pontos or 0), 'vitorias': int(s.total_vitorias or 0)} for s in legacy_results_query }

        for t in all_season_teams:
            # Identifica o ID do grid da equipe para a tabela de construtores
            t_grid_id = t.grid_id
            if not t_grid_id:
                cfg = next((c for c in grid_configs if c.nome.upper() == t.grid.upper()), None)
                t_grid_id = cfg.id if cfg else None

            if t_grid_id and t_grid_id in constructors:
                stats = team_stats.get(t.id, {'pontos': 0.0, 'vitorias': 0})
                for p in t.pilots:
                    if p.id in legacy_stats_by_pilot:
                        l_stats = legacy_stats_by_pilot[p.id]
                        stats['pontos'] += l_stats['pontos']
                        stats['vitorias'] += l_stats['vitorias']

                # Penalidades administrativas dos pilotos da equipe
                pen_adm = sum(float(p.penalidade_campeonato or 0) for p in t.pilots)
                # Penalidades de tribunal dos pilotos da equipe neste grid
                pen_tribunal = sum(sum(calcular_perda(pr.veredito_final) for pr in punicoes_temporada if pr.acusado_id == p.id and pr.grid_id == t.grid_id) for p in t.pilots)
                
                pontos_finais = stats['pontos'] - pen_adm - pen_tribunal
                constructors[t_grid_id].append({'equipe': t, 'pontos': pontos_finais, 'vitorias': stats['vitorias']})

        for g_id in constructors: constructors[g_id].sort(key=lambda x: (x['pontos'], x['vitorias']), reverse=True)

        # 5. Calendário e Últimas Corridas
        all_races = Race.query.filter_by(season_id=season_ativa.id).order_by(Race.data_corrida).all()
        for r in all_races:
            r_grid_id = r.grid_id
            if not r_grid_id:
                cfg = next((c for c in grid_configs if c.nome.upper() == r.grid.upper()), None)
                r_grid_id = cfg.id if cfg else None
            
            if r_grid_id and r_grid_id in calendar:
                calendar[r_grid_id].append(r)

        for g_id in last_races:
            concluidas = [r for r in calendar[g_id] if r.status == 'Concluida']
            if concluidas: last_races[g_id] = concluidas[-1]

        # 6. Pilotos por Grid (Carrossel)
        all_pilots_query = PilotProfile.query.join(User).order_by(PilotProfile.nickname).all()
        for g in grid_configs:
            for p in all_pilots_query:
                # Verifica se o piloto pertence a este grid ID ou Nome no perfil, ou se tem equipe
                p_grid_entries = [x.strip().upper() for x in p.grid.split(',')]
                team = next((t for t in all_season_teams if any(pilot.id == p.id for pilot in t.pilots) and (t.grid_id == g.id or (not t.grid_id and t.grid.upper() == g.nome.upper()))), None)

                if str(g.id) in p_grid_entries or g.nome.upper() in p_grid_entries or team:
                    foto_final = p.foto_url
                    for gp in p.grid_photos:
                        if gp.grid.upper() == g.nome.upper():
                            foto_final = gp.foto_url
                            break

                    reserve_team = next((t for t in all_season_teams if any(pilot.id == p.id for pilot in t.reserves) and (t.grid_id == g.id or (not t.grid_id and t.grid.upper() == g.nome.upper()))), None)

                    if (team or not reserve_team) and not any(item['data'].id == p.id for item in pilots_by_grid[g.id]):
                        pilots_by_grid[g.id].append({'data': p, 'foto_url': foto_final, 'team': team})

    return render_template('home.html', standings=standings, constructors=constructors, calendar=calendar, last_races=last_races, season_ativa=season_ativa, noticias=noticias, pilots_by_grid=pilots_by_grid, grid_configs=grid_configs, all_seasons=all_active_seasons)

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
    
    if current_user.is_authenticated and current_user.pilot_profile and current_user.pilot_profile.id == perfil.id:
        return redirect(url_for('public.my_profile'))

    active_seasons = Season.query.filter_by(ativa=True).order_by(Season.id.desc()).all()
    available_contexts = []
    p_grids = [g.strip() for g in perfil.grid.split(',')] if perfil.grid else []

    for s in active_seasons:
        # Busca grids onde o piloto tem resultados (Via ID)
        races_res = db.session.query(Race).join(RaceResult).filter(
            RaceResult.pilot_id == perfil.id,
            Race.season_id == s.id
        ).distinct().all()
        grids = []
        for r in races_res:
            gname = r.grid_config.nome if r.grid_config else r.grid
            if gname not in grids: grids.append(gname)
        
        # Filtra grids válidos para esta temporada via GridConfig
        configs = GridConfig.query.filter_by(season_id=s.id).all()
        if configs:
            valid_season_grids = set(c.nome for c in configs)
        else:
            # Fallback para corridas se não houver config
            season_races = Race.query.filter_by(season_id=s.id).all()
            valid_season_grids = set(r.grid_config.nome if r.grid_config else r.grid for r in season_races if r.grid or r.grid_config)

        for pg in p_grids:
            if pg not in grids and pg in valid_season_grids:
                grids.append(pg)
        
        for g in grids:
            available_contexts.append({'season_id': s.id, 'season_nome': s.nome, 'grid': g})

    sel_season_id = request.args.get('s', type=int)
    sel_grid = request.args.get('g')
    
    current_context = None
    if sel_season_id and sel_grid:
        current_context = next((c for c in available_contexts if c['season_id'] == sel_season_id and c['grid'] == sel_grid), None)
    
    if not current_context and available_contexts:
        default_grid = p_grids[0] if p_grids else 'SEM_GRID'
        current_context = next((c for c in available_contexts if c['grid'] == default_grid), available_contexts[0])
    
    if current_context:
        for gp in perfil.grid_photos:
            if gp.grid == current_context['grid']:
                perfil.foto_url = gp.foto_url
    
    current_team = None
    if current_context:
        # Busca equipe usando ID se possível
        current_team = next((t for t in perfil.teams if t.season_id == current_context['season_id'] and 
                             ((t.grid_config and t.grid_config.nome == current_context['grid']) or t.grid == current_context['grid'])), None)
        
        if not current_team:
            current_team = next((t for t in perfil.reserve_teams if t.season_id == current_context['season_id'] and 
                                 ((t.grid_config and t.grid_config.nome == current_context['grid']) or t.grid == current_context['grid'])), None)
    
    if current_context:
        cnh_info = perfil.get_cnh_info(current_context['season_id'], current_context['grid'])
        perfil.pontos_cnh = cnh_info['cnh']
        perfil.advertencias_acumuladas = cnh_info['advertencias']

    meus_pontos_camp = 0
    desempenho_temporada = []
    if current_context:
        s_id = current_context['season_id']
        g_name = current_context['grid']
        
        # Filtra resultados usando ID ou Texto
        resultados_contexto = [r for r in perfil.race_results if r.race.season_id == s_id and 
                               ((r.race.grid_config and r.race.grid_config.nome == g_name) or r.race.grid == g_name)]
        
        meus_pontos_camp = float(sum(r.pontos_ganhos for r in resultados_contexto)) - float(perfil.penalidade_campeonato or 0)
        
        all_races_season = Race.query.filter_by(season_id=s_id).order_by(Race.data_corrida).all()
        corridas = [r for r in all_races_season if (r.grid_config and r.grid_config.nome == g_name) or r.grid == g_name]
        
        for race in corridas:
            resultado = next((r for r in race.results if r.pilot_id == perfil.id), None)
            desempenho_temporada.append({
                'gp': race.nome_gp, 'data': race.data_corrida, 'status_corrida': race.status,
                'participou': True if resultado and not resultado.ausencia else False,
                'posicao': resultado.posicao if resultado else 0,
                'pontos': resultado.pontos_ganhos if resultado else 0,
                'dnf': resultado.dnf if resultado else False, 'dsq': resultado.dsq if resultado else False
            })

    seasons_fechadas = Season.query.filter_by(ativa=False).order_by(Season.id.desc()).all()
    historico_carreira = []
    for s in seasons_fechadas:
        resultados_na_season = [r for r in perfil.race_results if r.race.season_id == s.id]
        if resultados_na_season:
            pts = sum(r.pontos_ganhos for r in resultados_na_season)
            vitorias = sum(1 for r in resultados_na_season if r.posicao == 1 and not r.dsq)
            grids_corridos = [(r.race.grid_config.nome if r.race.grid_config else r.race.grid) for r in resultados_na_season]
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

    active_seasons = Season.query.filter_by(ativa=True).order_by(Season.id.desc()).all()
    available_contexts = []
    p_grids = [g.strip() for g in perfil.grid.split(',')] if perfil.grid else []

    for s in active_seasons:
        # Busca grids onde o piloto tem resultados (Via ID)
        races_res = db.session.query(Race).join(RaceResult).filter(
            RaceResult.pilot_id == perfil.id,
            Race.season_id == s.id
        ).distinct().all()
        grids = []
        for r in races_res:
            gname = r.grid_config.nome if r.grid_config else r.grid
            if gname not in grids: grids.append(gname)
        
        # Filtra grids válidos para esta temporada via GridConfig
        configs = GridConfig.query.filter_by(season_id=s.id).all()
        if configs:
            valid_season_grids = set(c.nome for c in configs)
        else:
            # Fallback para corridas se não houver config
            season_races = Race.query.filter_by(season_id=s.id).all()
            valid_season_grids = set(r.grid_config.nome if r.grid_config else r.grid for r in season_races if r.grid or r.grid_config)

        for pg in p_grids:
            if pg not in grids and pg in valid_season_grids:
                grids.append(pg)
        
        for g in grids:
            available_contexts.append({'season_id': s.id, 'season_nome': s.nome, 'grid': g})

    sel_season_id = request.args.get('s', type=int)
    sel_grid = request.args.get('g')
    
    current_context = None
    if sel_season_id and sel_grid:
        current_context = next((c for c in available_contexts if c['season_id'] == sel_season_id and c['grid'] == sel_grid), None)
    
    if not current_context and available_contexts:
        default_grid = p_grids[0] if p_grids else 'SEM_GRID'
        current_context = next((c for c in available_contexts if c['grid'] == default_grid), available_contexts[0])
    
    if current_context:
        for gp in perfil.grid_photos:
            if gp.grid == current_context['grid']:
                perfil.foto_url = gp.foto_url
    
    current_team = None
    if current_context:
        current_team = next((t for t in perfil.teams if t.season_id == current_context['season_id'] and 
                             ((t.grid_config and t.grid_config.nome == current_context['grid']) or t.grid == current_context['grid'])), None)
        
        if not current_team:
            current_team = next((t for t in perfil.reserve_teams if t.season_id == current_context['season_id'] and 
                                 ((t.grid_config and t.grid_config.nome == current_context['grid']) or t.grid == current_context['grid'])), None)

    if current_context:
        cnh_info = perfil.get_cnh_info(current_context['season_id'], current_context['grid'])
        perfil.pontos_cnh = cnh_info['cnh']
        perfil.advertencias_acumuladas = cnh_info['advertencias']

    if perfil.esta_banido():
        flash('ALERTA: Sua CNH está zerada ou negativa. Você está suspenso das atividades de pista.', 'danger')
    
    checkin_race = None
    registro_atual = None
    
    hoje = datetime.utcnow().date()
    if current_context:
        pode_ver_checkin = (current_context['grid'] in p_grids) or ('RESERVA' in p_grids) or \
                           (current_team is not None)

        if pode_ver_checkin:
            proxima = None
            futuras = Race.query.filter(
                Race.season_id == current_context['season_id'],
                Race.status != 'Concluida',
                Race.data_corrida >= hoje
            ).order_by(Race.data_corrida).all()
            
            for r in futuras:
                r_gname = r.grid_config.nome if r.grid_config else r.grid
                if r_gname == current_context['grid']:
                    proxima = r
                    break

            if proxima and proxima.data_corrida and (proxima.data_corrida - hoje).days <= 2:
                reg = RaceRegistration.query.filter_by(race_id=proxima.id, pilot_id=perfil.id).first()
                if not reg or reg.status not in ['CONFIRMADO', 'JUSTIFICADO']:
                    checkin_race = proxima
                    registro_atual = reg

    meus_pontos_camp = 0
    desempenho_temporada = []
    if current_context:
        s_id = current_context['season_id']
        g_name = current_context['grid']
        
        resultados_contexto = [r for r in perfil.race_results if r.race.season_id == s_id and 
                               ((r.race.grid_config and r.race.grid_config.nome == g_name) or r.race.grid == g_name)]
        
        meus_pontos_camp = float(sum(r.pontos_ganhos for r in resultados_contexto)) - float(perfil.penalidade_campeonato or 0)
        
        all_races_season = Race.query.filter_by(season_id=s_id).order_by(Race.data_corrida).all()
        corridas = [r for r in all_races_season if (r.grid_config and r.grid_config.nome == g_name) or r.grid == g_name]
        
        for race in corridas:
            resultado = next((r for r in race.results if r.pilot_id == perfil.id), None)
            desempenho_temporada.append({
                'gp': race.nome_gp, 'data': race.data_corrida, 'status_corrida': race.status,
                'participou': True if resultado and not resultado.ausencia else False,
                'posicao': resultado.posicao if resultado else 0,
                'pontos': resultado.pontos_ganhos if resultado else 0,
                'dnf': resultado.dnf if resultado else False, 'dsq': resultado.dsq if resultado else False
            })

    meus_protestos = Protesto.query.filter_by(acusador_id=perfil.id).order_by(Protesto.data_criacao.desc()).all()
    
    defesas_pendentes = Protesto.query.filter(
        Protesto.acusado_id == perfil.id,
        Protesto.status.in_(['AGUARDANDO_DEFESA', 'EM_VOTACAO']),
        Protesto.argumento_defesa == None
    ).all()
    
    historico_punicoes = Protesto.query.filter(Protesto.acusado_id == perfil.id, Protesto.status != 'AGUARDANDO_DEFESA').order_by(Protesto.data_fechamento.desc()).all()
    
    total_punicoes = 0
    for h in historico_punicoes:
        if h.veredito_final == 'LEVE': total_punicoes += 3
        elif h.veredito_final == 'MEDIA': total_punicoes += 5
        elif h.veredito_final == 'GRAVE': total_punicoes += 10

    seasons_fechadas = Season.query.filter_by(ativa=False).order_by(Season.id.desc()).all()
    historico_carreira = []
    for s in seasons_fechadas:
        resultados_na_season = [r for r in perfil.race_results if r.race.season_id == s.id]
        if resultados_na_season:
            pts = sum(r.pontos_ganhos for r in resultados_na_season)
            vitorias = sum(1 for r in resultados_na_season if r.posicao == 1 and not r.dsq)
            grids_corridos = [(r.race.grid_config.nome if r.race.grid_config else r.race.grid) for r in resultados_na_season]
            grid_predominante = max(set(grids_corridos), key=grids_corridos.count) if grids_corridos else "N/A"
            historico_carreira.append({'season_nome': s.nome, 'grid': grid_predominante, 'pontos': pts, 'vitorias': vitorias})

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
    
    all_seasons = Season.query.order_by(Season.id.desc()).all()
    selected_season_id = request.args.get('s', type=int)
    
    season_ativa = next((s for s in all_seasons if s.id == selected_season_id), None)
    
    if not season_ativa:
        if team.season_id:
            season_ativa = Season.query.get(team.season_id)
        
        active_seasons = [s for s in all_seasons if s.ativa]
        
        if active_seasons:
            for s in active_seasons:
                has_results = RaceResult.query.join(Race).filter(
                    Race.season_id == s.id,
                    RaceResult.team_id == team.id
                ).first()
                if has_results:
                    season_ativa = s
                    break
            
            if not season_ativa and team.pilots:
                titular_ids = [p.id for p in team.pilots]
                for s in active_seasons:
                    has_pilot_results = RaceResult.query.join(Race).filter(
                        Race.season_id == s.id,
                        RaceResult.pilot_id.in_(titular_ids)
                    ).first()
                    if has_pilot_results:
                        season_ativa = s
                        break
            
            if not season_ativa:
                season_ativa = active_seasons[0]
        else:
            season_ativa = all_seasons[0] if all_seasons else None

    total_pontos = 0
    total_vitorias = 0
    stats_pilotos = []
    if season_ativa:
        titulares_ids = []
        for piloto in team.pilots:
            titulares_ids.append(piloto.id)
            results_pilot = [r for r in piloto.race_results if r.race.season_id == season_ativa.id]
            
            pts_piloto = 0
            wins_piloto = 0
            
            for r in results_pilot:
                # Normaliza nomes dos grids para comparação segura
                r_grid = (r.race.grid_config.nome if r.race.grid_config else r.race.grid).strip().upper()
                t_grid = (team.grid_config.nome if team.grid_config else team.grid).strip().upper()

                # Se o piloto é titular desta equipe e o grid da corrida bate com o grid da equipe,
                # os pontos devem contar, mesmo que o team_id no banco esteja desatualizado.
                if r_grid == t_grid:
                    pts_piloto += r.pontos_ganhos
                    if r.posicao == 1 and not r.dsq:
                        wins_piloto += 1
            
            pts_liquidos = pts_piloto - float(piloto.penalidade_campeonato or 0)
            
            stats_pilotos.append({
                'piloto': piloto,
                'pontos': pts_liquidos,
                'vitorias': wins_piloto
            })
            
            total_pontos += pts_liquidos
            total_vitorias += wins_piloto

        extra_results_query = RaceResult.query.join(Race).filter(
            RaceResult.team_id == team.id,
            Race.season_id == season_ativa.id
        ).all()
        
        t_grid = (team.grid_config.nome if team.grid_config else team.grid).strip().upper()
        extra_results = []
        for r in extra_results_query:
            r_grid = (r.race.grid_config.nome if r.race.grid_config else r.race.grid).strip().upper()
            if r_grid == t_grid:
                extra_results.append(r)
        
        extras_map = {}
        for r in extra_results:
            if r.pilot_id not in titulares_ids:
                if r.pilot_id not in extras_map:
                    extras_map[r.pilot_id] = {'pontos': 0, 'vitorias': 0}
                
                extras_map[r.pilot_id]['pontos'] += r.pontos_ganhos
                if r.posicao == 1 and not r.dsq:
                    extras_map[r.pilot_id]['vitorias'] += 1
                    
                total_pontos += r.pontos_ganhos
                if r.posicao == 1 and not r.dsq:
                    total_vitorias += 1
        
        for pid, stats in extras_map.items():
            p = PilotProfile.query.get(pid)
            if p:
                stats_pilotos.append({
                    'piloto': p,
                    'pontos': stats['pontos'],
                    'vitorias': stats['vitorias']
                })

        stats_pilotos.sort(key=lambda x: x['pontos'], reverse=True)
            
    return render_template('public/team_profile.html', team=team, total_pontos=total_pontos, total_vitorias=total_vitorias, stats_pilotos=stats_pilotos, season_ativa=season_ativa, all_active_seasons=all_seasons)

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
            
    grid_photo_target = request.form.get('grid_photo_target')
    if grid_photo_target and 'grid_photo_file' in request.files:
        p_grids = [g.strip() for g in current_user.pilot_profile.grid.split(',')]
        if grid_photo_target in p_grids:
            g_file = request.files['grid_photo_file']
            if g_file and g_file.filename != '' and allowed_file(g_file.filename):
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
    
    active_seasons_ids = [s.id for s in Season.query.filter_by(ativa=True).all()]
    user_profile = current_user.pilot_profile
    
    # 1. Determina os grids do usuário (IDs e Nomes para compatibilidade)
    user_grid_ids = set()
    user_grid_names = set()
    
    for g in user_profile.grid.split(','):
        g = g.strip()
        if g.isdigit(): user_grid_ids.add(int(g))
        else: user_grid_names.add(g.upper())

    for t in user_profile.teams:
        if t.grid_id: user_grid_ids.add(t.grid_id)
        if t.grid: user_grid_names.add(t.grid.upper())
    for t in user_profile.reserve_teams:
        if t.grid_id: user_grid_ids.add(t.grid_id)
        if t.grid: user_grid_names.add(t.grid.upper())

    if 'SEM_GRID' in user_grid_names and (len(user_grid_names) > 1 or user_grid_ids):
        user_grid_names.remove('SEM_GRID')

    is_global = not user_grid_ids and (not user_grid_names or user_grid_names.issubset({'RESERVA', 'SEM_GRID'}))

    if is_global:
        races = Race.query.filter(Race.season_id.in_(active_seasons_ids)).order_by(Race.data_corrida.desc()).all()
        pilots = PilotProfile.query.filter(PilotProfile.id != user_profile.id).order_by(PilotProfile.nickname).all()
    else:
        all_races = Race.query.filter(Race.season_id.in_(active_seasons_ids)).order_by(Race.data_corrida.desc()).all()
        races = []
        for r in all_races:
            if r.grid_id in user_grid_ids or (r.grid and r.grid.upper() in user_grid_names):
                races.append(r)
        
        all_pilots = PilotProfile.query.filter(PilotProfile.id != user_profile.id).all()
        pilots = []
        for p in all_pilots:
            p_grid_ids = set()
            p_grid_names = set()
            for g in p.grid.split(','):
                g = g.strip()
                if g.isdigit(): p_grid_ids.add(int(g))
                else: p_grid_names.add(g.upper())
            
            for t in p.teams:
                if t.grid_id: p_grid_ids.add(t.grid_id)
                if t.grid: p_grid_names.add(t.grid.upper())

            # Se houver interseção de IDs ou Nomes, permite o protesto
            if not user_grid_ids.isdisjoint(p_grid_ids) or not user_grid_names.isdisjoint(p_grid_names):
                pilots.append(p)
        
        pilots.sort(key=lambda x: x.nickname)

    return render_template('pilot/protest.html', races=races, pilots=pilots)
