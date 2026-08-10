import os
import secrets
import shutil
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, abort, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, case
from app.models import db, User, PilotProfile, Season, Race, RaceResult, Invite, Protesto, VotoComissario, Team, RaceRegistration, SeletivaEntry, News, GridConfig, SeasonChampion, PilotGridPhoto, HomeCache, AccessLog
from app.utils import allowed_file, get_embed_url, PONTUACAO_20, PONTUACAO_22, ORDEM_CARROS, calcular_perda, get_grid_name, find_grid_config, grid_matches, DDI_OPTIONS, format_international_phone, parse_phone_components
from app.services.scoring_service import ScoringService
from app.services.diagnostics import build_data_health_report
from app.services.seletiva_service import SeletivaService
from app.services.race_result_service import RaceResultService
from app.services.stats_service import StatsService
from app.services.domain_rules import validate_unique_membership_per_grid
from app.services.team_context import build_team_context
from app.services.simhub_service import SimHubService

admin_bp = Blueprint('admin', __name__)


def _get_season_context():
    """
    Determina a temporada de contexto com base no request.
    Retorna (temporada_selecionada, todas_as_temporadas_ativas).
    """
    all_active_seasons = Season.query.filter_by(ativa=True).order_by(Season.id.desc()).all()

    selected_season_id = request.args.get('s', type=int)
    season_ativa = None
    if selected_season_id:
        season_ativa = next((s for s in all_active_seasons if s.id == selected_season_id), None)

    if not season_ativa and all_active_seasons:
        season_ativa = all_active_seasons[0]

    return season_ativa, all_active_seasons


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
    {"nome": "Circuito Internacional de Xangai", "gp": "GP da China", "tipo_etapa": "SPRINT"},
    {"nome": "Autódromo Internacional de Miami", "gp": "GP de Miami", "tipo_etapa": "SPRINT"},
    {"nome": "Autódromo Enzo e Dino Ferrari - Imola", "gp": "GP da Emilia-Romagna"},
    {"nome": "Circuito de Mônaco", "gp": "GP de Mônaco"},
    {"nome": "Circuito de Barcelona-Catalunha", "gp": "GP da Espanha"},
    {"nome": "Circuito de Madrid (IFEMA)", "gp": "GP de Madrid"},
    {"nome": "Circuito Gilles Villeneuve", "gp": "GP do Canadá"},
    {"nome": "Red Bull Ring", "gp": "GP da Áustria"},
    {"nome": "Circuito de Silverstone", "gp": "GP da Grã-Bretanha"},
    {"nome": "Hungaroring", "gp": "GP da Hungria"},
    {"nome": "Circuito de Spa-Francorchamps", "gp": "GP da Bélgica", "tipo_etapa": "SPRINT"},
    {"nome": "Circuito de Zandvoort", "gp": "GP da Holanda"},
    {"nome": "Autódromo Nacional de Monza", "gp": "GP da Itália"},
    {"nome": "Circuito Urbano de Baku", "gp": "GP do Azerbaijão"},
    {"nome": "Circuito de Marina Bay", "gp": "GP de Singapura"},
    {"nome": "Circuito das Américas (COTA) - Áustin", "gp": "GP dos Estados Unidos", "tipo_etapa": "SPRINT"},
    {"nome": "Autódromo Hermanos Rodríguez", "gp": "GP da Cidade do México"},
    {"nome": "Autódromo José Carlos Pace", "gp": "GP de São Paulo", "tipo_etapa": "SPRINT"},
    {"nome": "Las Vegas Strip Circuit", "gp": "GP de Las Vegas"},
    {"nome": "Circuito Internacional de Lusail", "gp": "GP do Catar", "tipo_etapa": "SPRINT"},
    {"nome": "Circuito de Yas Marina", "gp": "GP de Abu Dhabi"},
    {"nome": "Autódromo Internacional do Algarve", "gp": "GP de Portugal"},
    {"nome": "Circuito Paul Ricard", "gp": "GP da França"}
]

