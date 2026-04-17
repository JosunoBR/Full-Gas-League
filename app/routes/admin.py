import os
import secrets
import shutil
from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, abort
from flask_login import login_required, current_user
from sqlalchemy import func, case
from app.models import db, User, PilotProfile, Season, Race, RaceResult, Invite, Protesto, VotoComissario, Team, RaceRegistration, SeletivaEntry, News, GridConfig, SeasonChampion, PilotGridPhoto, HomeCache
from app.utils import allowed_file, get_embed_url, PONTUACAO_20, PONTUACAO_22, ORDEM_CARROS, calcular_perda, get_grid_name, find_grid_config, grid_matches
from app.services.scoring_service import ScoringService
from app.services.diagnostics import build_data_health_report
from app.services.seletiva_service import SeletivaService
from app.services.race_result_service import RaceResultService
from app.services.stats_service import StatsService
from app.services.domain_rules import validate_unique_membership_per_grid

admin_bp = Blueprint('admin', __name__)


def _cleanup_closed_season_profile_grids(season, grid_configs):
    closed_grid_ids = {str(cfg.id) for cfg in grid_configs if cfg and cfg.id}
    closed_grid_names = {
        (cfg.nome or '').strip().upper()
        for cfg in grid_configs
        if (cfg.nome or '').strip()
    }
    closed_grid_names.update(
        (grid_name or '').strip().upper()
        for (grid_name,) in db.session.query(Race.grid).filter_by(season_id=season.id).distinct().all()
        if (grid_name or '').strip()
    )

    other_active_ids = [
        s.id for s in Season.query.filter(Season.id != season.id, Season.ativa == True).all()
    ]
    other_active_names = set()
    if other_active_ids:
        other_active_names.update(
            (cfg.nome or '').strip().upper()
            for cfg in GridConfig.query.filter(GridConfig.season_id.in_(other_active_ids)).all()
            if (cfg.nome or '').strip()
        )
        other_active_names.update(
            (grid_name or '').strip().upper()
            for (grid_name,) in db.session.query(Race.grid).filter(Race.season_id.in_(other_active_ids)).distinct().all()
            if (grid_name or '').strip()
        )

    removable_legacy_names = closed_grid_names - other_active_names

    pilots = PilotProfile.query.filter(PilotProfile.grid != 'SEM_GRID').all()
    for pilot in pilots:
        tokens = [token.strip() for token in (pilot.grid or '').split(',') if token.strip()]
        cleaned_tokens = []
        seen = set()
        for token in tokens:
            token_upper = token.upper()
            should_remove = (
                (token.isdigit() and token in closed_grid_ids)
                or (not token.isdigit() and token_upper in removable_legacy_names)
            )
            if should_remove or token in seen:
                continue
            cleaned_tokens.append(token)
            seen.add(token)

        pilot.grid = ",".join(cleaned_tokens) if cleaned_tokens else 'SEM_GRID'


def _archive_season_teams_and_unlink_pilots(season):
    teams = Team.query.filter_by(season_id=season.id).all()
    for team in teams:
        team.ativa = False
        team.pilots.clear()
        team.reserves.clear()

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
    # 1. Permite acesso geral para ADMs e Narradores
    if current_user.role not in ['SUPER_ADM', 'ADM', 'NARRADOR']:
        flash('Acesso negado. Área restrita à Direção de Prova.', 'danger')
        return redirect(url_for('public.home'))

    # 2. Restrições específicas para Narrador (apenas leitura)
    if current_user.role == 'NARRADOR':
        endpoint_name = request.endpoint.split('.')[-1]

        # Whitelist de endpoints permitidos para o Narrador
        allowed_endpoints = [
            'overview',
            'pilot_stats',
            'pilot_career_stats',
        ]

        if endpoint_name not in allowed_endpoints:
            flash('Narradores têm acesso apenas à tela de Overview e Estatísticas.', 'warning')
            # O ponto de entrada seguro para o narrador é a overview.
            return redirect(url_for('admin.overview'))

# --- DASHBOARD E VISÃO GERAL ---

def converter_overview_para_json(dados_grids):
    """Transforma estrutura de dados de overview em formato serializável."""
    resultado = {}
    for grid_id, info in dados_grids.items():
        resultado[grid_id] = {}
        # classificaçao
        resultado[grid_id]['classificacao'] = []
        for row in info.get('classificacao', []):
            piloto = row['piloto']
            resultado[grid_id]['classificacao'].append({
                'piloto': {
                    'id': piloto.id,
                    'nickname': piloto.nickname,
                    'nome_real': piloto.nome_real
                },
                'vitorias': row.get('vitorias'),
                'podios': row.get('podios'),
                'pontos': row.get('pontos'),
                'team_name': row.get('team_name'),
                'is_reserve': row.get('is_reserve', False)
            })
        # evol_chart
        resultado[grid_id]['evol_chart'] = []
        for entry in info.get('evol_chart', []):
            piloto = entry['piloto']
            resultado[grid_id]['evol_chart'].append({
                'piloto': {'id': piloto.id, 'nickname': piloto.nickname, 'nome_real': piloto.nome_real},
                'evol': entry['evol']
            })
    return resultado


@admin_bp.route('/dashboard')
def dashboard():
    all_active_seasons = Season.query.filter_by(ativa=True).order_by(Season.id.desc()).all()
    
    selected_season_id = request.args.get('s', type=int)
    season_ativa = None
    if selected_season_id:
        season_ativa = next((s for s in all_active_seasons if s.id == selected_season_id), None)
    
    if not season_ativa and all_active_seasons:
        season_ativa = all_active_seasons[0]
        
    return render_template('admin/dashboard.html', season_ativa=season_ativa, all_active_seasons=all_active_seasons)


@admin_bp.route('/data-health')
def data_health():
    all_active_seasons = Season.query.filter_by(ativa=True).order_by(Season.id.desc()).all()
    selected_season_id = request.args.get('s', type=int)
    season_ativa = None
    if selected_season_id:
        season_ativa = next((s for s in all_active_seasons if s.id == selected_season_id), None)
    if not season_ativa:
        season_ativa = next((s for s in all_seasons if s.ativa), None)
    if not season_ativa and all_seasons:
        season_ativa = all_seasons[0]

    report = None
    if season_ativa:
        report = build_data_health_report(season_ativa.id)

    return render_template(
        'admin/data_health.html',
        season_ativa=season_ativa,
        all_seasons=all_seasons,
        report=report
    )

