from flask import Blueprint, jsonify
from app.models import News, Season, Race, PilotProfile, Team, RaceResult

api_bp = Blueprint('api', __name__)

@api_bp.route('/news', methods=['GET'])
def get_news():
    noticias = News.query.order_by(News.data_publicacao.desc()).limit(10).all()
    return jsonify([n.to_dict() for n in noticias])

@api_bp.route('/standings/<grid>', methods=['GET'])
def get_standings(grid):
    season = Season.query.filter_by(ativa=True).first()
    if not season:
        return jsonify([])
    
    pilotos = PilotProfile.query.filter_by(grid=grid.upper()).all()
    ranking = []
    for p in pilotos:
        pts = sum(r.pontos_ganhos for r in p.race_results if r.race.season_id == season.id)
        ranking.append({
            'id': p.id,
            'nickname': p.nickname,
            'pontos': pts,
            'telefone': p.telefone,
            'equipe': p.team.nome if p.team else 'Sem Equipe',
            'foto': p.foto_url
        })
    
    ranking.sort(key=lambda x: x['pontos'], reverse=True)
    return jsonify(ranking)

@api_bp.route('/calendar/<grid>', methods=['GET'])
def get_calendar(grid):
    season = Season.query.filter_by(ativa=True).first()
    if not season:
        return jsonify([])
    
    corridas = Race.query.filter_by(season_id=season.id, grid=grid.upper()).order_by(Race.data_corrida).all()
    return jsonify([r.to_dict() for r in corridas])

@api_bp.route('/race/<int:race_id>/results', methods=['GET'])
def get_race_results(race_id):
    resultados = RaceResult.query.filter_by(race_id=race_id).order_by(RaceResult.posicao).all()
    return jsonify([res.to_dict() for res in resultados])

@api_bp.route('/pilots', methods=['GET'])
def get_all_pilots():
    pilotos = PilotProfile.query.filter(PilotProfile.grid != 'SEM_GRID').all()
    return jsonify([p.to_dict() for p in pilotos])

@api_bp.route('/teams', methods=['GET'])
def get_teams():
    equipes = Team.query.filter_by(ativa=True).all()
    return jsonify([t.to_dict() for t in equipes])