@admin_bp.before_request
@login_required
def restrict_access():
    # Permite que acusados e acusadores vejam seu próprio protesto via admin.view_protest
    if request.endpoint == 'admin.view_protest':
        protest_id = request.view_args.get('protest_id') if request.view_args else None
        if protest_id:
            p = db.session.get(Protesto, protest_id)
            if p and current_user.pilot_profile and (current_user.pilot_profile.id in [p.acusado_id, p.acusador_id]):
                return # Acesso concedido para ver o próprio protesto!

    # 1. Permite acesso geral para ADMs, Narradores e Comissários
    if current_user.role not in ['SUPER_ADM', 'ADM', 'NARRADOR', 'COMISSARIO']:
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
            'analytics',
        ]

        if endpoint_name not in allowed_endpoints:
            flash('Narradores têm acesso apenas à tela de Overview e Estatísticas.', 'warning')
            # O ponto de entrada seguro para o narrador é a overview.
            return redirect(url_for('admin.overview'))

    # 3. Restrições específicas para Comissário (Visão Geral, Analytics, Histórico e Tribunal)
    if current_user.role == 'COMISSARIO':
        endpoint_name = request.endpoint.split('.')[-1]

        # Whitelist de endpoints permitidos para o Comissário
        allowed_endpoints = [
            'dashboard',
            'overview',
            'pilot_stats',
            'pilot_career_stats',
            'analytics',
            'historic',
            'protests',
            'view_protest',
        ]

        if endpoint_name not in allowed_endpoints:
            flash('Comissários têm acesso apenas aos cards Visão Geral, Analytics, Histórico e Tribunal.', 'warning')
            return redirect(url_for('admin.dashboard'))

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

def _get_checkin_stats_for_race(race, grid_pilots_count):
    """Calcula e retorna as estatísticas de check-in para uma corrida."""
    if not race:
        return {'confirmed': 0, 'absent': 0, 'pending': 0}

    regs = RaceRegistration.query.filter_by(race_id=race.id).all()
    confirmed = sum(1 for r in regs if r.status == 'CONFIRMADO')
    absent = sum(1 for r in regs if r.status in ['AUSENTE', 'JUSTIFICADO'])
    
    # Correção: Pendentes são o total de pilotos do grid menos os que já responderam.
    responded_count = len(regs)
    pending = max(0, grid_pilots_count - responded_count)

    return {'confirmed': confirmed, 'absent': absent, 'pending': pending}


@admin_bp.route('/dashboard')
def dashboard():
    season_ativa, all_active_seasons = _get_season_context()
    return render_template(
        'admin/dashboard.html',
        season_ativa=season_ativa, all_active_seasons=all_active_seasons
    )


@admin_bp.route('/analytics')
def analytics():
    if current_user.role not in ['SUPER_ADM', 'ADM']:
        flash('Acesso negado. Área exclusiva para Administradores.', 'danger')
        return redirect(url_for('admin.dashboard'))

    season_ativa, all_active_seasons = _get_season_context()

    try:
        hoje = datetime.utcnow().date()
        inicio_dia = datetime.combine(hoje, datetime.min.time())
        
        total_hoje = AccessLog.query.filter(AccessLog.timestamp >= inicio_dia).count()
        app_hoje = AccessLog.query.filter(AccessLog.timestamp >= inicio_dia, AccessLog.platform == 'APP').count()
        web_hoje = AccessLog.query.filter(AccessLog.timestamp >= inicio_dia, AccessLog.platform == 'WEB').count()

        pct_app = round((app_hoje / total_hoje * 100), 1) if total_hoje > 0 else 0
        pct_web = round((web_hoje / total_hoje * 100), 1) if total_hoje > 0 else 0

        unicos_hoje = db.session.query(func.count(db.distinct(AccessLog.user_id))).filter(
            AccessLog.timestamp >= inicio_dia, AccessLog.user_id.isnot(None)
        ).scalar() or 0

        trinta_dias_atras = inicio_dia - timedelta(days=30)
        logs_30 = AccessLog.query.filter(AccessLog.timestamp >= trinta_dias_atras).all()
        
        dias_map = {}
        for i in range(30, -1, -1):
            dt_key = (hoje - timedelta(days=i)).strftime('%d/%m')
            dias_map[dt_key] = {'APP': 0, 'WEB': 0}

        for log in logs_30:
            dt_str = log.timestamp.strftime('%d/%m')
            if dt_str in dias_map:
                plat = 'APP' if log.platform == 'APP' else 'WEB'
                dias_map[dt_str][plat] += 1

        chart_labels = list(dias_map.keys())
        chart_app_data = [dias_map[k]['APP'] for k in chart_labels]
        chart_web_data = [dias_map[k]['WEB'] for k in chart_labels]

        rotas_populares = db.session.query(
            AccessLog.route,
            AccessLog.platform,
            func.count(AccessLog.id).label('total')
        ).group_by(AccessLog.route, AccessLog.platform).order_by(func.count(AccessLog.id).desc()).limit(10).all()

        logs_recentes = AccessLog.query.order_by(AccessLog.timestamp.desc()).limit(20).all()
    except Exception as e:
        print(f"Erro em analytics: {e}")
        db.session.rollback()
        total_hoje = app_hoje = web_hoje = pct_app = pct_web = unicos_hoje = 0
        chart_labels, chart_app_data, chart_web_data = [], [], []
        rotas_populares, logs_recentes = [], []

    return render_template(
        'admin/analytics.html',
        total_hoje=total_hoje,
        app_hoje=app_hoje,
        web_hoje=web_hoje,
        pct_app=pct_app,
        pct_web=pct_web,
        unicos_hoje=unicos_hoje,
        chart_labels=chart_labels,
        chart_app_data=chart_app_data,
        chart_web_data=chart_web_data,
        rotas_populares=rotas_populares,
        logs_recentes=logs_recentes,
        season_ativa=season_ativa,
        all_active_seasons=all_active_seasons
    )


