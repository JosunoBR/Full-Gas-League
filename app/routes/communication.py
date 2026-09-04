from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app.models import db, User, PilotProfile, GridConfig, Season
from app.services.email_service import EmailService

communication_bp = Blueprint('communication', __name__)


def check_admin_permission():
    """Valida se o usuário tem permissão de administrador."""
    return current_user.is_authenticated and current_user.role in ['SUPER_ADM', 'ADM']


@communication_bp.before_request
def restrict_to_admin():
    if not current_user.is_authenticated:
        return redirect(url_for('public.login'))
    if not check_admin_permission():
        flash("Acesso restrito à Direção e Administradores da FullGas League.", "danger")
        return redirect(url_for('public.index'))


@communication_bp.route('/')
@login_required
def index():
    """
    Tela Principal da Central de Comunicação da FullGas League.
    """
    # Carrega grids ativos
    grids = GridConfig.query.order_by(GridConfig.ordem).all()

    # Carrega todos os pilotos com perfil e usuário válido
    pilotos = PilotProfile.query.join(User).filter(
        User.email.isnot(None),
        User.email != ''
    ).order_by(PilotProfile.nickname).all()

    # Estatísticas rápidas
    total_pilotos = PilotProfile.query.count()
    total_com_email = len([p for p in pilotos if p.user and '@' in (p.user.email or '')])
    
    is_resend_active = EmailService.is_configured()

    return render_template(
        'admin/communication.html',
        grids=grids,
        pilotos=pilotos,
        total_pilotos=total_pilotos,
        total_com_email=total_com_email,
        is_resend_active=is_resend_active
    )


@communication_bp.route('/destinatarios', methods=['GET'])
@login_required
def get_destinatarios():
    """
    Endpoint JSON reativo para atualizar o contador e a lista de pilotos
    ao alterar os filtros de envio (Todos, Por Grid ou Piloto Individual).
    """
    tipo = request.args.get('tipo', 'todos')
    grid_id = request.args.get('grid_id', type=int)
    piloto_id = request.args.get('piloto_id', type=int)

    query = PilotProfile.query.join(User).filter(
        User.email.isnot(None),
        User.email != ''
    )

    if tipo == 'grid' and grid_id:
        # Piloto com grid configurado (campo grid ou relação)
        query = query.filter(PilotProfile.grid.contains(str(grid_id)))
    elif tipo == 'piloto' and piloto_id:
        query = query.filter(PilotProfile.id == piloto_id)

    pilotos_filtrados = query.order_by(PilotProfile.nickname).all()

    destinatarios = []
    for p in pilotos_filtrados:
        email = (p.user.email or '').strip()
        if email and '@' in email:
            destinatarios.append({
                'id': p.id,
                'nickname': p.nickname,
                'email': email
            })

    return jsonify({
        'total': len(destinatarios),
        'destinatarios': destinatarios
    })


def format_natural_text_to_html(text_content):
    """
    Converte texto digitado naturalmente pelo usuário em parágrafos e
    blocos elegantes para o e-mail oficial, sem exigir digitação de tags HTML.
    """
    if not text_content:
        return ""

    # Se o texto já contiver tags completas, preserva
    if "<p>" in text_content or "<div>" in text_content or "<table>" in text_content:
        return text_content

    paragraphs = text_content.strip().split('\n\n')
    html_parts = []

    for p in paragraphs:
        p = p.strip()
        if not p:
            continue

        lines = p.split('\n')
        # Lista com marcadores (•, -, *)
        if all(line.strip().startswith(('•', '-', '*')) for line in lines if line.strip()):
            items = "".join(f"<li style='margin-bottom: 6px;'>{line.strip().lstrip('•-* ')}</li>" for line in lines if line.strip())
            html_parts.append(f"<ul style='color: #c9d1d9; padding-left: 20px; line-height: 1.6;'>{items}</ul>")
        # Bloco de destaque (📌, ⚠️, 🚨, ℹ️)
        elif any(line.strip().startswith(('📌', '⚠️', '🚨', 'ℹ️')) for line in lines):
            formatted_box = "<br>".join(line.strip() for line in lines if line.strip())
            html_parts.append(f"<div class='info-box'><p style='margin: 0; font-size: 14px; line-height: 1.6;'>{formatted_box}</p></div>")
        else:
            formatted_lines = "<br>".join(lines)
            html_parts.append(f"<p style='margin-bottom: 16px; line-height: 1.6;'>{formatted_lines}</p>")

    return "".join(html_parts)


