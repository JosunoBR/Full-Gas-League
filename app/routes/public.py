import os
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import check_password_hash
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from app.models import db, Season, Race, PilotProfile, Protesto, RaceResult, VotoComissario, Team, RaceRegistration, User, Invite, News, GridConfig, SeasonChampion, PilotGridPhoto
from app.utils import allowed_file, get_embed_url, ORDEM_CARROS, get_grid_name, find_grid_config, grid_matches
from app.services.team_context import build_team_context
from app.services.standings_service import StandingsService
from app.services.scoring_service import ScoringService
from app.services.discipline_service import DisciplineService
from app.services.notification_service import NotificationService

public_bp = Blueprint('public', __name__)

# --- FUNÇÕES AUXILIARES ---

def _parse_profile_grids(profile_grid_value):
    tokens = [g.strip() for g in (profile_grid_value or "").split(",") if g.strip()]
    ids = {int(g) for g in tokens if g.isdigit()}
    names = {g.upper() for g in tokens if not g.isdigit()}
    return ids, names


def _pilot_has_membership_for_race(pilot, race):
    if not pilot or not race:
        return False

    # Fonte principal: vinculos de equipe (titular/reserva) por temporada + grid.
    has_team_link = any(
        t.season_id == race.season_id and t.grid_id == race.grid_id
        for t in pilot.teams
    ) or any(
        t.season_id == race.season_id and t.grid_id == race.grid_id
        for t in pilot.reserve_teams
    )
    if has_team_link:
        return True

    # Fallback legado: campo textual de grids no perfil.
    grid_ids, grid_names = _parse_profile_grids(pilot.grid)
    if race.grid_id and race.grid_id in grid_ids:
        return True
    race_grid_name = (race.grid_config.nome if race.grid_config else race.grid or "").upper()
    if race_grid_name and race_grid_name in grid_names:
        return True
    if "RESERVA" in grid_names:
        return True

    return False


def _can_interact_with_checkin(pilot, race, today):
    if not pilot or not race:
        return False
    if race.status == "Concluida":
        return False
    if not race.data_corrida:
        return False
    if race.data_corrida < today:
        return False
    if (race.data_corrida - today).days > 2:
        return False
    return _pilot_has_membership_for_race(pilot, race)


def _get_active_protest_scope(profile):
    active_seasons_ids = [s.id for s in Season.query.filter_by(ativa=True).all()]
    has_active_team = False
    my_team_grid_ids = set()

    for team in profile.teams:
        if team.season_id in active_seasons_ids:
            has_active_team = True
            if team.grid_id:
                my_team_grid_ids.add(team.grid_id)

    for team in profile.reserve_teams:
        if team.season_id in active_seasons_ids:
            has_active_team = True
            if team.grid_id:
                my_team_grid_ids.add(team.grid_id)

    is_valid_pilot = False
    for grid_token in (profile.grid or '').upper().split(','):
        grid_token = grid_token.strip()
        if grid_token.isdigit() or grid_token == 'RESERVA':
            is_valid_pilot = True
            if grid_token.isdigit():
                my_team_grid_ids.add(int(grid_token))

    return active_seasons_ids, has_active_team, my_team_grid_ids, is_valid_pilot

# --- ROTAS PRINCIPAIS (HOME E LOGIN) ---