@admin_bp.route('/data-health')
def data_health():
    all_seasons = Season.query.filter_by(ativa=True).order_by(Season.id.desc()).all()
    selected_season_id = request.args.get('s', type=int)
    season_ativa = None
    if selected_season_id:
        season_ativa = next((s for s in all_seasons if s.id == selected_season_id), None)
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
    season_ativa, all_active_seasons = _get_season_context()
    
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

        # Build team context and calculate constructors points once
        team_ctx = build_team_context(season_ativa.id)
        raw_constructors = ScoringService.build_constructors_for_home(
            season_ativa.id, grid_configs, team_ctx["canonical_teams"], team_ctx["alias_ids_by_key"]
        )

        pilotos = PilotProfile.query.join(User).all()
        all_season_teams = Team.query.filter_by(season_id=season_ativa.id).all()
        
        for p in pilotos:
            resultados_season = [r for r in p.race_results if r.race.season_id == season_ativa.id]
            grids_participados_ids = set()

            # Estas listas são usadas posteriormente para determinar se o piloto é titular ou reserva
            teams_season = [t for t in all_season_teams if any(pilot.id == p.id for pilot in t.pilots)]
            reserves_season = [t for t in all_season_teams if any(pilot.id == p.id for pilot in t.reserves)]

            # Fonte única de verdade para a participação de um piloto em um grid:
            # O campo 'grid' no perfil do piloto, que contém os IDs dos grids atribuídos.
            if p.grid and p.grid != 'SEM_GRID':
                grid_tokens = [token.strip() for token in p.grid.split(',') if token.strip().isdigit()]
                grids_participados_ids.update(int(token) for token in grid_tokens)

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
            total_pilotos_no_grid = dados_grids[g_id]['stats']['total_pilotos']
            dados_grids[g_id]['checkin'] = _get_checkin_stats_for_race(
                next_race, total_pilotos_no_grid
            )
            
            # constructors standings
            constructors_data = raw_constructors.get(g_id, [])
            adapted_constructors = []
            for item in constructors_data:
                adapted_constructors.append({
                    'team': item['equipe'],
                    'points': item['pontos'],
                })
            dados_grids[g_id]['constructors'] = adapted_constructors
            
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

