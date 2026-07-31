from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app.models import db, User, News, Season, Race, PilotProfile, Team, RaceResult, GridConfig, RaceRegistration, Protesto, SeasonChampion
from app.services.team_context import build_team_context
from app.services.scoring_service import ScoringService
from app.services.calendar_service import CalendarService
from app.services.standings_service import StandingsService
from app.services.discipline_service import DisciplineService
from app.services.notification_service import NotificationService
from app.utils import calcular_perda
from datetime import datetime, timedelta

api_bp = Blueprint('api', __name__)

@api_bp.route('/login', methods=['POST'])
def login():
    print("[API] Tentativa de login recebida no servidor!")
    
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
    p_grid_id = None

    if active_season:
        # 1. Tenta achar o grid e nome do time do piloto (titular)
        pilot_teams_in_season = [t for t in pilot.teams if t.season_id == active_season.id]
        if pilot_teams_in_season:
            pilot_teams_in_season.sort(key=lambda t: t.grid_config.ordem if t.grid_config else 99)
            current_team_name = pilot_teams_in_season[0].nome
            p_grid_id = pilot_teams_in_season[0].grid_id
        else:
            # 2. Tenta achar o grid do piloto (reserva)
            pilot_reserves_in_season = [t for t in pilot.reserve_teams if t.season_id == active_season.id]
            if pilot_reserves_in_season:
                pilot_reserves_in_season.sort(key=lambda t: t.grid_config.ordem if t.grid_config else 99)
                p_grid_id = pilot_reserves_in_season[0].grid_id

        # 3. Fallback: busca pelo campo grid do perfil
        if not p_grid_id and pilot.grid and pilot.grid != 'SEM_GRID':
            grid_tokens = [token.strip() for token in pilot.grid.split(',') if token.strip().isdigit()]
            if grid_tokens:
                p_grid_id = int(grid_tokens[0])

    # Cálculo dinâmico de CNH e Advertências para a API
    dynamic_cnh = pilot.pontos_cnh
    if active_season and p_grid_id:
        cnh_info = DisciplineService.get_pilot_discipline_stats(pilot.id, active_season.id, p_grid_id)
        dynamic_cnh = cnh_info['cnh']

    cnh_status = "OK"
    if dynamic_cnh <= 10: cnh_status = "Em Risco"
    if dynamic_cnh <= 5: cnh_status = "Crítico"
    if dynamic_cnh <= 0: cnh_status = "BANIDO"

    # --- CÁLCULO DO LASTRO (Veículo da próxima corrida) ---
    lastro_veiculo = "Não definido"
    if active_season and p_grid_id and current_team_name != "Sem Equipe":
        # Busca a classificação atual do grid
        team_ctx = build_team_context(active_season.id)
        participants = team_ctx["participants_by_grid"].get(p_grid_id, [])
        ranking = []
        
        for item in participants:
            p = item["pilot"]
            pts_finais = ScoringService.calculate_pilot_total_points(p.id, active_season.id, p_grid_id)
            ranking.append({'id': p.id, 'pontos': pts_finais})
        
        # Ordena por pontos (Líderes no topo)
        ranking.sort(key=lambda x: x['pontos'], reverse=True)
        
        # Descobre a posição do piloto na tabela
        pos = next((i for i, r in enumerate(ranking) if r['id'] == pilot.id), -1)
        if pos != -1:
            pos += 1 # 1 para 1º lugar, 2 para 2º...
            # Regra do Lastro 2026 (11 Equipes - Construtores 2026 Invertido):
            # 1-2(Cadillac), 3-4(Aston), 5-6(Williams), 7-8(Audi), 9-10(Haas), 11-12(Alpine),
            # 13-14(RB), 15-16(Red Bull), 17-18(McLaren), 19-20(Ferrari), 21-22(Mercedes)
            carros_lastro = [
                "Cadillac", "Cadillac", "Aston Martin", "Aston Martin", "Williams", "Williams",
                "Audi", "Audi", "Haas", "Haas", "Alpine", "Alpine",
                "RB", "RB", "Red Bull", "Red Bull", "McLaren", "McLaren",
                "Ferrari", "Ferrari", "Mercedes", "Mercedes"
            ]
            lastro_veiculo = carros_lastro[pos-1] if pos <= len(carros_lastro) else "Mercedes"
    
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
            
            punicoes_tribunal = Protesto.query.filter_by(
                acusado_id=pilot.id,
                etapa_id=r.race_id,
                status='CONCLUIDO'
            ).all()
            total_punicoes_tribunal = sum(calcular_perda(p.veredito_final) for p in punicoes_tribunal)
            pontos_finais = (r.pontos_ganhos or 0.0) - total_punicoes_tribunal
            
            desempenho_temporada.append({
                "gp": r.race.nome_gp,
                "grid": grid_nome,
                "posicao": r.posicao,
                "dnf": r.dnf,
                "dsq": r.dsq,
                "pontos": round(pontos_finais, 1),
                "data": r.race.data_corrida.strftime('%d/%m') if r.race.data_corrida else None,
                "status": r.race.status,
                "participou": r.status_presenca == 'OK'
            })
        
        # Se não encontrou resultados mas o piloto tem resultados em outras temporadas
        if not resultados and pilot.race_results:
            # Log para debug
            print(f"[API] Piloto {pilot.id} ({pilot.nickname}) não tem resultados na temporada {active_season.id}, mas tem {len(pilot.race_results)} resultados no total")

    quali_ban = False
    advertencias = 0
    if p_grid_id:
        quali_ban = DisciplineService.is_quali_banned(pilot.id, p_grid_id)
        if active_season:
            cnh_info = DisciplineService.get_pilot_discipline_stats(pilot.id, active_season.id, p_grid_id)
            advertencias = cnh_info.get('advertencias', 0)

    # --- PONTUAÇÃO DO PILOTO NOS CAMPEONATOS DA TEMPORADA ---
    pontuacao_campeonatos = []
    if active_season:
        all_grid_cfgs = GridConfig.query.filter_by(season_id=active_season.id).order_by(GridConfig.ordem).all()
        team_ctx = build_team_context(active_season.id)
        
        for g_cfg in all_grid_cfgs:
            participants = team_ctx["participants_by_grid"].get(g_cfg.id, [])
            p_item = next((item for item in participants if item["pilot"].id == pilot.id), None)
            res_in_grid = [r for r in pilot.race_results if r.race.season_id == active_season.id and r.race.grid_id == g_cfg.id]
            
            if p_item or res_in_grid:
                team_name = p_item["team"].nome if p_item and p_item.get("team") else "Sem Equipe"
                pts = ScoringService.calculate_pilot_total_points(pilot.id, active_season.id, g_cfg.id)
                wins = ScoringService.get_pilot_wins(res_in_grid)
                
                grid_standings = []
                for part in participants:
                    p_id = part["pilot"].id
                    p_pts = ScoringService.calculate_pilot_total_points(p_id, active_season.id, g_cfg.id)
                    grid_standings.append((p_id, p_pts))
                grid_standings.sort(key=lambda x: x[1], reverse=True)
                
                pos = 1
                for idx, (p_id, _) in enumerate(grid_standings, start=1):
                    if p_id == pilot.id:
                        pos = idx
                        break
                
                pontuacao_campeonatos.append({
                    "grid_nome": g_cfg.nome,
                    "equipe": team_name,
                    "pontos": round(pts, 1),
                    "posicao": pos,
                    "vitorias": wins
                })

    profile_data = {
        "id": pilot.id,
        "nickname": pilot.nickname,
        "nome_real": pilot.nome_real,
        "foto_url": pilot.foto_url,
        "equipe_atual": current_team_name,
        "cnh_pontos": dynamic_cnh,
        "cnh_status": cnh_status,
        "advertencias": advertencias,
        "quali_ban": quali_ban,
        "grid_id": p_grid_id,
        "lastro_veiculo": lastro_veiculo,
        "desempenho_temporada": desempenho_temporada,
        "pontuacao_campeonatos": pontuacao_campeonatos
    }
    
    return jsonify(profile_data), 200