@admin_bp.route('/overview')
def overview():
    # 1. Busca todas as temporadas para as abas (Histórico completo)
    all_active_seasons = Season.query.filter_by(ativa=True).order_by(Season.id.desc()).all()
    
    # 2. Define a temporada ativa (Selecionada ou a mais recente)
    selected_season_id = request.args.get('s', type=int)
    season_ativa = None
    
    if selected_season_id:
        season_ativa = next((s for s in all_active_seasons if s.id == selected_season_id), None)
    
    if not season_ativa:
        # Tenta a mais recente ativa, senão a mais recente de todas
        season_ativa = all_active_seasons[0] if all_active_seasons else None
    
    # 3. Identifica os Grids (Dinâmico)
    grid_configs = []
    if season_ativa:
        # Busca os grids configurados especificamente para esta temporada
        grid_configs = GridConfig.query.filter_by(season_id=season_ativa.id).order_by(GridConfig.ordem).all()
    
    # 4. Prepara estrutura de dados
    dados_grids = {g.id: {'config': g, 'classificacao': [], 'disciplina': []} for g in grid_configs}

    # 5. Popula dados (se houver temporada)
    if season_ativa:
        # Carrega punições concluídas da temporada para o cálculo de pontos
        punicoes_temporada = Protesto.query.join(Race).filter(
            Protesto.status == 'CONCLUIDO',
            Race.season_id == season_ativa.id
        ).all()
        
        punicoes_by_pilot = {}
        for prot in punicoes_temporada:
            if prot.acusado_id not in punicoes_by_pilot:
                punicoes_by_pilot[prot.acusado_id] = []
            punicoes_by_pilot[prot.acusado_id].append(prot)

        pilotos = PilotProfile.query.join(User).all()
        all_season_teams = Team.query.filter_by(season_id=season_ativa.id).all()
        
        for p in pilotos:
            resultados_season = [r for r in p.race_results if r.race.season_id == season_ativa.id]
            grids_participados_ids = set()
            
            # 1. Identifica Grids via Equipe Titular (ID-only)
            teams_season = [t for t in all_season_teams if any(pilot.id == p.id for pilot in t.pilots)]
            for t in teams_season:
                g_id = t.grid_id
                if g_id: grids_participados_ids.add(g_id)
            
            # 2. Identifica Grids via Equipe Reserva (ID-only)
            reserves_season = [t for t in all_season_teams if any(pilot.id == p.id for pilot in t.reserves)]
            for t in reserves_season:
                g_id = t.grid_id
                if g_id: grids_participados_ids.add(g_id)

            for g_id in grids_participados_ids:
                if g_id in dados_grids:
                    # Filtra resultados comparando ID ou Nome (Fallback)
                    g_cfg_atual = dados_grids[g_id]['config']
                    res_no_grid = [r for r in resultados_season if grid_matches(r.race, g_cfg_atual)]
                    
                    my_punicoes = punicoes_by_pilot.get(p.id, [])
                    my_punicoes_grid = [pun for pun in my_punicoes if pun.grid_id == g_id]
                    
                    pontos_totais = ScoringService.calculate_pilot_total_points(p.id, season_ativa.id, g_id)
                    
                    vitorias = sum(1 for r in res_no_grid if r.posicao == 1 and not r.dsq)
                    podios = sum(1 for r in res_no_grid if r.posicao in [1, 2, 3] and not r.dsq)
                    
                    # Determina se é reserva neste grid específico
                    is_reserve = False
                    # Se não está em nenhuma equipe titular deste grid, mas está em uma reserva, é reserva
                    is_titular = any(t.grid_id == g_id for t in teams_season)
                    if not is_titular:
                        is_reserve = any(t.grid_id == g_id for t in reserves_season)

                    info = {
                        'piloto': p, 
                        'pontos': pontos_totais, 
                        'vitorias': vitorias, 
                        'podios': podios, 
                        'cnh': p.pontos_cnh, 
                        'advertencias': p.advertencias_acumuladas,
                        'punicoes': my_punicoes_grid,
                        'is_reserve': is_reserve
                    }
                    
                    # Evita duplicatas
                    if not any(x['piloto'].id == p.id for x in dados_grids[g_id]['classificacao']):
                        dados_grids[g_id]['classificacao'].append(info)
                
        # Ordenação e Limite de Vagas
        for g_id in dados_grids:
            # Ordena por pontos e vitórias
            dados_grids[g_id]['classificacao'].sort(key=lambda x: (x['pontos'], x['vitorias']), reverse=True)
            
            # A tabela de disciplina deve mostrar os mesmos pilotos do grid limitado, mas ordenados por CNH
            dados_grids[g_id]['disciplina'] = list(dados_grids[g_id]['classificacao'])
            dados_grids[g_id]['disciplina'].sort(key=lambda x: x['cnh'])
            
            # Estatísticas para o Dashboard do Grid
            classif = dados_grids[g_id]['classificacao']
            dados_grids[g_id]['stats'] = {
                'total_pilotos': len([x for x in classif if not x.get('is_reserve')]),
                'lider': classif[0]['piloto'].nickname if classif else 'N/A',
                'corridas_concluidas': Race.query.filter_by(season_id=season_ativa.id, grid_id=g_id, status='Concluida').count()
            }
            
            # --- additional data for overview ---
            # calendar summary
            races = Race.query.filter_by(season_id=season_ativa.id, grid_id=g_id).order_by(Race.data_corrida).all()
            today = datetime.utcnow().date()
            next_race = None
            past_races = []
            for r in races:
                if r.data_corrida and r.data_corrida >= today and not next_race:
                    next_race = r
                elif r.data_corrida and r.data_corrida < today:
                    past_races.append(r)
            dados_grids[g_id]['next_race'] = next_race
            dados_grids[g_id]['past_races'] = past_races[-3:]

            # check‑in statistics for the upcoming race
            if next_race:
                regs = RaceRegistration.query.filter_by(race_id=next_race.id).all()
                confirmed = sum(1 for r in regs if r.status == 'CONFIRMADO')
                absent = sum(1 for r in regs if r.status == 'AUSENTE')
                pending = max(0, len(regs) - confirmed - absent)
            else:
                confirmed = absent = pending = 0
            dados_grids[g_id]['checkin'] = {
                'confirmed': confirmed,
                'absent': absent,
                'pending': pending
            }
            
            # constructors standings
            PONTOS_PENALIDADE = {'LEVE': 3, 'MEDIA': 5, 'GRAVE': 10}
            team_points = {}
            results = RaceResult.query.join(Race).filter(Race.season_id == season_ativa.id, Race.grid_id == g_id).all()
            
            for rr in results:
                team = rr.team_snapshot if hasattr(rr, 'team_snapshot') else rr.team
                if not team: continue

                # Calcula os pontos líquidos para este resultado de corrida específico
                raw_points = float(rr.pontos_ganhos or 0)
                
                # Busca punições do tribunal para este piloto nesta corrida
                deductions = 0
                pilot_penalties = punicoes_by_pilot.get(rr.pilot_id, [])
                for penalty in pilot_penalties:
                    if penalty.etapa_id == rr.race_id:
                        deductions += PONTOS_PENALIDADE.get(penalty.veredito_final, 0)
                
                net_points = raw_points - deductions

                if team.id not in team_points:
                    team_points[team.id] = {'team': team, 'points': 0.0}
                team_points[team.id]['points'] += net_points
            dados_grids[g_id]['constructors'] = sorted(team_points.values(), key=lambda x: x['points'], reverse=True)
            
            # pending protests
            dados_grids[g_id]['pending_protests'] = Protesto.query.join(Race).filter(
                Race.season_id == season_ativa.id,
                Race.grid_id == g_id,
                Protesto.status.in_(['AGUARDANDO_DEFESA', 'EM_VOTACAO'])
            ).count()
            
            # pilots with no score in last 3 races
            last3 = past_races[-3:]
            no_score = []
            for row in dados_grids[g_id]['classificacao']:
                pid = row['piloto'].id
                pts = 0
                for race in last3:
                    rr = RaceResult.query.filter_by(pilot_id=pid, race_id=race.id).first()
                    if rr:
                        pts += float(rr.pontos_ganhos or 0)
                if pts == 0:
                    no_score.append(row['piloto'])
            dados_grids[g_id]['no_score_last3'] = no_score
            
            # average points per race
            pts_total = sum(x['pontos'] for x in classif)
            dados_grids[g_id]['avg_points_per_race'] = pts_total / len(races) if races else 0
            
            # evolution chart data for top pilots
            evol_list = []
            for info in classif[:5]:
                evol = ScoringService.generate_points_evolution(info['piloto'].id, g_id, season_ativa.id)
                evol_list.append({'piloto': info['piloto'], 'evol': evol})
            dados_grids[g_id]['evol_chart'] = evol_list
            
    # preparar versão serializável para uso em JS
    overview_json = converter_overview_para_json(dados_grids)

    return render_template('admin/overview.html', 
                           dados=dados_grids, 
                           overview_json=overview_json,
                           season=season_ativa,
                           season_ativa=season_ativa,
                           all_active_seasons=all_active_seasons,
                           grid_configs=grid_configs)