@admin_bp.route('/historic')
@login_required
def historic():

    def parse_time_str(time_str):
        if not time_str:
            return float('inf')
        s = time_str.strip()
        if not s:
            return float('inf')
        try:
            if ':' in s:
                parts = s.split(':')
                if len(parts) == 2:
                    return float(parts[0]) * 60 + float(parts[1])
                elif len(parts) == 3:
                    return float(parts[0]) * 60 + float(parts[1]) + float(parts[2]) / 1000.0
            return float(s)
        except Exception:
            return float('inf')
    """
    Lê todas as corridas com resultados, agrupa por circuito e calcula
    estatísticas por pista (vencedor mais frequente, total de corridas, etc.).
    """
    corridas_com_resultados = Race.query.join(RaceResult).distinct().order_by(
        Race.pista.asc(), Race.data_corrida.desc()
    ).all()

    historico_por_circuito = {}

    for race in corridas_com_resultados:
        resultados = RaceResult.query.filter_by(race_id=race.id).all()

        # Conta apenas pilotos que efetivamente participaram (têm posição > 0, DNF ou DSQ) e não estão marcados como ausentes.
        total_participantes = sum(1 for r in resultados if r.status_presenca == 'OK' and (r.posicao > 0 or r.dnf or r.dsq))

        primeiro     = next((r.pilot for r in resultados if r.posicao == 1 and not r.dsq), None)
        segundo      = next((r.pilot for r in resultados if r.posicao == 2 and not r.dsq), None)
        terceiro     = next((r.pilot for r in resultados if r.posicao == 3 and not r.dsq), None)
        piloto_dia   = next((r.pilot for r in resultados if r.piloto_do_dia), None)
        volta_rapida = next((r.pilot for r in resultados if r.volta_rapida), None)

        dados_corrida = {
            'nome_gp':       race.nome_gp,
            'data':          race.data_corrida,
            'season_name':   race.season.nome,
            'grid_name':     race.grid_config.nome if race.grid_config else race.grid,
            'pole_sitter':   race.pole_sitter,
            'pole_time':     race.pole_time,
            'primeiro':      primeiro,
            'segundo':       segundo,
            'terceiro':      terceiro,
            'volta_rapida':  volta_rapida,
            'piloto_do_dia': piloto_dia,
            'race_id':       race.id,
            'total_pilotos': total_participantes,
            'tipo_etapa':    race.tipo_etapa,
        }

        circuito = race.pista
        if circuito not in historico_por_circuito:
            historico_por_circuito[circuito] = {'corridas': [], 'stats': {}}
        historico_por_circuito[circuito]['corridas'].append(dados_corrida)

    # Calcula estatísticas por circuito
    for circuito, dados in historico_por_circuito.items():
        
        record_pilot = None
        record_time = None
        min_seconds = float('inf')
        corridas = dados['corridas']
        vitorias, poles = {}, {}
        for c in corridas:
            if c['primeiro']:
                nick = c['primeiro'].nickname
                vitorias[nick] = vitorias.get(nick, 0) + 1
            if c['pole_sitter']:
                nick = c['pole_sitter'].nickname
                poles[nick] = poles.get(nick, 0) + 1
                
                if c['pole_time']:
                    t_sec = parse_time_str(c['pole_time'])
                    if t_sec < min_seconds:
                        min_seconds = t_sec
                        record_pilot = nick
                        record_time = c['pole_time']

        maior_vencedor = max(vitorias, key=vitorias.get) if vitorias else None
        maior_pole     = max(poles,    key=poles.get)    if poles    else None

        dados['stats'] = {
            'total_corridas':  len(corridas),
            'maior_vencedor':  maior_vencedor,
            'vitorias_lider':  vitorias.get(maior_vencedor, 0) if maior_vencedor else 0,
            'maior_pole':      maior_pole,
            'poles_lider':     poles.get(maior_pole, 0) if maior_pole else 0,
            'record_pilot':    record_pilot,
            'record_time':     record_time,
            'ultima_data':     corridas[0]['data'],
        }

    total_corridas_geral = sum(d['stats']['total_corridas'] for d in historico_por_circuito.values())

    return render_template(
        'admin/historic.html',
        historico=historico_por_circuito,
        total_circuitos=len(historico_por_circuito),
        total_corridas_geral=total_corridas_geral,
    )

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
    admins = User.query.filter(User.role.in_(['ADM', 'SUPER_ADM', 'NARRADOR', 'COMISSARIO'])).order_by(User.role.desc(), User.username).all()
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

        if role not in ['ADM', 'SUPER_ADM', 'NARRADOR', 'COMISSARIO']:
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
    if new_role in ['PILOTO', 'ADM', 'SUPER_ADM', 'NARRADOR', 'COMISSARIO']:
        user.role = new_role
        db.session.commit()
        if new_role == 'PILOTO':
            flash(f'O usuário {user.username} foi rebaixado para PILOTO comum e teve seu acesso ADM removido.', 'info')
        else:
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
        if profile.foto_url and profile.foto_url != '../img/NP.jpg':
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
            if profile.foto_url and profile.foto_url != '../img/NP.jpg':
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
        # Captura o nome da temporada e prepara as listas de grids
        nome = request.form.get('nome')
        names = request.form.getlist('grid_name[]')
        vagas = request.form.getlist('grid_vagas[]')
        ordens = request.form.getlist('grid_ordem[]')
        lastros = request.form.getlist('grid_lastro[]') # Vem como "1" ou "0"

        # Validação: Pelo menos um grid deve ser informado
        if not any(name.strip() for name in names):
            flash('É obrigatório informar pelo menos um grid para criar a temporada.', 'danger')
            return redirect(url_for('admin.create_season'))

        # Cria a temporada apenas se a validação passar
        nova = Season(nome=nome, ativa=True, data_inicio=datetime.utcnow().date())
        db.session.add(nova)
        db.session.flush() # NECESSÁRIO: Gera o nova.id antes de vincular os grids
        # Processa os Grids Dinâmicos

        for i in range(len(names)):
            if names[i].strip():
                # Tratamento seguro para conversão de valores, previne erro 500 se o campo vier vazio
                try:
                    vagas_val = int(vagas[i]) if i < len(vagas) and vagas[i].strip() else 20
                except ValueError:
                    vagas_val = 20
                    
                try:
                    ordem_val = int(ordens[i]) if i < len(ordens) and ordens[i].strip() else (i + 1)
                except ValueError:
                    ordem_val = i + 1
                    
                lastro_val = (lastros[i] == '1') if i < len(lastros) else True
                
                novo_grid = GridConfig(
                    season_id=nova.id,
                    nome=names[i].strip(),
                    vagas=vagas_val,
                    ordem=ordem_val,
                    exibir_lastro=lastro_val
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
                except (OSError, FileNotFoundError) as e:
                    print(f"WARN: Falha ao copiar foto do campeao {pilot.nickname}: {e}")
                    champ_img = None # Falha na cópia, fica sem foto

            db.session.add(SeasonChampion(
                season_id=season.id, grid=grid_name, grid_id=g_cfg.id, category='PILOT', position=i+1,
                name=pilot.nickname, team_name=team.nome if team else 'Sem Equipe',
                image_url=champ_img, team_logo_url=team.logo_url if team else None,
                pontos=res.total_pts, vitorias=res.total_wins
            ))

        # 2. CAMPEÕES DE CONSTRUTORES (TOP 3)
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
            sorted_teams = sorted(team_results, key=lambda x: (x.total_pts or 0, x.total_wins or 0), reverse=True)[:3]
            for j, t_stats in enumerate(sorted_teams):
                team = Team.query.get(t_stats.team_id)
                if not team:
                    continue
                
                # Copia logo da equipe
                champ_logo = None
                if team.logo_url:
                    ext = team.logo_url.split('.')[-1]
                    champ_logo = f"champ_team_{season.id}_{grid_name}_{j+1}_{secrets.token_hex(4)}.{ext}"
                    try:
                        shutil.copy(os.path.join(upload_folder, team.logo_url), os.path.join(upload_folder, champ_logo))
                    except (OSError, FileNotFoundError) as e:
                        print(f"WARN: Falha ao copiar logo da equipe campea {team.nome}: {e}")
                        champ_logo = None

                db.session.add(SeasonChampion(
                    season_id=season.id, grid=grid_name, grid_id=g_cfg.id, category='CONSTRUCTOR', position=j+1,
                    name=team.nome, image_url=champ_logo,
                    pontos=t_stats.total_pts, vitorias=t_stats.total_wins
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

@admin_bp.route('/seasons/<int:season_id>/toggle-home', methods=['POST'])
@login_required
def toggle_season_home(season_id):
    if current_user.role not in ['ADM', 'SUPER_ADM']:
        abort(403)
    season = Season.query.get_or_404(season_id)
    if not season.ativa:
        flash('Não é possível alterar a exibição de uma temporada encerrada.', 'danger')
        return redirect(url_for('admin.seasons'))
    season.exibir_home = not season.exibir_home
    
    # Invalida cache de home
    HomeCache.query.delete()
    db.session.commit()
    
    status = "exibida" if season.exibir_home else "ocultada"
    flash(f'Temporada {season.nome} foi {status} na Home com sucesso.', 'success')
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
    except ValueError:
        numero_etapa = 1
        total_etapas = len(corridas_grid) if corridas_grid else 1
        
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
                carro = "Mercedes (Extra)"
        lista_final.append({'pos': i + 1, 'nickname': item['piloto'].nickname, 'carro': carro})
        
    return render_template('admin/grid_text.html', race=race, lista=lista_final, usar_lastro=usar_lastro)

@admin_bp.route('/race/<int:race_id>/parse_simhub_csv', methods=['POST'])
@login_required
def parse_simhub_csv(race_id):
    try:
        race = Race.query.get_or_404(race_id)
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'Nenhum arquivo enviado.'}), 400

        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'success': False, 'message': 'Arquivo inválido ou vazio.'}), 400

        filename = file.filename
        try:
            content = file.read().decode('utf-8', errors='ignore')
        except Exception as e:
            return jsonify({'success': False, 'message': f'Erro ao ler o arquivo: {e}'}), 400

        # 0. Salva o arquivo CSV enviado na pasta CSV/ e executa a retenção de 15 dias
        SimHubService.save_csv_and_cleanup_old(filename, content, days_retention=15)

        # 1. Validação de Pista / Etapa
        is_valid_track, detected_track, warning = SimHubService.validate_track(filename, race.pista, race.nome_gp)
        force = request.form.get('force') == 'true'

        if not is_valid_track and not force:
            return jsonify({
                'success': False,
                'track_mismatch': True,
                'detected_track': detected_track,
                'race_pista': race.pista,
                'race_nome_gp': race.nome_gp,
                'warning': warning
            }), 200

        # 2. Busca lista de pilotos elegíveis para o grid
        all_pilots = PilotProfile.query.join(User).order_by(PilotProfile.nickname).all()
        all_eligible_pilots = []
        race_grid_id_str = str(race.grid_id) if race.grid_id else None

        for p in all_pilots:
            grid_tokens = [token.strip() for token in (p.grid or '').split(',') if token.strip()]
            if (race_grid_id_str and race_grid_id_str in grid_tokens) or ('RESERVA' in grid_tokens):
                all_eligible_pilots.append(p)

        # 3. Faz o parsing do conteúdo CSV (passa pilotos elegíveis e lista completa como fallback)
        parsed = SimHubService.parse_simhub_csv(content, all_eligible_pilots, all_pilots=all_pilots)

        return jsonify({
            'success': True,
            'detected_track': detected_track,
            'warning': warning,
            'parsed_data': parsed
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro no servidor ao processar telemetria: {str(e)}'}), 500

# --- RESULTADOS DA CORRIDA (COM CHECK-IN, BÔNUS E RESERVAS) ---

@admin_bp.route('/race/<int:race_id>/results', methods=['GET', 'POST'])
def race_results(race_id):
    race = Race.query.get_or_404(race_id)
    if request.method == 'POST':
        try:
            # PASSO 1: Chamamos a NOVA função de salvamento que criaremos a seguir.
            RaceResultService.save_race_results_by_position(race.id, request.form)
            flash('Resultados salvos com sucesso!', 'success')
            return redirect(url_for('admin.manage_season', season_id=race.season_id))
        except ValueError as e:
            db.session.rollback()
            flash(str(e), 'danger')
            return redirect(url_for('admin.race_results', race_id=race.id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao salvar resultados da corrida {race.id}: {e}", exc_info=True)
            flash(f'Erro ao salvar resultados da corrida: {e}', 'danger')
            return redirect(url_for('admin.race_results', race_id=race.id))

    # --- GET: Preparar dados para o formulário de resultados ---
    
    # 1. Busca todos os pilotos
    all_pilots = PilotProfile.query.join(User).order_by(PilotProfile.nickname).all()
    
    # 2. Filtra pilotos elegíveis e especificamente os TITULARES do grid desta corrida
    all_eligible_pilots = []
    titulares_do_grid = []
    race_grid_id_str = str(race.grid_id) if race.grid_id else None

    for p in all_pilots:
        grid_tokens = [token.strip() for token in (p.grid or '').split(',') if token.strip()]
        if (race_grid_id_str and race_grid_id_str in grid_tokens) or ('RESERVA' in grid_tokens):
            all_eligible_pilots.append(p)
        if race_grid_id_str and race_grid_id_str in grid_tokens and 'RESERVA' not in grid_tokens:
            titulares_do_grid.append(p)
    
    # 3. Resultados já gravados, separados por quem pontuou e quem não
    resultados_existentes = RaceResult.query.filter_by(race_id=race.id).order_by(RaceResult.posicao).all()
    results_by_pos = {r.posicao: r for r in resultados_existentes if r.posicao and r.posicao > 0}
    
    # 4. Pilotos que já têm um resultado (de qualquer tipo)
    pilots_with_results_ids = {r.pilot_id for r in resultados_existentes}
    
    # 5. Lista de pilotos elegíveis que ainda não têm nenhum resultado gravado para esta corrida
    pilotos_sem_resultado = [p for p in all_eligible_pilots if p.id not in pilots_with_results_ids]
    
    # 6. Resultados de ausentes/não classificados (FJ, FNJ, etc.) para preencher o formulário
    ausentes_existentes = [r for r in resultados_existentes if not r.posicao or r.posicao <= 0]
    ausentes_map = {r.pilot_id: r for r in ausentes_existentes}

    # 7. Determina o tamanho do grid para o loop do template
    grid_size = 22 # Default
    if race.grid_config and race.grid_config.vagas:
        grid_size = race.grid_config.vagas

    # 8. Busca registros de Check-in (RaceRegistration) da etapa
    registrations = RaceRegistration.query.filter_by(race_id=race.id).all()
    checkin_map = {reg.pilot_id: reg for reg in registrations}
    confirmados_list = [reg for reg in registrations if reg.status == 'CONFIRMADO']
    ausentes_list = [reg for reg in registrations if reg.status in ['AUSENTE', 'JUSTIFICADO']]
    
    # Pilotos elegíveis/titulares do grid que ainda não responderam ao check-in (Pendentes)
    target_pilots = titulares_do_grid if titulares_do_grid else all_eligible_pilots
    pendentes_list = [p for p in target_pilots if p.id not in checkin_map]

    return render_template('admin/race_results.html', 
                           race=race, 
                           all_pilots=all_pilots,
                           all_eligible_pilots=all_eligible_pilots,
                           titulares_do_grid=titulares_do_grid,
                           results_by_pos=results_by_pos,
                           pilotos_sem_resultado=pilotos_sem_resultado,
                           ausentes_existentes=ausentes_existentes,
                           ausentes_map=ausentes_map,
                           grid_size=grid_size,
                           registrations=registrations,
                           checkin_map=checkin_map,
                           confirmados_list=confirmados_list,
                           ausentes_list=ausentes_list,
                           pendentes_list=pendentes_list)
# --- GESTÃO DE PILOTOS E CONVITES ---

# A função _get_pilot_grid_names_from_ids (que causava o erro) foi removida
# e sua lógica foi integrada diretamente nos helpers locais de list_pilots.
# def _get_pilot_grid_names_from_ids(pilot_grid_str, grid_configs_map):
#     ... (código anterior) ...

@admin_bp.route('/pilots')
def list_pilots():
    # Mostra todos os pilotos, inclusive ADMs, para gestão de Grid/CNH
    pilots = PilotProfile.query.join(User).order_by(PilotProfile.nickname).all()

    # Carrega grids configurados de TODAS as temporadas para mapeamento de IDs para nomes
    # e para as abas, priorizando os da temporada ativa.
    active_seasons = Season.query.filter_by(ativa=True).all()
    active_season_ids = [s.id for s in active_seasons]
    
    all_grid_configs = GridConfig.query.order_by(GridConfig.season_id.desc(), GridConfig.ordem).all()
    grid_id_to_name_map = {cfg.id: cfg.nome for cfg in all_grid_configs}

    # Grids para as abas: prioriza os da temporada ativa, depois outros grids existentes, e especiais.
    grid_tabs_set = set()
    for cfg in all_grid_configs:
        if cfg.season_id in active_season_ids:
            grid_tabs_set.add(cfg.nome)
    for cfg in all_grid_configs: # Add others not in active seasons
        grid_tabs_set.add(cfg.nome)
    grid_tabs_set.add('RESERVA')
    grid_tabs_set.add('SEM_GRID')
    
    # Ordena as abas: primeiro as da temporada ativa, depois as outras por nome, depois especiais
    grid_tabs = sorted(list(grid_tabs_set), key=lambda x: (
        0 if x in [cfg.nome for cfg in all_grid_configs if cfg.season_id in active_season_ids] else 1,
        2 if x == 'RESERVA' else 3 if x == 'SEM_GRID' else 1,
        x
    ))

    # Organiza pilotos por NOME de grid (um piloto pode aparecer em vários)
    pilots_by_grid = {name: [] for name in grid_tabs}

    for p in pilots:
        # Helper local para converter IDs de grid para nomes para agrupamento nas abas
        def _get_grid_names_for_grouping(pilot_grid_str, grid_map):
            if not pilot_grid_str or pilot_grid_str == 'SEM_GRID':
                return ['SEM_GRID']
            names = []
            for token in [x.strip() for x in pilot_grid_str.split(',') if x.strip()]:
                if token.isdigit():
                    names.append(grid_map.get(int(token), token)) # Usa nome do mapa, fallback para ID se não encontrado
                else:
                    names.append(token) # Tokens especiais como 'RESERVA'
            return names
        grid_names_for_pilot = _get_grid_names_for_grouping(p.grid, grid_id_to_name_map)
        
        # Se o piloto não tem grids definidos, vai para 'SEM_GRID'
        if not grid_names_for_pilot or (len(grid_names_for_pilot) == 1 and grid_names_for_pilot[0] == 'SEM_GRID'):
            pilots_by_grid.setdefault('SEM_GRID', []).append(p)
            continue
        
        # Adiciona o piloto a todas as abas de grid correspondentes
        for gname in grid_names_for_pilot:
            if gname not in pilots_by_grid:
                pilots_by_grid[gname] = [] # Should not happen if grid_tabs is comprehensive
            pilots_by_grid[gname].append(p)

    # Remove abas vazias, exceto 'SEM_GRID'
    # Apenas remove abas que não têm pilotos e não são 'SEM_GRID'
    # Isso garante que 'SEM_GRID' sempre apareça se for uma aba válida.
    grid_tabs = [
        tab for tab in grid_tabs
        if pilots_by_grid.get(tab) or tab == 'SEM_GRID'
    ]
    # Se 'SEM_GRID' não foi adicionado por ter pilotos, mas está na lista de abas,
    # garante que ele seja mantido.
    if 'SEM_GRID' not in grid_tabs and 'SEM_GRID' in grid_tabs_set:
        grid_tabs.append('SEM_GRID')

    # Garante que 'SEM_GRID' esteja no final, se existir
    if 'SEM_GRID' in grid_tabs:
        grid_tabs.remove('SEM_GRID')
        grid_tabs.append('SEM_GRID')

    # Helper para o template exibir os nomes dos grids do piloto
    def get_pilot_grids_display(pilot_profile_obj):
        pilot_grid_str = pilot_profile_obj.grid
        if not pilot_grid_str or pilot_grid_str == 'SEM_GRID':
            return 'SEM_GRID'
        names = []
        for token in [x.strip() for x in pilot_grid_str.split(',') if x.strip()]:
            if token.isdigit():
                names.append(grid_id_to_name_map.get(int(token), token)) # Usa nome do mapa, fallback para ID se não encontrado
            else:
                names.append(token) # Tokens especiais como 'RESERVA'
        return ", ".join(names)

    return render_template('admin/pilots.html', 
                           pilots_by_grid=pilots_by_grid,
                           total_count=len(pilots),
                           all_pilots=pilots,
                           grid_tabs=grid_tabs,
                           get_pilot_grids_display=get_pilot_grids_display)

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
        
        new_email = (request.form.get('email') or '').strip().lower()
        if new_email and new_email != pilot.user.email:
            existing_user = User.query.filter((User.email == new_email) & (User.id != pilot.user.id)).first()
            if existing_user:
                flash('O e-mail informado já está cadastrado para outro usuário.', 'danger')
            else:
                pilot.user.email = new_email
        elif not new_email:
            flash('O e-mail não pode ficar em branco.', 'danger')
        
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
        ddi = request.form.get('ddi')
        telefone_num = request.form.get('telefone_numero') or request.form.get('telefone')
        pilot.telefone = format_international_phone(ddi, telefone_num)
        
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
            if new_role and new_role in ['PILOTO', 'ADM', 'SUPER_ADM', 'NARRADOR', 'COMISSARIO']:
                # Impede que o Super Admin rebaixe a si mesmo para evitar bloqueio acidental
                if pilot.user.id != current_user.id:
                    pilot.user.role = new_role
                elif new_role != 'SUPER_ADM':
                    flash('Você não pode alterar seu próprio nível de acesso.', 'warning')
        
        if 'foto' in request.files:
            file = request.files['foto']
            if file and file.filename != '' and allowed_file(file.filename):
                if pilot.foto_url and pilot.foto_url != '../img/NP.jpg':
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

    stored_ddi, stored_number = parse_phone_components(pilot.telefone)
    return render_template('admin/edit_pilot.html', pilot=pilot, grid_configs_options=grid_configs_options, special_options=special_options, historico=historico_punicoes, ddi_options=DDI_OPTIONS, stored_ddi=stored_ddi, stored_number=stored_number)

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
        if profile.foto_url and profile.foto_url != '../img/NP.jpg':
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
        if profile.foto_url and profile.foto_url != '../img/NP.jpg':
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
    all_seasons = Season.query.filter_by(ativa=True).order_by(Season.id.desc()).all()
    selected_season_id = request.args.get('s', type=int)
    
    season_ativa = None
    if selected_season_id:
        season_ativa = next((s for s in all_seasons if s.id == selected_season_id), None)
    
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
        pilot3_id = request.form.get('pilot3')
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
        if pilot3_id:
            p3 = PilotProfile.query.get(pilot3_id)
            if p3 and p3.id not in titulares_ids:
                unlink_from_other_teams(p3)
                team.pilots.append(p3)
                titulares_ids.add(p3.id)
            
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
            campeonato_equipes = True if request.form.get('campeonato_equipes') == 'on' else False
            exibir_lastro = not campeonato_equipes
            
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
    total_admins = User.query.filter(User.role.in_(['ADM', 'SUPER_ADM', 'COMISSARIO'])).count()

    # Obtém a lista de IDs de protestos onde o administrador atual já votou
    voted_protest_ids = [v.protesto_id for v in VotoComissario.query.filter_by(admin_id=current_user.id).all()]

    aguardando = Protesto.query.filter_by(status='AGUARDANDO_DEFESA').order_by(Protesto.data_criacao.desc()).all()
    em_votacao = Protesto.query.filter_by(status='EM_VOTACAO').order_by(Protesto.data_criacao.desc()).all()
    concluidos = Protesto.query.filter_by(status='CONCLUIDO').order_by(Protesto.data_fechamento.desc()).limit(50).all()
    
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
