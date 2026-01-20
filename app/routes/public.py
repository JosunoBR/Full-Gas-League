import os
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import check_password_hash
from app.models import db, Season, Race, PilotProfile, Protesto, RaceResult, VotoComissario, Team, RaceRegistration, User, Invite, News
from app.utils import allowed_file, get_embed_url, ORDEM_CARROS

public_bp = Blueprint('public', __name__)

# --- ROTAS PRINCIPAIS (HOME E LOGIN) ---

@public_bp.route('/')
def home():
    season_ativa = Season.query.filter_by(ativa=True).first()
    standings = { 'ELITE': [], 'ADVANCED': [], 'INITIAL': [] }
    constructors = { 'ELITE': [], 'ADVANCED': [], 'INITIAL': [] }
    calendar = { 'ELITE': [], 'ADVANCED': [], 'INITIAL': [] }
    last_races = { 'ELITE': None, 'ADVANCED': None, 'INITIAL': None }
    noticias = News.query.order_by(News.data_publicacao.desc()).limit(5).all()
    pilots_by_grid = { 'ELITE': [], 'ADVANCED': [], 'INITIAL': [] }
    
    if season_ativa:
        # 1. Calcular Pontos dos Pilotos
        pilotos = PilotProfile.query.join(User).all()
        for p in pilotos:
            if p.grid in standings:
                resultados = [r for r in p.race_results if r.race.season_id == season_ativa.id]
                pontos_totais = sum(r.pontos_ganhos for r in resultados)
                vitorias = sum(1 for r in resultados if r.posicao == 1 and not r.dsq)
                # Adiciona placeholder para o carro
                standings[p.grid].append({'piloto': p, 'pontos': pontos_totais, 'vitorias': vitorias, 'carro': ''})
        
        # 2. Ordenar e Aplicar Lastro (Carro)
        for grid in standings: 
            standings[grid].sort(key=lambda x: x['pontos'], reverse=True)
            
            # Distribui os carros baseados na posição
            for i, item in enumerate(standings[grid]):
                if i < len(ORDEM_CARROS):
                    item['carro'] = ORDEM_CARROS[i]
                else:
                    item['carro'] = "McLaren (Extra)"

        # 3. Calcular Construtores
        teams = Team.query.filter_by(ativa=True).all()
        for t in teams:
            if t.grid in constructors:
                resultados_equipe = RaceResult.query.join(Race).filter(
                    RaceResult.team_id == t.id,
                    Race.season_id == season_ativa.id
                ).all()
                pts_equipe = sum(r.pontos_ganhos for r in resultados_equipe)
                vitorias_equipe = sum(1 for r in resultados_equipe if r.posicao == 1 and not r.dsq)
                constructors[t.grid].append({'equipe': t, 'pontos': pts_equipe, 'vitorias': vitorias_equipe})
        
        for grid in constructors: constructors[grid].sort(key=lambda x: x['pontos'], reverse=True)
        
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
        pilots_query = PilotProfile.query.join(User).filter(PilotProfile.grid.in_(['ELITE', 'ADVANCED', 'INITIAL'])).order_by(PilotProfile.nickname).all()
        for p in pilots_query:
            if p.grid in pilots_by_grid:
                pilots_by_grid[p.grid].append(p)

    return render_template('home.html', standings=standings, constructors=constructors, calendar=calendar, last_races=last_races, season_ativa=season_ativa, noticias=noticias, pilots_by_grid=pilots_by_grid)

@public_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'PILOTO':
            return redirect(url_for('public.my_profile'))
        elif current_user.role in ['SUPER_ADM', 'ADM']:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('public.home'))

    if request.method == 'POST':
        email = request.form.get('email')
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
        email = request.form.get('email')
        nickname = request.form.get('nickname')
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
        
        new_user = User(email=email, username=nickname, role='PILOTO')
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
    return render_template('regulamento.html')

@public_bp.route('/transparencia')
def transparency():
    return render_template('public/how_it_works.html')

# --- PERFIL DO PILOTO ---