@admin_bp.route('/overview/stats')
def pilot_stats():
    """
    Página de estatísticas por piloto (estilo F1 TV), para uma temporada + grid.
    Usa os mesmos critérios de classificação da overview e resume os números
    diretamente a partir dos resultados das corridas.
    """
    season_id = request.args.get('season_id', type=int)
    grid_id = request.args.get('grid_id', type=int)

    if not season_id or not grid_id:
        flash('Parâmetros insuficientes para estatísticas.', 'danger')
        return redirect(url_for('admin.overview'))
    
    season = db.session.get(Season, season_id)
    grid_cfg = db.session.get(GridConfig, grid_id)
    
    if not season or not grid_cfg:
        flash('Dados não encontrados.', 'danger')
        return redirect(url_for('admin.overview'))

    # Usa o novo serviço para obter os dados
    stats_rows = StatsService.get_grid_statistics(season_id, grid_id)

    return render_template(
        'admin/estatistic.html',
        season=season,
        grid=grid_cfg,
        stats_rows=stats_rows,
    )

@admin_bp.route('/overview/stats/career')
def pilot_career_stats():
    """
    Página de estatísticas GERAIS (Carreira) de todos os pilotos.
    """
    pilot_id = request.args.get('pilot_id', type=int)
    stats_rows = StatsService.get_all_time_statistics(pilot_id=pilot_id)
    return render_template(
        'admin/estatistic.html',
        career_mode=True,
        stats_rows=stats_rows
    )

@admin_bp.route('/overview/export')
def export_classification():
    # parameters
    season_id = request.args.get('season_id', type=int)
    grid_id = request.args.get('grid_id', type=int)
    if not season_id or not grid_id:
        flash('Parâmetros insuficientes para exportar.', 'danger')
        return redirect(url_for('admin.overview', s=season_id))

    season = db.session.get(Season, season_id)
    if not season:
        flash('Temporada não encontrada.', 'danger')
        return redirect(url_for('admin.overview'))

    # Usa o mesmo serviço para garantir consistência dos dados
    stats_data = StatsService.get_grid_statistics(season_id, grid_id)

    # build csv
    import csv, io
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(['Pos','Piloto','Vitórias','Pódios','Pontos'])
    
    for idx, row in enumerate(stats_data, start=1):
        writer.writerow([idx, row['piloto'].nickname, row['wins'], row['podiums'], row['points']])
        
    output = si.getvalue()
    return current_app.response_class(output, mimetype='text/csv',
                                       headers={'Content-Disposition':f'attachment;filename=classificacao_grid_{grid_id}_season_{season_id}.csv'})

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
        
        # Invalida cache de todas as temporadas (notícias são globais)
        HomeCache.query.delete()
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
    # Invalida cache de todas as temporadas
    HomeCache.query.delete()
    db.session.commit()
    flash('Notícia removida.', 'success')
    return redirect(url_for('admin.list_news'))