@public_bp.route('/')
def home():
    all_active_seasons = Season.query.filter_by(ativa=True).order_by(Season.id.asc()).all()
    if not all_active_seasons:
        all_active_seasons = Season.query.order_by(Season.id.desc()).all()
    
    selected_season_id = request.args.get('s', type=int)
    season_ativa = None
    if selected_season_id:
        season_ativa = next((s for s in all_active_seasons if s.id == selected_season_id), None)
    if not season_ativa and all_active_seasons:
        season_ativa = all_active_seasons[0]
    
    if not season_ativa:
        return render_template('home.html', season_ativa=None, all_seasons=all_active_seasons, noticias=[], grid_configs=[], standings={}, constructors={}, calendar={}, last_races={}, pilots_by_grid={})

    # Passo 3: Refatoração para usar StandingsService com Cache
    data = StandingsService.get_home_data(season_ativa.id)

    # --- INÍCIO DA CORREÇÃO PONTUAL PARA CONSTRUTORES NA HOME ---
    # A lógica abaixo recalcula a pontuação dos construtores para corrigir a inconsistência,
    # aplicando as deduções de penalidades que o StandingsService pode não estar considerando.
    # Esta é a mesma lógica usada no painel /admin/overview.

    # 1. Coleta todas as punições da temporada para eficiência
    punicoes_temporada = Protesto.query.join(Race).filter(
        Protesto.status == 'CONCLUIDO',
        Race.season_id == season_ativa.id
    ).all()
    punicoes_by_pilot = {}
    for prot in punicoes_temporada:
        if prot.acusado_id not in punicoes_by_pilot:
            punicoes_by_pilot[prot.acusado_id] = []
        punicoes_by_pilot[prot.acusado_id].append(prot)

    PONTOS_PENALIDADE = {'LEVE': 3, 'MEDIA': 5, 'GRAVE': 10}
    new_constructors_data = {}

    # 2. Itera sobre os grids da temporada ativa
    grid_configs = data.get('grid_configs', [])
    for g_cfg in grid_configs:
        g_id = g_cfg.id
        team_points = {}
        
        results = RaceResult.query.join(Race).filter(Race.season_id == season_ativa.id, Race.grid_id == g_id).all()
        
        for rr in results:
            team = rr.team_snapshot if hasattr(rr, 'team_snapshot') else rr.team
            if not team: continue

            raw_points = float(rr.pontos_ganhos or 0)
            deductions = sum(PONTOS_PENALIDADE.get(p.veredito_final, 0) for p in punicoes_by_pilot.get(rr.pilot_id, []) if p.etapa_id == rr.race_id)
            net_points = raw_points - deductions

            team_points.setdefault(team.id, {'team': team, 'points': 0.0})['points'] += net_points
            
        new_constructors_data[g_id] = sorted(team_points.values(), key=lambda x: x['points'], reverse=True)

    if 'constructors' in data:
        data['constructors'] = new_constructors_data
    # --- FIM DA CORREÇÃO PONTUAL ---

    return render_template('home.html', season_ativa=season_ativa, all_seasons=all_active_seasons, **data)

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
        cnh_info = DisciplineService.get_pilot_discipline_stats(perfil.id, current_context['season_id'], current_context['grid_id'])
        perfil.pontos_cnh = cnh_info['cnh']
        perfil.advertencias_acumuladas = cnh_info['advertencias']
        
        # Verificação de Quali Ban (100% via ID do Grid)
        grid_id_contexto = current_context.get('grid_id')
        if grid_id_contexto:
            quali_ban = DisciplineService.is_quali_banned(perfil.id, grid_id_contexto)

    meus_pontos_camp = 0
    desempenho_temporada = []
    if current_context:
        s_id = current_context['season_id']
        g_name = current_context['grid']
        grid_id_calc = current_context.get('grid_id')
        
        # Usa a função centralizada para calcular pontos totais
        if grid_id_calc:
            meus_pontos_camp = ScoringService.calculate_pilot_total_points(perfil.id, s_id, grid_id_calc)
        
        all_races_season = Race.query.filter_by(season_id=s_id).order_by(Race.data_corrida).all()
        corridas = [r for r in all_races_season if (r.grid_config and r.grid_config.nome == g_name) or r.grid == g_name]
        
        for race in corridas:
            resultado = next((r for r in race.results if r.pilot_id == perfil.id), None)
            desempenho_temporada.append({
                'gp': race.nome_gp, 'data': race.data_corrida, 'status_corrida': race.status,
                'participou': True if resultado and resultado.status_presenca == 'OK' else False,
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
        cnh_info = DisciplineService.get_pilot_discipline_stats(perfil.id, current_context['season_id'], current_context['grid_id'])
        perfil.pontos_cnh = cnh_info['cnh']
        perfil.advertencias_acumuladas = cnh_info['advertencias']
        
        # Verificação de Quali Ban (100% via ID do Grid)
        grid_id_contexto = current_context.get('grid_id')
        if grid_id_contexto:
            quali_ban = DisciplineService.is_quali_banned(perfil.id, grid_id_contexto)

    if perfil.esta_banido():
        flash('ALERTA: Sua CNH está zerada ou negativa. Você está suspenso das atividades de pista.', 'danger')
    
    checkin_race = None
    registro_atual = None
    
    hoje = (datetime.utcnow() - timedelta(hours=3)).date()
    if current_context:
        ctx_grid_id = current_context.get('grid_id')
        ctx_grid_name = (current_context.get('grid') or '').upper()
        futuras_q = Race.query.filter(
            Race.season_id == current_context['season_id'],
            Race.status != 'Concluida',
            Race.data_corrida >= hoje
        )
        if ctx_grid_id:
            futuras_q = futuras_q.filter(Race.grid_id == ctx_grid_id)
        futuras = futuras_q.order_by(Race.data_corrida, Race.id).all()

        for r in futuras:
            r_gname = (r.grid_config.nome if r.grid_config else r.grid or '').upper()
            same_context_grid = (ctx_grid_id and r.grid_id == ctx_grid_id) or (not ctx_grid_id and r_gname == ctx_grid_name)
            if not same_context_grid:
                continue
            if _can_interact_with_checkin(perfil, r, hoje):
                reg = RaceRegistration.query.filter_by(race_id=r.id, pilot_id=perfil.id).first()
                if not reg or reg.status not in ['CONFIRMADO', 'JUSTIFICADO']:
                    checkin_race = r
                    registro_atual = reg
                    break

    meus_pontos_camp = 0
    desempenho_temporada = []
    if current_context:
        s_id = current_context['season_id']
        g_name = current_context['grid']
        grid_id_calc = current_context.get('grid_id')
        
        # Usa a função centralizada para calcular pontos totais
        if grid_id_calc:
            meus_pontos_camp = ScoringService.calculate_pilot_total_points(perfil.id, s_id, grid_id_calc)
        
        all_races_season = Race.query.filter_by(season_id=s_id).order_by(Race.data_corrida).all()
        if grid_id_calc:
            corridas = [r for r in all_races_season if r.grid_id == grid_id_calc]
        else:
            corridas = [r for r in all_races_season if (r.grid_config and r.grid_config.nome == g_name) or r.grid == g_name]
        
        for race in corridas:
            resultado = next((r for r in race.results if r.pilot_id == perfil.id), None)
            desempenho_temporada.append({
                'gp': race.nome_gp, 'data': race.data_corrida, 'status_corrida': race.status,
                'participou': True if resultado and resultado.status_presenca == 'OK' else False,
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
    race = Race.query.get_or_404(race_id)
    
    if current_user.pilot_profile.esta_banido():
        flash('Você está com a CNH Suspensa/Banida e não pode correr.', 'danger')
        return redirect(url_for('public.my_profile'))
        
    today = (datetime.utcnow() - timedelta(hours=3)).date()
    if not _can_interact_with_checkin(current_user.pilot_profile, race, today):
        flash('Check-in indisponivel para esta corrida no seu contexto atual.', 'warning')
        return redirect(url_for('public.my_profile'))

    # Busca corridas candidatas no mesmo dia/grid/temporada.
    same_day_candidates = Race.query.filter(
        Race.season_id == race.season_id,
        Race.grid_id == race.grid_id,
        Race.data_corrida == race.data_corrida,
        Race.status != 'Concluida',
    ).all()

    # Sincroniza apenas corridas do mesmo evento (mesmo GP ou mesma pista),
    # evitando confirmar GPs diferentes que por acaso estejam na mesma data.
    same_day_races = [
        r for r in same_day_candidates
        if (r.nome_gp == race.nome_gp) or (r.pista == race.pista)
    ]
    if not same_day_races:
        same_day_races = [race]

    for r in same_day_races:
        registro = RaceRegistration.query.filter_by(
            race_id=r.id, pilot_id=current_user.pilot_profile.id
        ).first()
        if not registro:
            registro = RaceRegistration(race_id=r.id, pilot_id=current_user.pilot_profile.id)
            db.session.add(registro)

        registro.status = 'CONFIRMADO'
        registro.justificativa = None
        registro.data_resposta = datetime.utcnow()

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash('Nao foi possivel confirmar o check-in. Tente novamente.', 'danger')
        return redirect(url_for('public.my_profile'))
    if len(same_day_races) > 1:
        flash('Presença confirmada para todas as corridas do mesmo dia neste grid.', 'success')
    else:
        flash('Presença confirmada! Boa corrida!', 'success')
    return redirect(url_for('public.my_profile'))

@public_bp.route('/checkin/absent/<int:race_id>', methods=['POST'])
@login_required
def checkin_absent(race_id):
    if not current_user.pilot_profile: return redirect(url_for('public.home'))
    race = Race.query.get_or_404(race_id)
    motivo = (request.form.get('justificativa') or '').strip()
    if not motivo:
        flash('E obrigatorio informar o motivo da ausencia.', 'warning')
        return redirect(url_for('public.my_profile'))

    today = (datetime.utcnow() - timedelta(hours=3)).date()
    if not _can_interact_with_checkin(current_user.pilot_profile, race, today):
        flash('Check-in indisponivel para esta corrida no seu contexto atual.', 'warning')
        return redirect(url_for('public.my_profile'))

    registro = RaceRegistration.query.filter_by(race_id=race_id, pilot_id=current_user.pilot_profile.id).first()
    if not registro:
        registro = RaceRegistration(race_id=race_id, pilot_id=current_user.pilot_profile.id)
        db.session.add(registro)
    
    registro.status = 'JUSTIFICADO'
    registro.justificativa = motivo
    registro.data_resposta = datetime.utcnow()
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash('Nao foi possivel registrar a ausencia. Tente novamente.', 'danger')
        return redirect(url_for('public.my_profile'))
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
                if ScoringService.team_has_results_in_season(team, s.id):
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
        profile_stats = ScoringService.get_team_profile_stats(team, season_ativa.id)
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
    nome_real = (request.form.get('nome_real') or '').strip()
    new_nickname = (request.form.get('nickname') or '').strip()[:50]
    if not nome_real or not new_nickname:
        flash('Nome real e nickname sao obrigatorios.', 'warning')
        return redirect(url_for('public.my_profile'))

    existing_user = User.query.filter(User.username == new_nickname, User.id != current_user.id).first()
    if existing_user:
        flash('Este nickname ja esta em uso. Escolha outro.', 'danger')
        return redirect(url_for('public.my_profile'))

    current_user.pilot_profile.nome_real = nome_real[:100]
    current_user.pilot_profile.nickname = new_nickname
    current_user.username = new_nickname # Mantem o login em sincronia
    telefone_raw = (request.form.get('telefone') or '').strip()
    current_user.pilot_profile.telefone = telefone_raw[:20] if telefone_raw else None
    
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
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except OSError:
                        pass
                
            ext = file.filename.rsplit('.', 1)[1].lower()
            timestamp = int(datetime.utcnow().timestamp())
            nome = f"piloto_{current_user.pilot_profile.id}_{timestamp}.{ext}"
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], nome))
            current_user.pilot_profile.foto_url = nome
            
    # Upload de foto especifica por grid (baseado em ID)
    grid_photo_target_raw = (request.form.get('grid_photo_target') or '').strip()
    grid_photo_target_id = None
    grid_cfg = None
    if grid_photo_target_raw:
        if grid_photo_target_raw.isdigit():
            grid_photo_target_id = int(grid_photo_target_raw)
        else:
            grid_cfg = GridConfig.query.filter_by(nome=grid_photo_target_raw).first()
            if grid_cfg:
                grid_photo_target_id = grid_cfg.id

    if grid_photo_target_id and 'grid_photo_file' in request.files:
        g_file = request.files['grid_photo_file']
        if g_file and g_file.filename != '' and allowed_file(g_file.filename):
            # Busca e substitui a foto anterior para este grid_id
            old_gp = PilotGridPhoto.query.filter_by(pilot_id=current_user.pilot_profile.id, grid_id=grid_photo_target_id).first()
            if old_gp:
                old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], old_gp.foto_url)
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except OSError:
                        pass
                db.session.delete(old_gp)
            
            ext = g_file.filename.rsplit('.', 1)[1].lower()
            timestamp = int(datetime.utcnow().timestamp())

            # Usa o nome do grid para um nome de arquivo mais descritivo
            if not grid_cfg:
                grid_cfg = db.session.get(GridConfig, grid_photo_target_id)
            grid_name_for_file = grid_cfg.nome.replace(" ", "_") if grid_cfg else f"grid_{grid_photo_target_id}"

            nome_gp = f"piloto_{current_user.pilot_profile.id}_{grid_name_for_file}_{timestamp}.{ext}"
            g_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], nome_gp))
            
            # Salva a nova foto com o grid_id
            new_gp = PilotGridPhoto(pilot_id=current_user.pilot_profile.id, grid_id=grid_photo_target_id, foto_url=nome_gp)
            db.session.add(new_gp)

    delete_gp_id = request.form.get('delete_grid_photo_id', type=int)
    if delete_gp_id:
        gp_to_del = PilotGridPhoto.query.get(delete_gp_id)
        if gp_to_del and gp_to_del.pilot_id == current_user.pilot_profile.id:
            path = os.path.join(current_app.config['UPLOAD_FOLDER'], gp_to_del.foto_url)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
            db.session.delete(gp_to_del)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash('Nao foi possivel salvar. Verifique se o nickname ja existe.', 'danger')
        return redirect(url_for('public.my_profile'))
    return redirect(url_for('public.my_profile'))