@api_bp.route('/profile/update', methods=['POST'])
@jwt_required()
def update_profile_api():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    if not user or not user.pilot_profile:
        return jsonify({"msg": "Perfil não encontrado"}), 404

    pilot = user.pilot_profile
    data = request.get_json() or {}

    new_nickname = (data.get('nickname') or '').strip()
    new_nome_real = (data.get('nome_real') or '').strip()
    new_telefone = (data.get('telefone') or '').strip()

    if new_nickname:
        existing = PilotProfile.query.filter(func.lower(PilotProfile.nickname) == func.lower(new_nickname), PilotProfile.id != pilot.id).first()
        if existing:
            return jsonify({"msg": f"O nickname '{new_nickname}' já está em uso por outro piloto."}), 400
        pilot.nickname = new_nickname

    if new_nome_real:
        pilot.nome_real = new_nome_real

    if new_telefone:
        pilot.telefone = new_telefone

    new_password = (data.get('password') or '').strip()
    if new_password:
        if len(new_password) < 4:
            return jsonify({"msg": "A nova senha deve ter no mínimo 4 caracteres."}), 400
        user.set_password(new_password)

    try:
        db.session.commit()
        return jsonify({
            "msg": "Perfil atualizado com sucesso!",
            "nickname": pilot.nickname,
            "nome_real": pilot.nome_real,
            "telefone": pilot.telefone
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": f"Erro ao atualizar perfil: {str(e)}"}), 500

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
    justificativa = request.json.get('justificativa', None)

    if status == "AUSENTE":
        status = "JUSTIFICADO"

    if not race_id or status not in ["CONFIRMADO", "JUSTIFICADO"]:
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
        registration.justificativa = justificativa
        registration.data_resposta = datetime.utcnow()
    else:
        registration = RaceRegistration(
            race_id=race.id,
            pilot_id=pilot.id,
            status=status,
            justificativa=justificativa,
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

from app.services.standings_service import StandingsService

def get_active_home_data():
    season = Season.query.filter_by(ativa=True).order_by(Season.id.asc()).first()
    if not season:
        season = Season.query.order_by(Season.id.desc()).first()
    if not season:
        return None, {}
    data = StandingsService.get_home_data(season.id)
    return season, data

def find_grid_cfg_in_data(grid_identifier, grid_configs):
    if not grid_identifier or not grid_configs:
        return None
    grid_str = str(grid_identifier).strip()
    
    if grid_str.isdigit():
        target_id = int(grid_str)
        matched = next((g for g in grid_configs if g['id'] == target_id), None)
        if matched:
            return matched

    matched = next((g for g in grid_configs if g['nome'].lower() == grid_str.lower()), None)
    if matched:
        return matched

    matched = next((g for g in grid_configs if grid_str.lower() in g['nome'].lower() or g['nome'].lower() in grid_str.lower()), None)
    if matched:
        return matched

    return grid_configs[0] if grid_configs else None

@api_bp.route('/grid-configs', methods=['GET'])
def get_grid_configs():
    season, data = get_active_home_data()
    configs = data.get('grid_configs', [])
    return jsonify([{"id": c['id'], "nome": c['nome']} for c in configs])

@api_bp.route('/constructors/<grid>', methods=['GET'])
def get_constructors_standings(grid):
    season, data = get_active_home_data()
    grid_configs = data.get('grid_configs', [])
    cfg = find_grid_cfg_in_data(grid, grid_configs)
    if not cfg:
        return jsonify([])
    
    raw_list = data.get('constructors', {}).get(cfg['id'], [])
    result = []
    for idx, item in enumerate(raw_list, start=1):
        eq_data = item.get('equipe') or {}
        eq_nome = eq_data.get('nome') if isinstance(eq_data, dict) else str(eq_data)
        eq_logo = eq_data.get('logo_url') if isinstance(eq_data, dict) else None
        result.append({
            "posicao": idx,
            "nome": eq_nome,
            "logo": eq_logo,
            "pontos": round(item.get('pontos', 0.0), 1),
            "vitorias": item.get('vitorias', 0)
        })
    return jsonify(result)

@api_bp.route('/standings/<grid>', methods=['GET'])
def get_standings(grid):
    season, data = get_active_home_data()
    grid_configs = data.get('grid_configs', [])
    cfg = find_grid_cfg_in_data(grid, grid_configs)
    if not cfg:
        return jsonify([])
    
    raw_list = data.get('standings', {}).get(cfg['id'], [])
    ranking = []
    for item in raw_list:
        p_data = item.get('piloto') or item.get('pilot') or {}
        ranking.append({
            'id': p_data.get('id'),
            'nickname': p_data.get('nickname') or p_data.get('nome_real'),
            'pontos': round(item.get('pontos', 0.0), 1),
            'vitorias': item.get('vitorias', 0),
            'foto': item.get('foto_url'),
            'equipe': item.get('team_name', 'Sem Equipe')
        })
    ranking.sort(key=lambda x: x['pontos'], reverse=True)
    return jsonify(ranking)

@api_bp.route('/calendar/<grid>', methods=['GET'])
def get_calendar(grid):
    season, data = get_active_home_data()
    grid_configs = data.get('grid_configs', [])
    cfg = find_grid_cfg_in_data(grid, grid_configs)
    if not cfg:
        return jsonify([])
    
    raw_races = data.get('calendar', {}).get(cfg['id'], [])
    result = []
    for r in raw_races:
        d_val = r.get('data_corrida')
        if hasattr(d_val, 'strftime'):
            dt_str = d_val.strftime('%d/%m/%Y')
        elif isinstance(d_val, str):
            dt_str = d_val[:10]
        else:
            dt_str = "A definir"

        st_val = r.get('status') or ("Concluida" if r.get('vencedor') else "Agendada")

        result.append({
            "id": r.get('id'),
            "nome_gp": r.get('nome_gp'),
            "pista": r.get('pista') or "Circuito Geral",
            "data": dt_str,
            "grid": cfg['nome'],
            "status": "Concluida" if str(st_val).upper() in ['CONCLUIDA', 'CONCLUÍDA'] else "Agendada"
        })
    return jsonify(result)

@api_bp.route('/race/<int:race_id>/results', methods=['GET'])
def get_race_results(race_id):
    """
    Endpoint utilizado exclusivamente pelo portal WEB (Bootstrap Modal na Home).
    Retorna a estrutura completa e intocada do CalendarService.get_race_summary.
    """
    try:
        summary = CalendarService.get_race_summary(race_id)
    except Exception as exc:
        print(f"[API] Erro em get_race_results({race_id}): {exc}")
        return jsonify({'error': 'Erro interno ao carregar a súmula.'}), 500

    if not summary:
        return jsonify({'error': 'Corrida nao encontrada'}), 404

    # Serialização segura da data
    data_corrida = summary.get('data_corrida')
    if data_corrida is not None:
        try:
            summary['data_corrida'] = data_corrida.isoformat()
        except AttributeError:
            pass

    return jsonify(summary)

@api_bp.route('/app/race/<int:race_id>/summary', methods=['GET'])
def get_app_race_summary(race_id):
    """
    Endpoint exclusivo e otimizado para a súmula do aplicativo móvel (React Native).
    Maneja nulos, previne erros de tipagem e garante formato simples e previsível.
    """
    race = db.session.get(Race, race_id)
    if not race:
        return jsonify({'error': 'Corrida não encontrada'}), 404

    # Busca os resultados ordenados por posição
    results = (
        RaceResult.query.filter_by(race_id=race.id)
        .filter(RaceResult.posicao.isnot(None), RaceResult.posicao > 0)
        .order_by(RaceResult.posicao.asc())
        .all()
    )

    clean_results = []
    for r in results:
        # Filtra presença
        if r.status_presenca in ['AUSENTE', 'JUSTIFICADO', 'NC']:
            continue

        pilot_name = r.pilot.nickname if (r.pilot and r.pilot.nickname) else (r.pilot.nome_real if r.pilot else "Piloto")
        team_name = r.team_snapshot.nome if r.team_snapshot else "Sem Equipe"
        grid_start = r.grid_largada if r.grid_largada and r.grid_largada > 0 else None

        clean_results.append({
            "posicao": r.posicao,
            "piloto": pilot_name,
            "equipe": team_name,
            "grid_largada": grid_start,
            "pontos": round(r.pontos_ganhos or 0.0, 1)
        })

    data_str = race.data_corrida.strftime('%d/%m/%Y') if race.data_corrida else "A definir"

    return jsonify({
        "id": race.id,
        "nome_gp": race.nome_gp,
        "pista": race.pista or "Circuito Geral",
        "data_corrida": data_str,
        "resultados": clean_results
    })

@api_bp.route('/standings/<int:grid_id>/evolution', methods=['GET'])
def get_grid_evolution(grid_id):
    """
    Retorna os dados de evolução de pontos para o gráfico da Home.
    Carregamento sob demanda (Lazy Loading).
    """
    grid = GridConfig.query.get(grid_id)
    season_id = grid.season_id if grid else None

    if not season_id:
        season = Season.query.filter_by(ativa=True).order_by(Season.id.asc()).first()
        if not season:
            season = Season.query.order_by(Season.id.desc()).first()
        if not season:
            return jsonify([])
        season_id = season.id

    data = StandingsService.get_evolution_data(season_id, grid_id)
    return jsonify(data)

@api_bp.route('/pilots', methods=['GET'])
def get_all_pilots():
    pilotos = PilotProfile.query.filter(PilotProfile.grid != 'SEM_GRID').all()
    return jsonify([p.to_dict() for p in pilotos])

@api_bp.route('/teams', methods=['GET'])
def get_teams():
    equipes = Team.query.filter_by(ativa=True).all()
    return jsonify([t.to_dict() for t in equipes])

# --- FASE 2: PROTESTOS & DEFESAS ---

@api_bp.route('/protests', methods=['GET'])
@jwt_required()
def get_protests():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    if not user or not user.pilot_profile:
        return jsonify({"msg": "Perfil não encontrado"}), 404

    pilot = user.pilot_profile
    protestos_feitos = Protesto.query.filter_by(acusador_id=pilot.id).order_by(Protesto.data_criacao.desc()).all()
    protestos_recebidos = Protesto.query.filter_by(acusado_id=pilot.id).order_by(Protesto.data_criacao.desc()).all()

    def serialize_p(p):
        return {
            "id": p.id,
            "etapa": p.etapa.nome_gp if p.etapa else "N/A",
            "acusador": p.acusador.nickname if p.acusador else "N/A",
            "acusado": p.acusado.nickname if p.acusado else "N/A",
            "acusador_id": p.acusador_id,
            "acusado_id": p.acusado_id,
            "video_link": p.video_link,
            "minuto": p.minuto,
            "descricao": p.descricao,
            "video_defesa": p.video_defesa,
            "argumento_defesa": p.argumento_defesa,
            "status": p.status,
            "veredito": p.veredito_final,
            "data": p.data_criacao.strftime('%d/%m/%Y %H:%M') if p.data_criacao else None
        }

    return jsonify({
        "protestos_feitos": [serialize_p(p) for p in protestos_feitos],
        "protestos_recebidos": [serialize_p(p) for p in protestos_recebidos]
    }), 200

@api_bp.route('/protests/create', methods=['POST'])
@jwt_required()
def create_protest():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    if not user or not user.pilot_profile:
        return jsonify({"msg": "Perfil não encontrado"}), 404

    if not request.is_json:
        return jsonify({"msg": "Requisicao deve ser JSON"}), 400

    data = request.json
    etapa_id = data.get('etapa_id')
    acusado_id = data.get('acusado_id')
    video_link = data.get('video_link')
    minuto = data.get('minuto')
    descricao = data.get('descricao')

    if not etapa_id or not acusado_id or not video_link:
        return jsonify({"msg": "Campos obrigatórios ausentes"}), 400

    race = db.session.get(Race, etapa_id)
    acusado = db.session.get(PilotProfile, acusado_id)
    if not race or not acusado:
        return jsonify({"msg": "Corrida ou piloto não encontrado"}), 404

    protesto = Protesto(
        etapa_id=race.id,
        grid_id=race.grid_id,
        acusador_id=user.pilot_profile.id,
        acusado_id=acusado.id,
        video_link=video_link,
        minuto=minuto,
        descricao=descricao,
        status='AGUARDANDO_DEFESA',
        data_criacao=datetime.utcnow()
    )
    db.session.add(protesto)
    db.session.commit()

    # Notificação Push via FCM para o acusado
    if acusado.fcm_token:
        try:
            NotificationService.send_single_notification(
                token=acusado.fcm_token,
                title="🚨 Novo Protesto Registrado",
                body=f"Você recebeu um protesto no {race.nome_gp} de {user.pilot_profile.nickname}. Acesse o app para se defender.",
                data={"protest_id": str(protesto.id)}
            )
        except Exception as err:
            print(f"[API] Erro notificação protesto: {err}")

    return jsonify({"msg": "Protesto aberto com sucesso", "id": protesto.id}), 201

@api_bp.route('/protests/<int:protest_id>/defense', methods=['POST'])
@jwt_required()
def submit_defense(protest_id):
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    if not user or not user.pilot_profile:
        return jsonify({"msg": "Perfil não encontrado"}), 404

    protesto = db.session.get(Protesto, protest_id)
    if not protesto:
        return jsonify({"msg": "Protesto não encontrado"}), 404

    if protesto.acusado_id != user.pilot_profile.id:
        return jsonify({"msg": "Sem permissão para defender este protesto"}), 403

    if not request.is_json:
        return jsonify({"msg": "Requisicao deve ser JSON"}), 400

    data = request.json
    protesto.video_defesa = data.get('video_defesa')
    protesto.argumento_defesa = data.get('argumento_defesa')
    if protesto.status == 'AGUARDANDO_DEFESA':
        protesto.status = 'EM_VOTACAO'

    db.session.commit()
    return jsonify({"msg": "Defesa enviada com sucesso!"}), 200

# --- FASE 4: HEAD-TO-HEAD & EQUIPE ---

@api_bp.route('/head-to-head/<int:p1_id>/<int:p2_id>', methods=['GET'])
def get_head_to_head(p1_id, p2_id):
    p1 = db.session.get(PilotProfile, p1_id)
    p2 = db.session.get(PilotProfile, p2_id)
    if not p1 or not p2:
        return jsonify({"msg": "Pilotos não encontrados"}), 404

    # Busca resultados da temporada ativa
    active_season = Season.query.filter_by(ativa=True).first()
    s_id = active_season.id if active_season else None

    res1 = RaceResult.query.join(Race).filter(RaceResult.pilot_id == p1.id, Race.season_id == s_id).all() if s_id else []
    res2 = RaceResult.query.join(Race).filter(RaceResult.pilot_id == p2.id, Race.season_id == s_id).all() if s_id else []

    races_map1 = {r.race_id: r for r in res1}
    races_map2 = {r.race_id: r for r in res2}
    common_races = set(races_map1.keys()) & set(races_map2.keys())

    h2h_races_p1 = 0
    h2h_races_p2 = 0
    for r_id in common_races:
        pos1 = races_map1[r_id].posicao
        pos2 = races_map2[r_id].posicao
        if pos1 > 0 and (pos2 == 0 or pos1 < pos2):
            h2h_races_p1 += 1
        elif pos2 > 0 and (pos1 == 0 or pos2 < pos1):
            h2h_races_p2 += 1

    return jsonify({
        "p1": {"id": p1.id, "nickname": p1.nickname, "foto": p1.foto_url, "h2h_vitorias": h2h_races_p1},
        "p2": {"id": p2.id, "nickname": p2.nickname, "foto": p2.foto_url, "h2h_vitorias": h2h_races_p2},
        "corridas_em_comum": len(common_races)
    }), 200

# --- FASE 5: HALL DA FAMA ---

@api_bp.route('/hall-of-fame', methods=['GET'])
def get_hall_of_fame():
    champions = SeasonChampion.query.all()
    result = []
    for c in champions:
        result.append({
            "season": c.season.nome if c.season else "N/A",
            "grid": c.grid,
            "category": c.category,
            "position": c.position,
            "name": c.name,
            "team_name": c.team_name,
            "image_url": c.image_url,
            "pontos": c.pontos,
            "vitorias": c.vitorias
        })
    return jsonify(result), 200