# --- GESTÃO DE USUÁRIOS (ADMINS) ---

@admin_bp.route('/users')
def list_admins():
    if current_user.role != 'SUPER_ADM':
        flash('Acesso restrito ao Super Admin.', 'danger')
        return redirect(url_for('admin.dashboard'))
    admins = User.query.filter(User.role.in_(['ADM', 'SUPER_ADM', 'NARRADOR'])).order_by(User.role.desc(), User.username).all()
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

        if role not in ['ADM', 'SUPER_ADM', 'NARRADOR']:
            flash('Nível de acesso inválido.', 'danger')
            return redirect(url_for('admin.create_admin'))
        
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
    if new_role in ['ADM', 'SUPER_ADM', 'NARRADOR']:
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

        for i in range(len(names)):
            if names[i].strip():
                novo_grid = GridConfig(
                    season_id=nova.id,
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
        grid_id = request.form.get('grid_id', type=int)
        tipo_etapa = request.form.get('tipo_etapa')
        data_str = request.form.get('data')
        
        grid_cfg = db.session.get(GridConfig, grid_id)
        grid_nome = grid_cfg.nome if grid_cfg else "SEM_GRID"

        try:
            data_obj = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else None
        except ValueError:
            flash('Formato de data inválido.', 'danger')
            return redirect(url_for('admin.manage_season', season_id=season.id))
        
        nova_race = Race(season_id=season.id, nome_gp=nome_gp, pista=pista, grid=grid_nome, grid_id=grid_id, data_corrida=data_obj, tipo_etapa=tipo_etapa)
        db.session.add(nova_race)
        # Invalida cache da temporada
        HomeCache.query.filter_by(season_id=season.id).delete()
        db.session.commit()
        flash('Corrida adicionada ao calendário!', 'success')
        return redirect(url_for('admin.manage_season', season_id=season.id))
        
    # CORREÇÃO: Exibir grids configurados para esta temporada
    final_grids = GridConfig.query.filter_by(season_id=season.id).order_by(GridConfig.ordem).all()
    
    if not final_grids:
        # Fallback: busca grids das corridas se não houver config
        grids_in_season = [r[0] for r in db.session.query(Race.grid).filter_by(season_id=season.id).distinct().all()]
        final_grids = [type('HistoricalGrid', (object,), {'id': 0, 'nome': g, 'vagas': 20, 'ordem': 999, 'exibir_lastro': True})() for g in grids_in_season]

    return render_template('admin/season_detail.html', season=season, pistas=PISTAS_F1, grid_configs=final_grids)

@admin_bp.route('/season/<int:season_id>/close', methods=['POST'])
def close_season(season_id):
    if current_user.role != 'SUPER_ADM':
        flash('Apenas o Super ADM pode encerrar temporadas.', 'danger')
        return redirect(url_for('admin.seasons'))
    
    season = Season.query.get_or_404(season_id)

    pending_protests = Protesto.query.join(Race).filter(
        Race.season_id == season.id,
        Protesto.status != 'CONCLUIDO'
    ).count()
    if pending_protests:
        flash(
            f'Nao e possivel encerrar a temporada enquanto existirem {pending_protests} protesto(s) pendente(s).',
            'danger'
        )
        return redirect(url_for('admin.manage_season', season_id=season.id))

    season.ativa = False
    
    # --- HALL OF FAME SNAPSHOT (CONGELAMENTO) ---
    # Busca as configurações de grid reais da temporada para garantir o uso de IDs
    grid_configs = GridConfig.query.filter_by(season_id=season.id).all()

    upload_folder = current_app.config['UPLOAD_FOLDER']

    for g_cfg in grid_configs:
        grid_name = g_cfg.nome
        # 1. TOP 3 PILOTOS
        pilot_rows = db.session.query(
            RaceResult.pilot_id,
            func.sum(case((((RaceResult.posicao == 1) & (RaceResult.dsq == False)), 1), else_=0)).label('total_wins')
        ).join(Race).filter(
            Race.season_id == season.id,
            Race.grid_id == g_cfg.id
        ).group_by(RaceResult.pilot_id).all()

        results = []
        for row in pilot_rows:
            total_pts = ScoringService.calculate_pilot_total_points(row.pilot_id, season.id, g_cfg.id)
            results.append(type('PilotSeasonResult', (), {
                'pilot_id': row.pilot_id,
                'total_pts': total_pts,
                'total_wins': int(row.total_wins or 0),
            })())

        # Ordena e pega Top 3
        sorted_pilots = sorted(results, key=lambda x: (x.total_pts or 0, x.total_wins or 0), reverse=True)[:3]

        for i, res in enumerate(sorted_pilots):
            pilot = PilotProfile.query.get(res.pilot_id)
            # Busca a equipe do piloto específica para este grid
            team = next(
                (
                    t for t in pilot.teams
                    if t.season_id == season.id and ((t.grid_id and t.grid_id == g_cfg.id) or t.grid == grid_name)
                ),
                None
            )
            
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
                season_id=season.id, grid=grid_name, grid_id=g_cfg.id, category='PILOT', position=i+1,
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
            Race.grid_id == g_cfg.id,
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
                season_id=season.id, grid=grid_name, grid_id=g_cfg.id, category='CONSTRUCTOR', position=1,
                name=team.nome, image_url=champ_logo,
                pontos=champion_team_stats.total_pts, vitorias=champion_team_stats.total_wins
            ))
    # --------------------------------------------

    _archive_season_teams_and_unlink_pilots(season)
    _cleanup_closed_season_profile_grids(season, grid_configs)
        
    db.session.commit()
    flash(
        f'Temporada {season.nome} encerrada. Pilotos foram desvinculados do grid e das equipes desta temporada.',
        'success'
    )
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
        race.grid_id = request.form.get('grid_id', type=int)
        
        grid_cfg = db.session.get(GridConfig, race.grid_id)
        race.grid = grid_cfg.nome if grid_cfg else "SEM_GRID"
        
        race.tipo_etapa = request.form.get('tipo_etapa')
        race.status = request.form.get('status')
        
        data_str = request.form.get('data')
        if data_str:
            try:
                race.data_corrida = datetime.strptime(data_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Data inválida.', 'danger')
                return redirect(url_for('admin.edit_race', race_id=race.id))
            
        # Invalida cache da temporada
        HomeCache.query.filter_by(season_id=race.season_id).delete()
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
    
    statuses = ['Agendada', 'Concluida']
    return render_template('admin/edit_race.html', race=race, pistas=PISTAS_F1, grid_configs=final_grids, statuses=statuses)

@admin_bp.route('/race/<int:race_id>/delete', methods=['POST'])
def delete_race(race_id):
    race = Race.query.get_or_404(race_id)
    season_id = race.season_id
    
    if not race.season.ativa:
        flash('Não é possível apagar corridas de temporadas arquivadas.', 'danger')
        return redirect(url_for('admin.manage_season', season_id=season_id))
        
    RaceResult.query.filter_by(race_id=race.id).delete()
    RaceRegistration.query.filter_by(race_id=race.id).delete() # Limpa check-ins
    
    # Limpa votos antes de apagar protestos
    protestos = Protesto.query.filter_by(etapa_id=race.id).all()
    for p in protestos:
        VotoComissario.query.filter_by(protesto_id=p.id).delete()
        db.session.delete(p)
        
    db.session.delete(race)
    # Invalida cache da temporada
    HomeCache.query.filter_by(season_id=season_id).delete()
    db.session.commit()
    flash('Corrida removida.', 'success')
    return redirect(url_for('admin.manage_season', season_id=season_id))

@admin_bp.route('/race/<int:race_id>/generate_grid')
def generate_grid_text(race_id):
    race = Race.query.get_or_404(race_id)
    season = race.season
    corridas_grid = Race.query.filter_by(season_id=season.id, grid_id=race.grid_id).order_by(Race.data_corrida).all()
    
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
    grid_cfg = race.grid_config
    if grid_cfg and hasattr(grid_cfg, 'exibir_lastro') and not grid_cfg.exibir_lastro:
        usar_lastro = False

    # FIX: Busca pilotos corretamente mesmo se tiverem múltiplos grids (ex: "ELITE, ADVANCED")
    all_pilots = PilotProfile.query.join(User).all()
    
    pilotos = []
    for p in all_pilots:
        # Inclui somente se tiver equipe neste grid (ID-only)
        if any(t.grid_id == race.grid_id for t in p.teams):
            pilotos.append(p)
    
    ranking = []
    
    for p in pilotos:
        # FIX: Calcula pontos APENAS do grid_id da corrida e desconta penalidades
        resultados_grid = [r for r in p.race_results if r.race.season_id == season.id and r.race.grid_id == race.grid_id]
        
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
        try:
            RaceResultService.save_race_results(race.id, request.form)
            flash('Resultados salvos com sucesso!', 'success')
            return redirect(url_for('admin.manage_season', season_id=race.season_id))
        except ValueError as e:
            db.session.rollback()
            flash(str(e), 'danger')
            return redirect(url_for('admin.race_results', race_id=race.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Ocorreu um erro inesperado: {e}', 'danger')
            return redirect(url_for('admin.manage_season', season_id=race.season_id))

    # --- GET: Preparar dados ---
    
    # 1. Titulares: Apenas do GRID da corrida, COM EQUIPE (Inclui ADMs se tiverem equipe)
    # FIX: Filtragem exata via Python para evitar falsos positivos com nomes de grid parecidos
    # Com M2M, verificamos se o piloto tem alguma equipe associada
    all_pilots = PilotProfile.query.join(User).order_by(PilotProfile.nickname).all()
    
    titulares = [] # Será uma lista de dicionários: {'piloto': obj, 'team': obj}
    titulares_ids = set()

    for p in all_pilots:
        # Verifica se o piloto pertence ao grid via equipe (ID-only)
        has_team_in_grid = any(t.grid_id == race.grid_id for t in p.teams)
        if has_team_in_grid:
            team = next((t for t in p.teams if t.grid_id == race.grid_id), None)
            titulares.append({'piloto': p, 'team': team})
            titulares_ids.add(p.id)
    
    # 2. Reservas: QUALQUER piloto SEM EQUIPE (Inclui ADMs para correrem de reserva)
    # Reservas são aqueles que não têm equipe NO GRID DA CORRIDA (ou nenhuma equipe)
    # Mas simplificando: Qualquer um que não seja titular neste grid
    reservas_disponiveis = [p for p in all_pilots if p.id not in titulares_ids]
    
    # 3. Equipes Ativas (para selecionar onde o reserva correu)
    equipes = Team.query.filter_by(ativa=True, grid_id=race.grid_id).all()
    
    # 4. Check-ins (Carrega as respostas)
    checkins = RaceRegistration.query.filter_by(race_id=race.id).all()
    checkin_map = { r.pilot_id: r for r in checkins }
    
    # 5. Resultados já gravados (Para edição/visualização)
    resultados_existentes = RaceResult.query.filter_by(race_id=race.id).all()
    results_map = { r.pilot_id: r for r in resultados_existentes }
    
    # Identificar reservas que correram (não são titulares do grid)
    titulares_ids = [t['piloto'].id for t in titulares]
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

    # Carrega grids configurados (todas as temporadas) para obter o mapeamento ID -> Nome
    configs = GridConfig.query.order_by(GridConfig.season_id, GridConfig.ordem).all()
    id_to_name = {str(c.id): c.nome for c in configs}

    # Abas na ordem das configs + especiais no final
    base_tabs = [c.nome for c in configs]
    specials = ['RESERVA', 'SEM_GRID']
    grid_tabs = []
    # Evita duplicatas mantendo ordem de aparição das configs
    for name in base_tabs:
        if name not in grid_tabs:
            grid_tabs.append(name)
    for sp in specials:
        if sp not in grid_tabs:
            grid_tabs.append(sp)

    # Organiza pilotos por NOME de grid (um piloto pode aparecer em vários)
    pilots_by_grid = {name: [] for name in grid_tabs}

    for p in pilots:
        tokens = [x.strip() for x in (p.grid or '').split(',') if x.strip()]
        if not tokens:
            pilots_by_grid.setdefault('SEM_GRID', []).append(p)
            continue
        for t in tokens:
            gname = None
            if t.isdigit() and t in id_to_name:
                gname = id_to_name[t]
            elif t in specials:
                gname = t
            # Ignora tokens legados não mapeados
            if not gname:
                continue
            if gname not in pilots_by_grid:
                pilots_by_grid[gname] = []
            pilots_by_grid[gname].append(p)

    def get_grid_names_helper(grid_str):
        if not grid_str or grid_str == 'SEM_GRID':
            return 'SEM_GRID'
        names = []
        for tid in [x.strip() for x in grid_str.split(',') if x.strip()]:
            names.append(id_to_name.get(tid, tid))
        return ", ".join(names)

    return render_template('admin/pilots.html', 
                           pilots_by_grid=pilots_by_grid,
                           total_count=len(pilots),
                           all_pilots=pilots,
                           grid_tabs=grid_tabs,
                           get_grid_names=get_grid_names_helper)

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
        
        # NOVO: PilotProfile.grid passa a armazenar APENAS IDs numéricos de grids (ex.: "1,2").
        # O formulário envia IDs; salvamos somente IDs (sem nomes) para suportar a Home pilot-centric por ID.
        grid_ids_selecionados = request.form.getlist('grids')
        ids_limpos = []
        if grid_ids_selecionados:
            for val in grid_ids_selecionados:
                val_clean = val.strip()
                if val_clean:
                    # Aceita IDs numéricos E tokens especiais (ex: 'RESERVA')
                    if val_clean.isdigit():
                        ids_limpos.append(str(int(val_clean)))
                    else:
                        ids_limpos.append(val_clean)
        pilot.grid = ",".join(sorted(set(ids_limpos))) if ids_limpos else 'SEM_GRID'
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
        
        # --- GESTÃO DE NÍVEL DE ACESSO (PROMOÇÃO/REBAIXAMENTO) ---
        # Apenas Super Admin pode alterar o papel do usuário
        if current_user.role == 'SUPER_ADM':
            new_role = request.form.get('role')
            if new_role and new_role in ['PILOTO', 'ADM', 'SUPER_ADM', 'NARRADOR']:
                # Impede que o Super Admin rebaixe a si mesmo para evitar bloqueio acidental
                if pilot.user.id != current_user.id:
                    pilot.user.role = new_role
                elif new_role != 'SUPER_ADM':
                    flash('Você não pode alterar seu próprio nível de acesso.', 'warning')
        
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
        # Upload de nova foto específica (baseado em ID)
        grid_photo_target_id = request.form.get('grid_photo_target', type=int)

        if grid_photo_target_id and 'grid_photo_file' in request.files:
            g_file = request.files['grid_photo_file']
            if g_file and g_file.filename != '' and allowed_file(g_file.filename):
                # Busca e substitui a foto anterior para este grid_id
                old_gp = PilotGridPhoto.query.filter_by(pilot_id=pilot.id, grid_id=grid_photo_target_id).first()
                if old_gp:
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], old_gp.foto_url)
                    if os.path.exists(old_path): os.remove(old_path)
                    db.session.delete(old_gp)
                
                ext = g_file.filename.rsplit('.', 1)[1].lower()
                timestamp = int(datetime.utcnow().timestamp())

                # Usa o nome do grid para um nome de arquivo mais descritivo
                grid_cfg = db.session.get(GridConfig, grid_photo_target_id)
                grid_name_for_file = grid_cfg.nome.replace(" ", "_") if grid_cfg else f"grid_{grid_photo_target_id}"

                nome_gp = f"piloto_{pilot.id}_{grid_name_for_file}_{timestamp}.{ext}"
                g_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], nome_gp))
                
                # Salva a nova foto com o grid_id
                new_gp = PilotGridPhoto(pilot_id=pilot.id, grid_id=grid_photo_target_id, foto_url=nome_gp)
                db.session.add(new_gp)

        # Exclusão de foto específica
        delete_gp_id = request.form.get('delete_grid_photo_id')
        if delete_gp_id:
            gp_to_del = PilotGridPhoto.query.get(delete_gp_id)
            if gp_to_del and gp_to_del.pilot_id == pilot.id:
                path = os.path.join(current_app.config['UPLOAD_FOLDER'], gp_to_del.foto_url)
                if os.path.exists(path): os.remove(path)
                db.session.delete(gp_to_del)
                
        # Invalida todos os caches (mudança de piloto afeta rankings de várias temporadas)
        HomeCache.query.delete()
        db.session.commit()
        flash('Perfil atualizado com sucesso.', 'success')
        return redirect(url_for('admin.list_pilots'))
        
    # Busca todas as configurações de grid das temporadas ativas para seleção
    active_seasons = Season.query.filter_by(ativa=True).all()
    active_ids = [s.id for s in active_seasons]
    
    # Lista de objetos GridConfig para o template usar IDs no value do checkbox
    grid_configs_options = GridConfig.query.filter(GridConfig.season_id.in_(active_ids)).order_by(GridConfig.season_id, GridConfig.ordem).all()
    special_options = [{'id': 'RESERVA', 'nome': 'RESERVA'}, {'id': 'SEM_GRID', 'nome': 'SEM_GRID'}]

    # Busca histórico de punições para exibir no admin
    historico_punicoes = Protesto.query.filter(
        Protesto.acusado_id == pilot.id, 
        Protesto.status == 'CONCLUIDO'
    ).order_by(Protesto.data_fechamento.desc()).all()

    return render_template('admin/edit_pilot.html', pilot=pilot, grid_configs_options=grid_configs_options, special_options=special_options, historico=historico_punicoes)

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
    # FIX: Buscar TODAS as temporadas para permitir gestão de histórico e evitar tela vazia
    all_seasons = Season.query.order_by(Season.id.desc()).all()
    selected_season_id = request.args.get('s', type=int)
    
    season_ativa = None
    if selected_season_id:
        season_ativa = next((s for s in all_seasons if s.id == selected_season_id), None)
    
    if not season_ativa:
        # Tenta a mais recente ativa, senão a mais recente de todas
        season_ativa = next((s for s in all_seasons if s.ativa), None)
        if not season_ativa and all_seasons:
            season_ativa = all_seasons[0]

    # 2. Busca equipes da temporada
    teams = []
    if season_ativa:
        teams = Team.query.filter_by(season_id=season_ativa.id).order_by(Team.ativa.desc(), Team.nome).all()
        # Fallback para órfãs apenas na temporada mais recente
        if not teams and all_seasons and season_ativa.id == all_seasons[0].id:
            teams = Team.query.filter(Team.season_id == None).order_by(Team.ativa.desc(), Team.nome).all()

    # 3. Busca grids (Abas) - Prioridade total para GridConfig da temporada
    grid_configs = []
    if season_ativa:
        grid_configs = GridConfig.query.filter_by(season_id=season_ativa.id).order_by(GridConfig.ordem).all()

    # Se não houver configs, criamos objetos temporários para manter compatibilidade com o template
    if not grid_configs:
        # Fallback para manter o sistema funcional caso não existam GridConfigs
        unique_grids = sorted(list(set([t.grid.upper() for t in teams if t.grid])))
        for i, g_name in enumerate(unique_grids or ['ELITE', 'ADVANCED', 'INITIAL']):
            grid_configs.append(type('TempGrid', (object,), {'id': 0, 'nome': g_name, 'ordem': i})())

    return render_template('admin/teams.html', teams=teams, grid_configs=grid_configs, season_ativa=season_ativa, all_seasons=all_seasons)