@public_bp.route('/piloto/<int:pilot_id>')
def public_profile(pilot_id):
    perfil = PilotProfile.query.get_or_404(pilot_id)
    
    # Se for o próprio dono vendo seu perfil público, redireciona para o privado (com controles)
    if current_user.is_authenticated and current_user.pilot_profile and current_user.pilot_profile.id == perfil.id:
        return redirect(url_for('public.my_profile'))

    season_ativa = Season.query.filter_by(ativa=True).first()
    
    # Estatísticas da Temporada
    meus_pontos_camp = 0
    desempenho_temporada = []
    if season_ativa:
        meus_pontos_camp = sum(r.pontos_ganhos for r in perfil.race_results if r.race.season_id == season_ativa.id)
        corridas = Race.query.filter_by(season_id=season_ativa.id, grid=perfil.grid).order_by(Race.data_corrida).all()
        for race in corridas:
            resultado = next((r for r in race.results if r.pilot_id == perfil.id), None)
            desempenho_temporada.append({
                'gp': race.nome_gp, 'data': race.data_corrida, 'status_corrida': race.status,
                'participou': True if resultado and not resultado.ausencia else False,
                'posicao': resultado.posicao if resultado else 0,
                'pontos': resultado.pontos_ganhos if resultado else 0,
                'dnf': resultado.dnf if resultado else False, 'dsq': resultado.dsq if resultado else False
            })

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
                           registro_atual=None)

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

    season_ativa = Season.query.filter_by(ativa=True).first()
    
    if perfil.esta_banido():
        flash('ALERTA: Sua CNH está zerada ou negativa. Você está suspenso das atividades de pista.', 'danger')
    
    checkin_race = None
    registro_atual = None
    
    # Lógica de Check-in
    if season_ativa:
        hoje = datetime.utcnow().date()
        corridas_futuras = Race.query.filter(
            Race.season_id == season_ativa.id,
            Race.grid == perfil.grid,
            Race.status != 'Concluida',
            Race.data_corrida >= hoje
        ).order_by(Race.data_corrida).all()
        
        if corridas_futuras:
            proxima = corridas_futuras[0]
            if proxima.data_corrida and (proxima.data_corrida - hoje).days <= 2: 
                checkin_race = proxima
                registro_atual = RaceRegistration.query.filter_by(race_id=proxima.id, pilot_id=perfil.id).first()

    # Estatísticas da Temporada
    meus_pontos_camp = 0
    desempenho_temporada = []
    if season_ativa:
        meus_pontos_camp = sum(r.pontos_ganhos for r in perfil.race_results if r.race.season_id == season_ativa.id)
        corridas = Race.query.filter_by(season_id=season_ativa.id, grid=perfil.grid).order_by(Race.data_corrida).all()
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
    defesas_pendentes = Protesto.query.filter_by(acusado_id=perfil.id, status='AGUARDANDO_DEFESA').all()
    
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
                           registro_atual=registro_atual)

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
    season_ativa = Season.query.filter_by(ativa=True).first()
    total_pontos = 0
    total_vitorias = 0
    stats_pilotos = []
    if season_ativa:
        for piloto in team.pilots:
            pts = sum(r.pontos_ganhos for r in piloto.race_results if r.race.season_id == season_ativa.id)
            wins = sum(1 for r in piloto.race_results if r.race.season_id == season_ativa.id and r.posicao == 1 and not r.dsq)
            stats_pilotos.append({'piloto': piloto, 'pontos': pts, 'vitorias': wins})
        results_team = RaceResult.query.join(Race).filter(RaceResult.team_id == team.id, Race.season_id == season_ativa.id).all()
        total_pontos = sum(r.pontos_ganhos for r in results_team)
        total_vitorias = sum(1 for r in results_team if r.posicao == 1 and not r.dsq)
    return render_template('public/team_profile.html', team=team, total_pontos=total_pontos, total_vitorias=total_vitorias, stats_pilotos=stats_pilotos)

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
    current_user.pilot_profile.nome_real = request.form.get('nome_real')[:100]
    current_user.pilot_profile.nickname = request.form.get('nickname')[:50]
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
    season_ativa = Season.query.filter_by(ativa=True).first()
    races = Race.query.filter_by(season_id=season_ativa.id).all() if season_ativa else []
    pilots = PilotProfile.query.filter(PilotProfile.id != current_user.pilot_profile.id).order_by(PilotProfile.nickname).all()
    return render_template('pilot/protest.html', races=races, pilots=pilots)