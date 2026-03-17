from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app.models import db, User, News, Season, Race, PilotProfile, Team, RaceResult, GridConfig, RaceRegistration
from app.services.team_context import build_team_context
from app.services.scoring_service import ScoringService
from app.services.calendar_service import CalendarService
from app.services.standings_service import StandingsService
from datetime import datetime, timedelta

api_bp = Blueprint('api', __name__)

@api_bp.route('/login', methods=['POST'])
def login():
    if not request.is_json:
        return jsonify({"msg": "Requisicao deve ser JSON"}), 400
    
    email = request.json.get('email', None)
    password = request.json.get('password', None)
    fcm_token = request.json.get('fcm_token', None) # Token do celular para notificacao
    
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"msg": "Email ou senha incorretos"}), 401
    
    # Recupera o perfil de piloto
    pilot = user.pilot_profile
    
    # Se enviou token de notificação, salva no banco
    if pilot and fcm_token:
        pilot.fcm_token = fcm_token
        db.session.commit()

    # Cria o token de acesso (o "crachá" do app)
    access_token = create_access_token(identity=user.id)
    
    return jsonify({
        "access_token": access_token,
        "user": {
            "id": user.id,
            "username": user.username,
            "pilot_id": pilot.id if pilot else None,
            "nickname": pilot.nickname if pilot else user.username,
            "foto": pilot.foto_url if pilot else None
        }
    }), 200

@api_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    if not user or not user.pilot_profile:
        return jsonify({"msg": "Perfil de piloto não encontrado"}), 404

    pilot = user.pilot_profile
    
    active_season = Season.query.filter_by(ativa=True).first()
    current_team_name = "Sem Equipe"
    if active_season:
        pilot_teams_in_season = [t for t in pilot.teams if t.season_id == active_season.id]
        if pilot_teams_in_season:
            pilot_teams_in_season.sort(key=lambda t: t.grid_config.ordem if t.grid_config else 99)
            current_team_name = pilot_teams_in_season[0].nome

    cnh_status = "OK"
    if pilot.pontos_cnh <= 10: cnh_status = "Em Risco"
    if pilot.pontos_cnh <= 5: cnh_status = "Crítico"
    if pilot.esta_banido(): cnh_status = "BANIDO"
    
    # Busca o histórico de corridas do piloto na temporada atual
    desempenho_temporada = []
    pilot_grid_ids = [int(g_id) for g_id in (pilot.grid or '').split(',') if g_id.isdigit()]
    
    if active_season:
        # Se o piloto tem grids definidos, filtra por eles
        if pilot_grid_ids:
            resultados = RaceResult.query.join(Race).filter(
                RaceResult.pilot_id == pilot.id,
                Race.season_id == active_season.id,
                Race.grid_id.in_(pilot_grid_ids)
            ).order_by(Race.data_corrida.asc()).all()
        else:
            # Se não tem grid definido, retorna vazio
            resultados = []
        
        for r in resultados:
            grid_nome = r.race.grid_config.nome if r.race.grid_config else r.race.grid
            desempenho_temporada.append({
                "gp": r.race.nome_gp,
                "grid": grid_nome,
                "posicao": r.posicao,
                "dnf": r.dnf,
                "dsq": r.dsq,
                "pontos": r.pontos_ganhos,
                "data": r.race.data_corrida.strftime('%d/%m') if r.race.data_corrida else None,
                "status": r.race.status,
                "participou": r.status_presenca == 'OK'
            })
        
        # Se não encontrou resultados mas o piloto tem resultados em outras temporadas
        if not resultados and pilot.race_results:
            # Log para debug
            print(f"[API] Piloto {pilot.id} ({pilot.nickname}) não tem resultados na temporada {active_season.id}, mas tem {len(pilot.race_results)} resultados no total")

    profile_data = {
        "id": pilot.id,
        "nickname": pilot.nickname,
        "nome_real": pilot.nome_real,
        "foto_url": pilot.foto_url,
        "equipe_atual": current_team_name,
        "cnh_pontos": pilot.pontos_cnh,
        "cnh_status": cnh_status,
        "advertencias": pilot.advertencias_acumuladas,
        "desempenho_temporada": desempenho_temporada
    }
    
    return jsonify(profile_data), 200

@api_bp.route('/next-race', methods=['GET'])
@jwt_required()
def get_next_race_for_checkin():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    if not user or not user.pilot_profile:
        return jsonify({"msg": "Perfil de piloto não encontrado"}), 404
    
    pilot = user.pilot_profile
    
    pilot_grid_ids = [int(g_id) for g_id in (pilot.grid or '').split(',') if g_id.isdigit()]
    if not pilot_grid_ids:
        return jsonify(None), 200

    now = datetime.utcnow().date()
    
    # Busca todas as corridas futuras agendadas nos grids do piloto
    future_races = Race.query.filter(
        Race.grid_id.in_(pilot_grid_ids),
        Race.data_corrida >= now,
        Race.status == 'Agendada'
    ).order_by(Race.data_corrida.asc()).all()

    # Encontra a primeira corrida que o piloto ainda não confirmou ou justificou
    # (igual à lógica do site em public.py)
    for race in future_races:
        registration = RaceRegistration.query.filter_by(race_id=race.id, pilot_id=pilot.id).first()
        if not registration or registration.status not in ['CONFIRMADO', 'JUSTIFICADO']:
            return jsonify({
                "race_id": race.id,
                "nome_gp": race.nome_gp,
                "pista": race.pista,
                "data_corrida": race.data_corrida.isoformat(),
                "grid_nome": race.grid_config.nome if race.grid_config else race.grid,
                "checkin_status": registration.status if registration else "PENDENTE"
            }), 200

    # Se chegou aqui, todas as corridas futuras já foram confirmadas/justificadas
    return jsonify(None), 200

@api_bp.route('/checkin', methods=['POST'])
@jwt_required()
def perform_checkin():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    if not user or not user.pilot_profile:
        return jsonify({"msg": "Perfil de piloto não encontrado"}), 401

    pilot = user.pilot_profile
    
    if not request.is_json:
        return jsonify({"msg": "Requisicao deve ser JSON"}), 400

    race_id = request.json.get('race_id', None)
    status = request.json.get('status', None)

    if not race_id or status not in ["CONFIRMADO", "AUSENTE"]:
        return jsonify({"msg": "Parâmetros inválidos"}), 400

    race = db.session.get(Race, race_id)
    if not race:
        return jsonify({"msg": "Corrida não encontrada"}), 404

    pilot_grid_ids = [int(g_id) for g_id in (pilot.grid or '').split(',') if g_id.isdigit()]
    if race.grid_id not in pilot_grid_ids:
        return jsonify({"msg": "Piloto não pertence ao grid desta corrida"}), 403

    registration = RaceRegistration.query.filter_by(race_id=race.id, pilot_id=pilot.id).first()
    if registration:
        registration.status = status
        registration.data_resposta = datetime.utcnow()
    else:
        registration = RaceRegistration(
            race_id=race.id,
            pilot_id=pilot.id,
            status=status,
            data_resposta=datetime.utcnow()
        )
        db.session.add(registration)
    
    db.session.commit()

    return jsonify({
        "msg": f"Check-in para '{race.nome_gp}' atualizado para '{status}'",
        "new_status": status
    }), 200

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