@admin_bp.route('/teams/new', methods=['GET', 'POST'])
def create_team():
    # Captura o ID da temporada da URL (para saber onde criar a equipe)
    season_id = request.args.get('season_id', type=int)

    if request.method == 'POST':
        nome = request.form.get('nome')
        grid_id = request.form.get('grid_id', type=int)
        season_id = request.form.get('season_id', type=int) # Captura do formulário
        
        grid_cfg = db.session.get(GridConfig, grid_id)
        grid_nome = grid_cfg.nome if grid_cfg else "SEM_GRID"
        
        nova_equipe = Team(nome=nome[:50], grid=grid_nome, grid_id=grid_id, season_id=season_id, ativa=True)
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
        
    grid_configs = GridConfig.query.filter_by(season_id=season_id).order_by(GridConfig.ordem).all() if season_id else []
    return render_template('admin/create_team.html', grid_configs=grid_configs, season_id=season_id)

@admin_bp.route('/teams/edit/<int:team_id>', methods=['GET', 'POST'])
def edit_team(team_id):
    team = Team.query.get_or_404(team_id)
    if request.method == 'POST':
        team.nome = request.form.get('nome')
        team.grid_id = request.form.get('grid_id', type=int)
        
        grid_cfg = db.session.get(GridConfig, team.grid_id)
        team.grid = grid_cfg.nome if grid_cfg else "SEM_GRID"
        
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

        same_grid_teams = Team.query.filter(
            Team.season_id == team.season_id,
            Team.grid_id == team.grid_id,
            Team.id != team.id
        ).all()

        def unlink_from_other_teams(pilot_obj):
            """Garante unicidade do piloto por grid/temporada (titular ou reserva)."""
            if not pilot_obj:
                return
            for other in same_grid_teams:
                if any(pp.id == pilot_obj.id for pp in other.pilots):
                    other.pilots.remove(pilot_obj)
                if any(pp.id == pilot_obj.id for pp in other.reserves):
                    other.reserves.remove(pilot_obj)
            
        pilot1_id = request.form.get('pilot1')
        pilot2_id = request.form.get('pilot2')
        titulares_ids = set()
        
        if pilot1_id:
            p1 = PilotProfile.query.get(pilot1_id)
            if p1 and p1.id not in titulares_ids:
                unlink_from_other_teams(p1)
                team.pilots.append(p1)
                titulares_ids.add(p1.id)
        if pilot2_id:
            p2 = PilotProfile.query.get(pilot2_id)
            if p2 and p2.id not in titulares_ids:
                unlink_from_other_teams(p2)
                team.pilots.append(p2)
                titulares_ids.add(p2.id)
            
        reserve1_id = request.form.get('reserve_pilot_1')
        reservas_ids = set()
        if reserve1_id:
            r1 = PilotProfile.query.get(reserve1_id)
            if r1 and r1.id not in titulares_ids and r1.id not in reservas_ids:
                unlink_from_other_teams(r1)
                team.reserves.append(r1)
                reservas_ids.add(r1.id)
            
        reserve2_id = request.form.get('reserve_pilot_2')
        if reserve2_id:
            r2 = PilotProfile.query.get(reserve2_id)
            if r2 and r2.id not in titulares_ids and r2.id not in reservas_ids:
                unlink_from_other_teams(r2)
                team.reserves.append(r2)
                reservas_ids.add(r2.id)
            
        reserve3_id = request.form.get('reserve_pilot_3')
        if reserve3_id:
            r3 = PilotProfile.query.get(reserve3_id)
            if r3 and r3.id not in titulares_ids and r3.id not in reservas_ids:
                unlink_from_other_teams(r3)
                team.reserves.append(r3)
                reservas_ids.add(r3.id)
            
        reserve4_id = request.form.get('reserve_pilot_4')
        if reserve4_id:
            r4 = PilotProfile.query.get(reserve4_id)
            if r4 and r4.id not in titulares_ids and r4.id not in reservas_ids:
                unlink_from_other_teams(r4)
                team.reserves.append(r4)
                reservas_ids.add(r4.id)
            
        try:
            validate_unique_membership_per_grid(team)
        except ValueError as e:
            db.session.rollback()
            flash(str(e), 'danger')
            return redirect(url_for('admin.edit_team', team_id=team.id))

        # Invalida cache da temporada
        HomeCache.query.filter_by(season_id=team.season_id).delete()
        db.session.commit()
        flash('Equipe atualizada!', 'success')
        return redirect(url_for('admin.list_teams'))

    # LÓGICA: Apenas pilotos que já pertencem ao MESMO GRID da equipe aparecem aqui (incluindo ADMs).
    # E que não estejam em outra equipe DO MESMO GRID
    all_pilots = PilotProfile.query.join(User).order_by(PilotProfile.nickname).all()
    
    # Filtra pilotos elegíveis por ID do grid: não vinculados a outra equipe do mesmo grid nesta temporada
    final_pilots = []
    for p in all_pilots:
        if team.grid_id:
            team_in_grid = next((t for t in p.teams if t.grid_id == team.grid_id and t.season_id == team.season_id), None)
            is_reserve_here = next((t for t in p.reserve_teams if t.grid_id == team.grid_id and t.id == team.id), None)
            if (team_in_grid is None or team_in_grid.id == team.id) or is_reserve_here:
                final_pilots.append(p)

    grid_configs = GridConfig.query.filter_by(season_id=team.season_id).order_by(GridConfig.ordem).all() if team.season_id else []
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
        
        # Invalida cache da temporada
        HomeCache.query.filter_by(season_id=team.season_id).delete()
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
            
            existing = GridConfig.query.filter_by(season_id=None, nome=nome).first()
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
            entry = SeletivaService.register_time(pilot_id, tempo_input)
            flash(f'Tempo de {entry.piloto.nickname} registrado: {tempo_input}', 'success')
            
        except Exception as e:
            flash('Formato de tempo inválido. Use o formato 1:35.800', 'danger')
            
        return redirect(url_for('admin.seletiva'))

    # LÓGICA: Agora aparecem TODOS os pilotos, pois podem participar de múltiplos grids
    pilotos = PilotProfile.query.order_by(PilotProfile.nickname).all()
    entradas = SeletivaEntry.query.order_by(SeletivaEntry.tempo_ms.asc()).all()
    grid_configs = GridConfig.query.filter_by(season_id=None).order_by(GridConfig.ordem).all()
    
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

    count = SeletivaService.close_seletiva(season_name)
    
    flash(f'Temporada "{season_name}" criada e {count} pilotos alocados com sucesso!', 'success')
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


