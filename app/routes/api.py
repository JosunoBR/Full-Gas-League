from flask import Blueprint, jsonify
from app.models import News, Season, Race, PilotProfile, Team, RaceResult, GridConfig
from app.services.team_context import build_team_context
from app.services.scoring_service import ScoringService
from app.services.calendar_service import CalendarService
from app.services.standings_service import StandingsService

api_bp = Blueprint('api', __name__)

@api_bp.route('/news', methods=['GET'])
def get_news():
    noticias = News.query.order_by(News.data_publicacao.desc()).limit(10).all()
    return jsonify([n.to_dict() for n in noticias])

@api_bp.route('/standings/<grid>', methods=['GET'])
def get_standings(grid):
    season = Season.query.filter_by(ativa=True).order_by(Season.id.asc()).first()
    if not season:
        return jsonify([])
    
    # Busca a config do grid para garantir o ID correto
    grid_cfg = GridConfig.query.filter_by(season_id=season.id, nome=grid.upper()).first()
    if not grid_cfg:
        return jsonify([])

    team_ctx = build_team_context(season.id)
    participants = team_ctx["participants_by_grid"].get(grid_cfg.id, [])
    ranking = []

    for item in participants:
        p = item["pilot"]
        pts_finais = ScoringService.calculate_pilot_total_points(p.id, season.id, grid_cfg.id)

        ranking.append({
            'id': p.id,
            'nickname': p.nickname,
            'pontos': pts_finais,
            'telefone': p.telefone,
            'foto': p.foto_url
        })
    
    ranking.sort(key=lambda x: x['pontos'], reverse=True)
    return jsonify(ranking)

@api_bp.route('/calendar/<grid>', methods=['GET'])
def get_calendar(grid):
    season = Season.query.filter_by(ativa=True).order_by(Season.id.asc()).first()
    if not season:
        return jsonify([])

    grid_cfg = GridConfig.query.filter_by(season_id=season.id, nome=grid.upper()).first()
    if not grid_cfg:
        return jsonify([])

    corridas = Race.query.filter_by(season_id=season.id, grid_id=grid_cfg.id).order_by(Race.data_corrida).all()
    return jsonify([r.to_dict() for r in corridas])

@api_bp.route('/race/<int:race_id>/results', methods=['GET'])
def get_race_results(race_id):
    """
    Retorna um resumo leve e totalmente serializável da corrida,
    usado na súmula do modal da Home.
    """
    try:
        summary = CalendarService.get_race_summary(race_id)
    except Exception as exc:
        # Fallback defensivo: nunca deixar a requisição "pendurada"
        # e sempre retornar um JSON simples em caso de falha interna.
        print(f"[API] Erro em get_race_results({race_id}): {exc}")
        return jsonify({'error': 'Erro interno ao carregar a súmula.'}), 500

    if not summary:
        return jsonify({'error': 'Corrida nao encontrada'}), 404

    # Serialização segura de datas
    data_corrida = summary.get('data_corrida')
    if data_corrida is not None:
        try:
            summary['data_corrida'] = data_corrida.isoformat()
        except AttributeError:
            # Se já vier como string/None, não faz nada
            pass

    return jsonify(summary)

@api_bp.route('/standings/<int:grid_id>/evolution', methods=['GET'])
def get_grid_evolution(grid_id):
    """
    Retorna os dados de evolução de pontos para o gráfico da Home.
    Carregamento sob demanda (Lazy Loading).
    """
    season = Season.query.filter_by(ativa=True).order_by(Season.id.asc()).first()
    if not season: return jsonify([])
    data = StandingsService.get_evolution_data(season.id, grid_id)
    return jsonify(data)

@api_bp.route('/pilots', methods=['GET'])
def get_all_pilots():
    pilotos = PilotProfile.query.filter(PilotProfile.grid != 'SEM_GRID').all()
    return jsonify([p.to_dict() for p in pilotos])

@api_bp.route('/teams', methods=['GET'])
def get_teams():
    equipes = Team.query.filter_by(ativa=True).all()
    return jsonify([t.to_dict() for t in equipes])