@public_bp.route('/protestar', methods=['GET', 'POST'])
@login_required
def open_protest():
    if not current_user.pilot_profile: return redirect(url_for('public.home'))
    user_profile = current_user.pilot_profile
    active_seasons_ids, has_active_team, my_team_grid_ids, is_valid_pilot = _get_active_protest_scope(user_profile)

    if request.method == 'POST':
        etapa_id = request.form.get('race_id', type=int)
        if not etapa_id:
            flash('Selecione uma corrida valida para abrir o protesto.', 'warning')
            return redirect(url_for('public.open_protest'))

        race = db.session.get(Race, etapa_id)
        if not race:
            flash('Corrida nao encontrada.', 'danger')
            return redirect(url_for('public.open_protest'))
        if not race.season or not race.season.ativa or race.season_id not in active_seasons_ids:
            flash('Nao e possivel abrir protesto para uma corrida de temporada encerrada.', 'warning')
            return redirect(url_for('public.open_protest'))
        if not race.grid_id:
            flash('Corrida sem grid vinculado. Contate a administracao.', 'danger')
            return redirect(url_for('public.open_protest'))
        if not has_active_team and not is_valid_pilot:
            flash('Voce precisa estar vinculado a um grid aberto para abrir protestos.', 'warning')
            return redirect(url_for('public.my_profile'))
        if not _pilot_has_membership_for_race(user_profile, race):
            flash('Voce nao esta vinculado ao grid aberto desta corrida.', 'warning')
            return redirect(url_for('public.open_protest'))

        acusado_id = request.form.get('acusado_id', type=int)
        acusado = db.session.get(PilotProfile, acusado_id) if acusado_id else None
        if not acusado or acusado.id == user_profile.id:
            flash('Selecione um piloto valido para abrir o protesto.', 'warning')
            return redirect(url_for('public.open_protest'))
        if not _pilot_has_membership_for_race(acusado, race):
            flash('O piloto acusado nao pertence ao grid desta corrida.', 'warning')
            return redirect(url_for('public.open_protest'))

        novo = Protesto(
            etapa_id=etapa_id,
            grid_id=race.grid_id,
            acusador_id=user_profile.id,
            acusado_id=acusado.id,
            video_link=request.form.get('video'),
            minuto=request.form.get('minuto'),
            descricao=request.form.get('descricao'),
            status='AGUARDANDO_DEFESA',
            data_criacao=datetime.utcnow()
        )
        db.session.add(novo)
        db.session.commit()

        # Envia notificação para o piloto acusado
        try:
            acusado = PilotProfile.query.get(novo.acusado_id)
            if acusado and acusado.fcm_token:
                NotificationService.send_single_notification(
                    token=acusado.fcm_token,
                    title="🚨 Novo Protesto Registrado",
                    body=f"Você foi citado no protesto #{novo.id} por {novo.acusador.nickname}. Acesse o site para apresentar sua defesa."
                )
        except Exception as e:
            print(f"Falha ao enviar notificação de protesto: {e}")

        return redirect(url_for('public.my_profile'))
    
    if not has_active_team and not is_valid_pilot:
        flash('Você precisa estar vinculado a um grid para abrir protestos.', 'warning')
        return redirect(url_for('public.my_profile'))

    races = []
    pilots = []

    if has_active_team:
        # CENÁRIO 1: Vinculado a equipe -> Restringe aos grids da equipe
        # Mostra corridas apenas dos grids onde ele corre pela equipe
        races = Race.query.filter(
            Race.season_id.in_(active_seasons_ids),
            Race.grid_id.in_(my_team_grid_ids)
        ).order_by(Race.data_corrida.desc()).all()
        
        # Filtra pilotos que também estão nesses grids (para acusar)
        # Nota: Trazemos todos e filtramos no Python para garantir cruzamento correto de grids
        all_pilots = PilotProfile.query.filter(PilotProfile.id != user_profile.id).order_by(PilotProfile.nickname).all()
        for p in all_pilots:
            p_grids = set()
            for g in (p.grid or '').split(','):
                if g.strip().isdigit(): p_grids.add(int(g.strip()))
            for t in p.teams:
                if t.season_id in active_seasons_ids and t.grid_id: p_grids.add(t.grid_id)
            for t in p.reserve_teams:
                if t.season_id in active_seasons_ids and t.grid_id: p_grids.add(t.grid_id)
            
            if p_grids & my_team_grid_ids:
                pilots.append(p)
    else:
        # CENÁRIO 2: Sem equipe (Reserva Global) -> Acesso Total
        # Pode ver todas as corridas e acusar qualquer piloto
        all_races = Race.query.filter(Race.season_id.in_(active_seasons_ids)).order_by(Race.data_corrida.desc()).all()
        races = all_races
        pilots = PilotProfile.query.filter(PilotProfile.id != user_profile.id).order_by(PilotProfile.nickname).all()
        
    return render_template('pilot/protest.html', races=races, pilots=pilots)