def _resolve_protest_verdict(form_data):
    """Aceita nomes antigos e novos dos campos do formulário."""
    verdict = (form_data.get('veredito_final') or form_data.get('veredito') or '').strip().upper()
    valid_verdicts = {'INOCENTE', 'INCIDENTE_CORRIDA', 'ADVERTENCIA', 'LEVE', 'MEDIA', 'GRAVE'}
    return verdict if verdict in valid_verdicts else None


def _resolve_reopened_protest_status(protesto):
    """Ao reabrir, volta para votação se já existir defesa; senão, aguarda defesa."""
    has_defense = bool((protesto.argumento_defesa or '').strip() or (protesto.video_defesa or '').strip())
    return 'EM_VOTACAO' if has_defense else 'AGUARDANDO_DEFESA'

@admin_bp.route('/protests/<int:protest_id>', methods=['GET', 'POST'])
def view_protest(protest_id):
    protesto = db.session.get(Protesto, protest_id) or abort(404)
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
                flash('Conflito de interesse: Você é parte envolvida neste protesto.', 'danger')
                return redirect(url_for('admin.view_protest', protest_id=protesto.id))

            escolha = request.form.get('voto')
            if escolha:
                if meu_voto:
                    meu_voto.escolha = escolha
                else:
                    novo_voto = VotoComissario(protesto_id=protesto.id, admin_id=current_user.id, escolha=escolha)
                    db.session.add(novo_voto)
                db.session.commit()
                flash('Voto registrado.', 'success')
            return redirect(url_for('admin.view_protest', protest_id=protesto.id))

        if ('fechar' in request.form or 'encerrar' in request.form) and current_user.role == 'SUPER_ADM':
            verdict = _resolve_protest_verdict(request.form)
            justificativa = (request.form.get('justificativa') or '').strip()

            if not verdict:
                flash('Selecione um veredito válido para encerrar o protesto.', 'danger')
                return redirect(url_for('admin.view_protest', protest_id=protesto.id))
            if not justificativa:
                flash('A justificativa oficial é obrigatória para encerrar o protesto.', 'danger')
                return redirect(url_for('admin.view_protest', protest_id=protesto.id))

            protesto.veredito_final = verdict
            protesto.justificativa_texto = justificativa
            protesto.status = 'CONCLUIDO'
            protesto.data_fechamento = datetime.utcnow()
            HomeCache.query.filter_by(season_id=protesto.etapa.season_id).delete()
            db.session.commit()
            flash('Protesto encerrado com sucesso.', 'success')
            return redirect(url_for('admin.protests'))

        if 'reabrir' in request.form and current_user.role == 'SUPER_ADM':
            protesto.status = _resolve_reopened_protest_status(protesto)
            protesto.veredito_final = None
            protesto.justificativa_texto = None
            protesto.data_fechamento = None
            HomeCache.query.filter_by(season_id=protesto.etapa.season_id).delete()
            db.session.commit()
            flash('Protesto reaberto com sucesso. Penalidades estornadas dinamicamente.', 'warning')
            return redirect(url_for('admin.view_protest', protest_id=protesto.id))

    return render_template('admin/view_protest.html', protesto=protesto, meu_voto=meu_voto, votos_resumo=votos_resumo, embed_acusacao=embed_acusacao, embed_defesa=embed_defesa)

@admin_bp.route('/protests/<int:protest_id>/delete', methods=['POST'])
def delete_protest_admin(protest_id):
    if current_user.role != 'SUPER_ADM':
        flash('Apenas o Super Admin pode apagar protestos.', 'danger')
        return redirect(url_for('admin.protests'))

    protesto = db.session.get(Protesto, protest_id) or abort(404)
    VotoComissario.query.filter_by(protesto_id=protesto.id).delete()
    db.session.delete(protesto)
    HomeCache.query.delete()
    db.session.commit()
    flash('Protesto apagado com sucesso.', 'success')
    return redirect(url_for('admin.protests'))