@communication_bp.route('/preview', methods=['POST'])
@login_required
def preview_email():
    """
    Renderiza o HTML oficial do e-mail para exibição no modal de Live Preview.
    """
    subject = request.form.get('assunto', 'Comunicado Oficial FullGas League')
    category = request.form.get('categoria', 'COMUNICADO OFICIAL')
    raw_message = request.form.get('mensagem', 'Insira a mensagem do comunicado...')
    message_content = format_natural_text_to_html(raw_message)

    host_url = request.host_url.rstrip('/') if request.host_url else current_app.config.get('BASE_URL')

    rendered_html = render_template(
        'emails/broadcast_email.html',
        subject=subject,
        category=category,
        message_content=message_content,
        base_url=host_url,
        instagram_url=current_app.config.get('INSTAGRAM_URL'),
        youtube_url=current_app.config.get('YOUTUBE_URL')
    )

    return jsonify({'html': rendered_html})


@communication_bp.route('/enviar', methods=['POST'])
@login_required
def send_broadcast():
    """
    Processa o disparo de e-mails para os destinatários selecionados.
    """
    tipo_destinatario = request.form.get('tipo_destinatario', 'todos')
    grid_id = request.form.get('grid_id', type=int)
    piloto_id = request.form.get('piloto_id', type=int)

    assunto = (request.form.get('assunto') or '').strip()
    categoria = request.form.get('categoria', 'COMUNICADO OFICIAL')
    mensagem = (request.form.get('mensagem') or '').strip()

    if not assunto or not mensagem:
        flash("Por favor, preencha o assunto e a mensagem do comunicado.", "warning")
        return redirect(url_for('communication.index'))

    # Coleta os e-mails
    query = PilotProfile.query.join(User).filter(
        User.email.isnot(None),
        User.email != ''
    )

    if tipo_destinatario == 'grid' and grid_id:
        query = query.filter(PilotProfile.grid.contains(str(grid_id)))
        alvo_desc = f"pilotos do Grid selecionado"
    elif tipo_destinatario == 'piloto' and piloto_id:
        query = query.filter(PilotProfile.id == piloto_id)
        alvo_desc = "piloto selecionado"
    else:
        alvo_desc = "todos os pilotos cadastrados"

    pilotos = query.all()
    emails = [p.user.email.strip() for p in pilotos if p.user and p.user.email and '@' in p.user.email]

    if not emails:
        flash("Nenhum piloto com e-mail válido foi encontrado no filtro selecionado.", "danger")
        return redirect(url_for('communication.index'))

    # Formata texto natural em HTML limpo
    mensagem_html = format_natural_text_to_html(mensagem)

    # Dispara via EmailService
    total_enviados = EmailService.send_custom_broadcast(
        subject=assunto,
        recipients=emails,
        message_html=mensagem_html,
        category=categoria
    )

    is_active = EmailService.is_configured()
    if is_active:
        flash(f"✅ Sucesso! Comunicado disparado para {total_enviados} {alvo_desc}.", "success")
    else:
        flash(
            f"ℹ️ Modo Simulação Ativo: {total_enviados} e-mail(s) preparados e validados para {alvo_desc}. "
            f"Adicione a chave RESEND_API_KEY no arquivo .env para envio real aos pilotos.",
            "info"
        )

    return redirect(url_for('communication.index'))
