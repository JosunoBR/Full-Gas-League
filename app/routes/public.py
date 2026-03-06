import os
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import check_password_hash
from sqlalchemy.orm import joinedload
from app.models import db, Season, Race, PilotProfile, Protesto, RaceResult, VotoComissario, Team, RaceRegistration, User, Invite, News, GridConfig, SeasonChampion, PilotGridPhoto
from app.utils import allowed_file, get_embed_url, ORDEM_CARROS, get_grid_name, find_grid_config, gerar_evolucao_pontos, grid_matches, calcular_pontos_totais_piloto
from app.services.team_context import build_team_context
from app.services.scoring import build_constructors_for_home, team_has_results_in_season, get_team_profile_stats

public_bp = Blueprint('public', __name__)

# --- FUNÇÕES AUXILIARES ---

def converter_standings_para_json(standings):
    """Converte standings com objetos SQLAlchemy para dicionários serializáveis"""
    resultado = {}
    for grid_id, pilotos_list in standings.items():
        resultado[grid_id] = []
        for item in pilotos_list:
            piloto = item['piloto']
            resultado[grid_id].append({
                'piloto': {
                    'id': piloto.id,
                    'nome_real': piloto.nome_real,
                    'nickname': piloto.nickname
                },
                'pontos': item['pontos'],
                'vitorias': item['vitorias'],
                'carro': item['carro'],
                'quali_ban': item['quali_ban'],
                'foto_url': item['foto_url'],
                'team_name': item['team_name'],
                'is_reserve': item['is_reserve'],
                'evolucao': item.get('evolucao', [])
            })
    return resultado

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
        pilotos = PilotProfile.query.options(
            joinedload(PilotProfile.user),
            joinedload(PilotProfile.race_results).joinedload(RaceResult.race),
            joinedload(PilotProfile.teams),
            joinedload(PilotProfile.grid_photos)
        ).all()

        team_ctx = build_team_context(season_ativa.id)
        participants_by_grid = team_ctx["participants_by_grid"]
        constructors = build_constructors_for_home(
            season_ativa.id,
            grid_configs,
            team_ctx["canonical_teams"],
            team_ctx["alias_ids_by_key"]
        )

        # Preload severe protests and last participations to reduce per-row queries.
        severe_protests = Protesto.query.join(Race).filter(
            Race.season_id == season_ativa.id,
            Protesto.status == "CONCLUIDO",
            Protesto.veredito_final.in_(["MEDIA", "GRAVE"])
        ).all()
        latest_severe = {}
        for pr in severe_protests:
            if not pr.grid_id:
                continue
            key = (pr.acusado_id, pr.grid_id)
            prev = latest_severe.get(key)
            if not prev or (pr.data_fechamento and prev.data_fechamento and pr.data_fechamento > prev.data_fechamento):
                latest_severe[key] = pr

        last_participation_rows = RaceResult.query.join(Race).with_entities(
            RaceResult.pilot_id, Race.grid_id, Race.data_corrida
        ).filter(
            Race.season_id == season_ativa.id,
            Race.status == "Concluida",
            RaceResult.ausencia.is_(None)
        ).all()
        last_participation = {}
        for pilot_id, grid_id, data_corrida in last_participation_rows:
            if not grid_id:
                continue
            key = (pilot_id, grid_id)
            prev_date = last_participation.get(key)
            if not prev_date or (data_corrida and data_corrida > prev_date):
                last_participation[key] = data_corrida

        points_cache = {}
        evolution_cache = {}

        for g in grid_configs:
            for item in participants_by_grid.get(g.id, []):
                p = item["pilot"]
                team_ref = item["team"]
                is_reserve = item["is_reserve"]

                resultados = [r for r in p.race_results if r.race.season_id == season_ativa.id]
                res_no_grid = [r for r in resultados if grid_matches(r.race, g)]

                key_pg = (p.id, g.id)
                if key_pg not in points_cache:
                    points_cache[key_pg] = calcular_pontos_totais_piloto(p.id, season_ativa.id, g.id)
                pontos_totais = points_cache[key_pg]
                vitorias = sum(1 for r in res_no_grid if r.posicao == 1 and not r.dsq)

                ultimo_p = latest_severe.get(key_pg)
                ultima_data = last_participation.get(key_pg)
                quali_ban = bool(ultimo_p and (not ultima_data or ultimo_p.data_fechamento.date() >= ultima_data))

                foto_final = p.foto_url
                grid_photo = next((gp for gp in p.grid_photos if getattr(gp, "grid_id", None) == g.id), None)
                if grid_photo:
                    foto_final = grid_photo.foto_url

                if key_pg not in evolution_cache:
                    evolution_cache[key_pg] = gerar_evolucao_pontos(p.id, g.id, season_ativa.id)

                standings[g.id].append({
                    "piloto": p,
                    "pontos": pontos_totais,
                    "vitorias": vitorias,
                    "carro": "",
                    "quali_ban": quali_ban,
                    "foto_url": foto_final,
                    "team_name": team_ref.nome if team_ref else "Sem Equipe",
                    "is_reserve": is_reserve,
                    "evolucao": evolution_cache[key_pg],
                })

                if not any(x["data"].id == p.id for x in pilots_by_grid[g.id]):
                    pilots_by_grid[g.id].append({"data": p, "foto_url": foto_final, "team": team_ref})

        # Lastro assignment.
        for g in grid_configs:
            standings[g.id].sort(key=lambda x: (x["pontos"], x["vitorias"]), reverse=True)
            for i, item in enumerate(standings[g.id]):
                item["carro"] = ORDEM_CARROS[i] if (g.exibir_lastro and i < len(ORDEM_CARROS)) else ("-" if not g.exibir_lastro else "McLaren (Extra)")

        # 5. Calendário e Últimas Corridas
        all_races = Race.query.filter_by(season_id=season_ativa.id).order_by(Race.data_corrida).all()
        for r in all_races:
            r_grid_id = r.grid_id
            
            if r_grid_id and r_grid_id in calendar:
                calendar[r_grid_id].append(r)

        for g_id in last_races:
            concluidas = [r for r in calendar[g_id] if r.status == 'Concluida']
            if concluidas: last_races[g_id] = concluidas[-1]

        # 6. Pilotos por Grid (Carrossel) already populated with same source as standings.

    # Converte dados para formato JSON-seguro
    grid_configs_json = [{'id': g.id, 'nome': g.nome, 'vagas': g.vagas, 'exibir_lastro': g.exibir_lastro} for g in grid_configs]
    standings_json = converter_standings_para_json(standings)

    return render_template('home.html', standings=standings_json, constructors=constructors, calendar=calendar, last_races=last_races, season_ativa=season_ativa, noticias=noticias, pilots_by_grid=pilots_by_grid, grid_configs=grid_configs_json, all_seasons=all_active_seasons)

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
        configs = GridConfig.query.filter_by(season_id=s.id).all()
        cfg_by_id = {c.id: c for c in configs}
        valid_names = {c.nome for c in configs}
        contexts_seen = set()

        # 1) Grids por vínculo de equipe (titular/reserva) - fonte principal.
        team_links = [t for t in perfil.teams if t.season_id == s.id] + [t for t in perfil.reserve_teams if t.season_id == s.id]
        for t in team_links:
            g_id = t.grid_id
            g_name = t.grid_config.nome if t.grid_config else t.grid
            if g_id in cfg_by_id:
                g_name = cfg_by_id[g_id].nome
            if not g_name:
                continue
            key = (s.id, g_name)
            if key in contexts_seen:
                continue
            contexts_seen.add(key)
            available_contexts.append({
                'season_id': s.id,
                'season_nome': s.nome,
                'grid': g_name,
                'grid_id': g_id
            })

        # 2) Grids por resultados (fallback/histórico).
        races_res = db.session.query(Race).join(RaceResult).filter(
            RaceResult.pilot_id == perfil.id,
            Race.season_id == s.id
        ).distinct().all()
        for r in races_res:
            g_name = r.grid_config.nome if r.grid_config else r.grid
            key = (s.id, g_name)
            if not g_name or key in contexts_seen:
                continue
            contexts_seen.add(key)
            available_contexts.append({
                'season_id': s.id,
                'season_nome': s.nome,
                'grid': g_name,
                'grid_id': r.grid_id
            })

        # 3) Grids do perfil (aceita ID ou nome).
        for pg in p_grids:
            cfg = None
            g_name = None
            g_id = None

            if pg.isdigit():
                g_id = int(pg)
                cfg = cfg_by_id.get(g_id)
                if cfg:
                    g_name = cfg.nome
            else:
                if pg in valid_names:
                    g_name = pg
                    cfg = next((c for c in configs if c.nome == pg), None)
                    g_id = cfg.id if cfg else None

            if not g_name:
                continue
            key = (s.id, g_name)
            if key in contexts_seen:
                continue
            contexts_seen.add(key)
            available_contexts.append({
                'season_id': s.id,
                'season_nome': s.nome,
                'grid': g_name,
                'grid_id': g_id
            })

    sel_season_id = request.args.get('s', type=int)
    sel_grid = request.args.get('g')
    
    current_context = None
    if sel_season_id and sel_grid:
        current_context = next((c for c in available_contexts if c['season_id'] == sel_season_id and c['grid'] == sel_grid), None)
    
    if not current_context and available_contexts:
        default_grid = p_grids[0] if p_grids else 'SEM_GRID'
        current_context = next((c for c in available_contexts if c['grid'] == default_grid), available_contexts[0])
    
    quali_ban = False
    # Lógica de Foto por Grid (baseada em ID)
    if current_context:
        grid_id_contexto = current_context.get('grid_id')
        if grid_id_contexto:
            grid_photo = next((gp for gp in perfil.grid_photos if hasattr(gp, 'grid_id') and gp.grid_id == grid_id_contexto), None)
            if grid_photo:
                perfil.foto_url = grid_photo.foto_url
    
    current_team = None
    if current_context:
        # Busca equipe usando ID se possível
        current_team = next((t for t in perfil.teams if t.season_id == current_context['season_id'] and 
                             ((t.grid_config and t.grid_config.nome == current_context['grid']) or t.grid == current_context['grid'])), None)
        
        if not current_team:
            current_team = next((t for t in perfil.reserve_teams if t.season_id == current_context['season_id'] and 
                                 ((t.grid_config and t.grid_config.nome == current_context['grid']) or t.grid == current_context['grid'])), None)
    
    if current_context:
        cnh_info = perfil.get_cnh_info(current_context['season_id'], current_context['grid_id'])
        perfil.pontos_cnh = cnh_info['cnh']
        perfil.advertencias_acumuladas = cnh_info['advertencias']
        
        # Verificação de Quali Ban (100% via ID do Grid)
        grid_id_contexto = current_context.get('grid_id')
        ultimo_p = Protesto.query.filter_by(acusado_id=perfil.id, grid_id=grid_id_contexto, status='CONCLUIDO')\
            .filter(Protesto.veredito_final.in_(['MEDIA', 'GRAVE']))\
            .order_by(Protesto.data_fechamento.desc()).first()
            
        if ultimo_p:
            ultima_res = RaceResult.query.join(Race).filter(
                RaceResult.pilot_id == perfil.id, 
                Race.grid_id == grid_id_contexto,
                Race.status == 'Concluida',
                RaceResult.ausencia == None
            ).order_by(Race.data_corrida.desc()).first()
            if not ultima_res or ultimo_p.data_fechamento.date() >= ultima_res.race.data_corrida:
                quali_ban = True

    meus_pontos_camp = 0
    desempenho_temporada = []
    if current_context:
        s_id = current_context['season_id']
        g_name = current_context['grid']
        grid_id_calc = current_context.get('grid_id')
        
        # Usa a função centralizada para calcular pontos totais
        if grid_id_calc:
            meus_pontos_camp = calcular_pontos_totais_piloto(perfil.id, s_id, grid_id_calc)
        
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
        configs = GridConfig.query.filter_by(season_id=s.id).all()
        cfg_by_id = {c.id: c for c in configs}
        valid_names = {c.nome for c in configs}
        contexts_seen = set()

        # 1) Grids por vínculo de equipe (titular/reserva) - fonte principal.
        team_links = [t for t in perfil.teams if t.season_id == s.id] + [t for t in perfil.reserve_teams if t.season_id == s.id]
        for t in team_links:
            g_id = t.grid_id
            g_name = t.grid_config.nome if t.grid_config else t.grid
            if g_id in cfg_by_id:
                g_name = cfg_by_id[g_id].nome
            if not g_name:
                continue
            key = (s.id, g_name)
            if key in contexts_seen:
                continue
            contexts_seen.add(key)
            available_contexts.append({
                'season_id': s.id,
                'season_nome': s.nome,
                'grid': g_name,
                'grid_id': g_id
            })

        # 2) Grids por resultados (fallback/histórico).
        races_res = db.session.query(Race).join(RaceResult).filter(
            RaceResult.pilot_id == perfil.id,
            Race.season_id == s.id
        ).distinct().all()
        for r in races_res:
            g_name = r.grid_config.nome if r.grid_config else r.grid
            key = (s.id, g_name)
            if not g_name or key in contexts_seen:
                continue
            contexts_seen.add(key)
            available_contexts.append({
                'season_id': s.id,
                'season_nome': s.nome,
                'grid': g_name,
                'grid_id': r.grid_id
            })

        # 3) Grids do perfil (aceita ID ou nome).
        for pg in p_grids:
            cfg = None
            g_name = None
            g_id = None

            if pg.isdigit():
                g_id = int(pg)
                cfg = cfg_by_id.get(g_id)
                if cfg:
                    g_name = cfg.nome
            else:
                if pg in valid_names:
                    g_name = pg
                    cfg = next((c for c in configs if c.nome == pg), None)
                    g_id = cfg.id if cfg else None

            if not g_name:
                continue
            key = (s.id, g_name)
            if key in contexts_seen:
                continue
            contexts_seen.add(key)
            available_contexts.append({
                'season_id': s.id,
                'season_nome': s.nome,
                'grid': g_name,
                'grid_id': g_id
            })

    sel_season_id = request.args.get('s', type=int)
    sel_grid = request.args.get('g')
    
    current_context = None
    if sel_season_id and sel_grid:
        current_context = next((c for c in available_contexts if c['season_id'] == sel_season_id and c['grid'] == sel_grid), None)
    
    if not current_context and available_contexts:
        default_grid = p_grids[0] if p_grids else 'SEM_GRID'
        current_context = next((c for c in available_contexts if c['grid'] == default_grid), available_contexts[0])
    
    quali_ban = False
    # Lógica de Foto por Grid (baseada em ID)
    if current_context:
        grid_id_contexto = current_context.get('grid_id')
        if grid_id_contexto:
            grid_photo = next((gp for gp in perfil.grid_photos if hasattr(gp, 'grid_id') and gp.grid_id == grid_id_contexto), None)
            if grid_photo:
                perfil.foto_url = grid_photo.foto_url
    
    current_team = None
    if current_context:
        ctx_grid_id = current_context.get('grid_id')
        if ctx_grid_id:
            current_team = next((t for t in perfil.teams if t.season_id == current_context['season_id'] and t.grid_id == ctx_grid_id), None)
        else:
            current_team = next((t for t in perfil.teams if t.season_id == current_context['season_id'] and 
                                 ((t.grid_config and t.grid_config.nome == current_context['grid']) or t.grid == current_context['grid'])), None)

        if not current_team:
            if ctx_grid_id:
                current_team = next((t for t in perfil.reserve_teams if t.season_id == current_context['season_id'] and t.grid_id == ctx_grid_id), None)
            else:
                current_team = next((t for t in perfil.reserve_teams if t.season_id == current_context['season_id'] and 
                                     ((t.grid_config and t.grid_config.nome == current_context['grid']) or t.grid == current_context['grid'])), None)

    if current_context:
        cnh_info = perfil.get_cnh_info(current_context['season_id'], current_context['grid_id'])
        perfil.pontos_cnh = cnh_info['cnh']
        perfil.advertencias_acumuladas = cnh_info['advertencias']
        
        # Verificação de Quali Ban (100% via ID do Grid)
        grid_id_contexto = current_context.get('grid_id')
        ultimo_p = Protesto.query.filter_by(acusado_id=perfil.id, grid_id=grid_id_contexto, status='CONCLUIDO')\
            .filter(Protesto.veredito_final.in_(['MEDIA', 'GRAVE']))\
            .order_by(Protesto.data_fechamento.desc()).first()
            
        if ultimo_p:
            ultima_res = RaceResult.query.join(Race).filter(
                RaceResult.pilot_id == perfil.id, 
                Race.grid_id == grid_id_contexto,
                Race.status == 'Concluida',
                RaceResult.ausencia == None
            ).order_by(Race.data_corrida.desc()).first()
            if not ultima_res or ultimo_p.data_fechamento.date() >= ultima_res.race.data_corrida:
                quali_ban = True

    if perfil.esta_banido():
        flash('ALERTA: Sua CNH está zerada ou negativa. Você está suspenso das atividades de pista.', 'danger')
    
    checkin_race = None
    registro_atual = None
    
    hoje = datetime.utcnow().date()
    if current_context:
        p_grid_ids = set(int(g) for g in p_grids if g.isdigit())
        p_grid_names = set(g.upper() for g in p_grids if not g.isdigit())
        ctx_grid_id = current_context.get('grid_id')
        ctx_grid_name = (current_context.get('grid') or '').upper()
        pode_ver_checkin = (
            (ctx_grid_id in p_grid_ids if ctx_grid_id else False) or
            (ctx_grid_name in p_grid_names) or
            ('RESERVA' in p_grid_names) or
            (current_team is not None)
        )

        if pode_ver_checkin:
            proxima = None
            futuras_q = Race.query.filter(
                Race.season_id == current_context['season_id'],
                Race.status != 'Concluida',
                Race.data_corrida >= hoje
            )
            if ctx_grid_id:
                futuras_q = futuras_q.filter(Race.grid_id == ctx_grid_id)
            futuras = futuras_q.order_by(Race.data_corrida).all()

            for r in futuras:
                r_gname = (r.grid_config.nome if r.grid_config else r.grid or '').upper()
                if (ctx_grid_id and r.grid_id == ctx_grid_id) or (not ctx_grid_id and r_gname == ctx_grid_name):
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
        grid_id_calc = current_context.get('grid_id')
        
        # Usa a função centralizada para calcular pontos totais
        if grid_id_calc:
            meus_pontos_camp = calcular_pontos_totais_piloto(perfil.id, s_id, grid_id_calc)
        
        all_races_season = Race.query.filter_by(season_id=s_id).order_by(Race.data_corrida).all()
        if grid_id_calc:
            corridas = [r for r in all_races_season if r.grid_id == grid_id_calc]
        else:
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
                if team_has_results_in_season(team, s.id):
                    season_ativa = s
                    break
            
            if not season_ativa:
                season_ativa = active_seasons[0]
        else:
            season_ativa = all_seasons[0] if all_seasons else None

    total_pontos = 0.0
    total_vitorias = 0
    stats_pilotos = []
    if season_ativa:
        profile_stats = get_team_profile_stats(team, season_ativa.id)
        total_pontos = profile_stats["total_pontos"]
        total_vitorias = profile_stats["total_vitorias"]
        # Exibe apenas titulares atualmente cadastrados nesta equipe.
        stats_by_pilot_id = {item["piloto"].id: item for item in profile_stats["stats_pilotos"]}
        stats_pilotos = []
        for p in sorted(team.pilots, key=lambda x: (x.nickname or "").upper()):
            st = stats_by_pilot_id.get(p.id)
            stats_pilotos.append({
                "piloto": p,
                "pontos": float(st["pontos"]) if st else 0.0,
                "vitorias": int(st["vitorias"]) if st else 0,
            })
            
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
            
    # Upload de foto específica por grid (baseado em ID)
    grid_photo_target_id = request.form.get('grid_photo_target', type=int)
    if grid_photo_target_id and 'grid_photo_file' in request.files:
        g_file = request.files['grid_photo_file']
        if g_file and g_file.filename != '' and allowed_file(g_file.filename):
            # Busca e substitui a foto anterior para este grid_id
            old_gp = PilotGridPhoto.query.filter_by(pilot_id=current_user.pilot_profile.id, grid_id=grid_photo_target_id).first()
            if old_gp:
                old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], old_gp.foto_url)
                if os.path.exists(old_path): os.remove(old_path)
                db.session.delete(old_gp)
            
            ext = g_file.filename.rsplit('.', 1)[1].lower()
            timestamp = int(datetime.utcnow().timestamp())

            # Usa o nome do grid para um nome de arquivo mais descritivo
            grid_cfg = db.session.get(GridConfig, grid_photo_target_id)
            grid_name_for_file = grid_cfg.nome.replace(" ", "_") if grid_cfg else f"grid_{grid_photo_target_id}"

            nome_gp = f"piloto_{current_user.pilot_profile.id}_{grid_name_for_file}_{timestamp}.{ext}"
            g_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], nome_gp))
            
            # Salva a nova foto com o grid_id
            new_gp = PilotGridPhoto(pilot_id=current_user.pilot_profile.id, grid_id=grid_photo_target_id, foto_url=nome_gp)
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
        etapa_id = request.form.get('race_id')
        race = db.session.get(Race, etapa_id)
        novo = Protesto(
            etapa_id=etapa_id,
            grid_id=race.grid_id if race else None,
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
