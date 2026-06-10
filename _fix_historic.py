"""
Passo 3: Atualizar rota /historic em admin.py
Passo 4: Atualizar template historic.html com dados dinâmicos
"""
import os

# =============================================
# PASSO 3: Atualizar a rota em admin.py
# =============================================
admin_path = os.path.join('app', 'routes', 'admin.py')

with open(admin_path, 'r', encoding='utf-8') as f:
    admin_content = f.read()

# 3a. Garantir que CircuitHistory está importado
if 'CircuitHistory' not in admin_content:
    # Adiciona ao import existente de models
    old_import = "from app.models import db, User, PilotProfile, Season, Race, RaceResult, Invite, Protesto, VotoComissario, Team, RaceRegistration, SeletivaEntry, News, GridConfig, SeasonChampion, PilotGridPhoto, HomeCache"
    new_import = "from app.models import db, User, PilotProfile, Season, Race, RaceResult, Invite, Protesto, VotoComissario, Team, RaceRegistration, SeletivaEntry, News, GridConfig, SeasonChampion, PilotGridPhoto, HomeCache, CircuitHistory"
    
    if old_import in admin_content:
        admin_content = admin_content.replace(old_import, new_import, 1)
        print("PASSO 3a: CircuitHistory adicionado ao import")
    else:
        print("AVISO 3a: Import padrao nao encontrado. Verificando alternativas...")
        # Tenta um import parcial
        if "from app.models import" in admin_content and "HomeCache" in admin_content:
            admin_content = admin_content.replace("HomeCache", "HomeCache, CircuitHistory", 1)
            print("PASSO 3a: CircuitHistory adicionado (alternativo)")
        else:
            print("ERRO 3a: Nao consegui adicionar CircuitHistory ao import!")
else:
    print("PASSO 3a: CircuitHistory ja esta importado")

# 3b. Atualizar a rota historic()
old_route = """@admin_bp.route('/historic')
def historic():
    return render_template('admin/historic.html')"""

new_route = """@admin_bp.route('/historic')
@login_required
def historic():
    historico = CircuitHistory.query.order_by(CircuitHistory.data.desc()).all()
    pilotos = PilotProfile.query.order_by(PilotProfile.nickname).all()
    return render_template('admin/historic.html', historico=historico, pilotos=pilotos)"""

if old_route in admin_content:
    admin_content = admin_content.replace(old_route, new_route, 1)
    print("PASSO 3b: Rota historic() atualizada com query e login_required")
else:
    print("AVISO 3b: Rota original nao encontrada exatamente. Tentando variacao...")
    # Tenta sem login_required
    old_route2 = "@admin_bp.route('/historic')\ndef historic():\n    return render_template('admin/historic.html')"
    if old_route2 in admin_content:
        admin_content = admin_content.replace(old_route2, new_route, 1)
        print("PASSO 3b: Rota historic() atualizada (variacao)")
    else:
        print("ERRO 3b: Nao encontrei a rota historic() para atualizar!")

with open(admin_path, 'w', encoding='utf-8') as f:
    f.write(admin_content)
print("PASSO 3: admin.py salvo com sucesso!")

# =============================================
# PASSO 3c: Adicionar rota para CRIAR histórico
# =============================================
with open(admin_path, 'r', encoding='utf-8') as f:
    admin_content = f.read()

if "def create_historic" not in admin_content:
    # Adiciona a rota de criação logo após a rota historic
    create_route = """

@admin_bp.route('/historic/add', methods=['GET', 'POST'])
@login_required
def create_historic():
    if request.method == 'POST':
        from datetime import datetime as dt
        circuito = request.form.get('circuito', '').strip()
        data_str = request.form.get('data', '').strip()
        pole_id = request.form.get('pole_position_id', type=int)
        tempo_pole = request.form.get('tempo_pole', '').strip() or None
        primeiro_id = request.form.get('primeiro_id', type=int)
        segundo_id = request.form.get('segundo_id', type=int)
        terceiro_id = request.form.get('terceiro_id', type=int)
        melhor_tempo = request.form.get('melhor_tempo_pista', '').strip() or None
        piloto_dia_id = request.form.get('piloto_do_dia_id', type=int)

        if not circuito or not data_str:
            flash('Circuito e Data são obrigatórios.', 'danger')
            return redirect(url_for('admin.historic'))

        try:
            data_corrida = dt.strptime(data_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Data inválida.', 'danger')
            return redirect(url_for('admin.historic'))

        novo = CircuitHistory(
            circuito=circuito,
            data=data_corrida,
            pole_position_id=pole_id or None,
            tempo_pole=tempo_pole,
            primeiro_id=primeiro_id or None,
            segundo_id=segundo_id or None,
            terceiro_id=terceiro_id or None,
            melhor_tempo_pista=melhor_tempo,
            piloto_do_dia_id=piloto_dia_id or None
        )
        db.session.add(novo)
        db.session.commit()
        flash(f'Histórico do {circuito} adicionado com sucesso!', 'success')
        return redirect(url_for('admin.historic'))

    pilotos = PilotProfile.query.order_by(PilotProfile.nickname).all()
    return render_template('admin/historic.html', historico=CircuitHistory.query.order_by(CircuitHistory.data.desc()).all(), pilotos=pilotos, show_form=True)"""

    # Insere após a rota historic()
    marker = "    return render_template('admin/historic.html', historico=historico, pilotos=pilotos)"
    if marker in admin_content:
        admin_content = admin_content.replace(marker, marker + create_route, 1)
        with open(admin_path, 'w', encoding='utf-8') as f:
            f.write(admin_content)
        print("PASSO 3c: Rota create_historic() adicionada!")
    else:
        print("AVISO 3c: Nao encontrei o marcador para inserir create_historic")
else:
    print("PASSO 3c: create_historic ja existe")

# =============================================
# PASSO 3d: Adicionar rota para DELETAR histórico
# =============================================
with open(admin_path, 'r', encoding='utf-8') as f:
    admin_content = f.read()

if "def delete_historic" not in admin_content:
    delete_route = """

@admin_bp.route('/historic/delete/<int:item_id>', methods=['POST'])
@login_required
def delete_historic(item_id):
    item = CircuitHistory.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash(f'Registro do {item.circuito} removido.', 'warning')
    return redirect(url_for('admin.historic'))"""

    # Insere após create_historic
    if "def create_historic" in admin_content:
        # Find end of create_historic function
        marker2 = "    return render_template('admin/historic.html', historico=CircuitHistory.query.order_by(CircuitHistory.data.desc()).all(), pilotos=pilotos, show_form=True)"
        if marker2 in admin_content:
            admin_content = admin_content.replace(marker2, marker2 + delete_route, 1)
            with open(admin_path, 'w', encoding='utf-8') as f:
                f.write(admin_content)
            print("PASSO 3d: Rota delete_historic() adicionada!")
        else:
            print("AVISO 3d: Marcador para delete nao encontrado")
    else:
        print("AVISO 3d: create_historic nao encontrado")
else:
    print("PASSO 3d: delete_historic ja existe")


# =============================================
# PASSO 4: Atualizar o template historic.html
# =============================================
template_path = os.path.join('app', 'templates', 'admin', 'historic.html')

new_template = r"""{% extends "base.html" %}

{% block content %}
<div class="row mb-4">
    <div class="col-12 d-flex justify-content-between align-items-center flex-wrap gap-2">
        <div>
            <h2 class="text-white fw-bold" style="font-family: 'Cinzel', serif;">
                <i class="fa-solid fa-clock-rotate-left text-danger me-2"></i>HISTÓRICO DE CIRCUITO
            </h2>
            <p class="text-white-50 mb-0">Confira o histórico completo de resultados de cada circuito.</p>
        </div>
        <div class="d-flex gap-2">
            <a href="{{ url_for('admin.dashboard') }}" class="btn btn-outline-light btn-sm">
                <i class="fa-solid fa-arrow-left me-1"></i> Voltar ao Painel
            </a>
            <a href="{{ url_for('admin.create_historic') }}" class="btn btn-danger btn-sm">
                <i class="fa-solid fa-plus me-1"></i> Novo Registro
            </a>
        </div>
    </div>
</div>

{% with messages = get_flashed_messages(with_categories=true) %}
{% if messages %}
<div class="row mb-3">
    <div class="col-12">
        {% for category, message in messages %}
        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
            {{ message }}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
        {% endfor %}
    </div>
</div>
{% endif %}
{% endwith %}

<!-- FORMULÁRIO DE CADASTRO (exibido apenas quando show_form=True) -->
{% if show_form %}
<div class="card shadow border-silver bg-dark mb-4">
    <div class="card-header bg-dark border-secondary">
        <h5 class="text-white mb-0 fw-bold"><i class="fa-solid fa-plus-circle text-success me-2"></i>Novo Registro de Circuito</h5>
    </div>
    <div class="card-body p-4">
        <form method="POST" action="{{ url_for('admin.create_historic') }}">
            <div class="row g-3">
                <div class="col-md-6">
                    <label class="form-label text-white fw-bold">Circuito *</label>
                    <input type="text" name="circuito" class="form-control bg-dark text-white border-secondary" placeholder="Ex: GP do Bahrein" required>
                </div>
                <div class="col-md-3">
                    <label class="form-label text-white fw-bold">Data *</label>
                    <input type="date" name="data" class="form-control bg-dark text-white border-secondary" required>
                </div>
                <div class="col-md-3">
                    <label class="form-label text-white fw-bold">Tempo da Pole</label>
                    <input type="text" name="tempo_pole" class="form-control bg-dark text-white border-secondary" placeholder="Ex: 1:32.450">
                </div>
                <div class="col-md-4">
                    <label class="form-label text-white fw-bold">Pole Position</label>
                    <select name="pole_position_id" class="form-select bg-dark text-white border-secondary">
                        <option value="">-- Selecionar --</option>
                        {% for p in pilotos %}
                        <option value="{{ p.id }}">{{ p.nickname }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="col-md-4">
                    <label class="form-label text-white fw-bold">1º Lugar</label>
                    <select name="primeiro_id" class="form-select bg-dark text-white border-secondary">
                        <option value="">-- Selecionar --</option>
                        {% for p in pilotos %}
                        <option value="{{ p.id }}">{{ p.nickname }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="col-md-4">
                    <label class="form-label text-white fw-bold">2º Lugar</label>
                    <select name="segundo_id" class="form-select bg-dark text-white border-secondary">
                        <option value="">-- Selecionar --</option>
                        {% for p in pilotos %}
                        <option value="{{ p.id }}">{{ p.nickname }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="col-md-4">
                    <label class="form-label text-white fw-bold">3º Lugar</label>
                    <select name="terceiro_id" class="form-select bg-dark text-white border-secondary">
                        <option value="">-- Selecionar --</option>
                        {% for p in pilotos %}
                        <option value="{{ p.id }}">{{ p.nickname }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="col-md-4">
                    <label class="form-label text-white fw-bold">Melhor Tempo da Pista</label>
                    <input type="text" name="melhor_tempo_pista" class="form-control bg-dark text-white border-secondary" placeholder="Ex: 1:34.120">
                </div>
                <div class="col-md-4">
                    <label class="form-label text-white fw-bold">Piloto do Dia</label>
                    <select name="piloto_do_dia_id" class="form-select bg-dark text-white border-secondary">
                        <option value="">-- Selecionar --</option>
                        {% for p in pilotos %}
                        <option value="{{ p.id }}">{{ p.nickname }}</option>
                        {% endfor %}
                    </select>
                </div>
            </div>
            <div class="mt-4 d-flex gap-2">
                <button type="submit" class="btn btn-success fw-bold">
                    <i class="fa-solid fa-save me-1"></i> Salvar
                </button>
                <a href="{{ url_for('admin.historic') }}" class="btn btn-outline-secondary">Cancelar</a>
            </div>
        </form>
    </div>
</div>
{% endif %}

<!-- TABELA DE HISTÓRICO -->
<div class="card shadow border-silver bg-dark mb-4">
    <div class="card-body p-4">
        <div class="table-responsive">
            <table class="table table-dark table-hover table-striped align-middle mb-0">
                <thead>
                    <tr class="text-danger border-bottom border-danger">
                        <th>Circuito</th>
                        <th>Data</th>
                        <th>Pole Position</th>
                        <th>Tempo da Pole</th>
                        <th><i class="fa-solid fa-trophy text-warning me-1"></i>1º</th>
                        <th><i class="fa-solid fa-medal me-1" style="color: silver;"></i>2º</th>
                        <th><i class="fa-solid fa-medal me-1" style="color: #cd7f32;"></i>3º</th>
                        <th>Melhor Tempo</th>
                        <th><i class="fa-solid fa-star text-info me-1"></i>Piloto do Dia</th>
                        <th class="text-center">Ações</th>
                    </tr>
                </thead>
                <tbody>
                    {% for h in historico %}
                    <tr>
                        <td class="fw-bold text-white">{{ h.circuito }}</td>
                        <td class="text-white-50">{{ h.data.strftime('%d/%m/%Y') }}</td>
                        <td>{{ h.pole_position.nickname if h.pole_position else '-' }}</td>
                        <td class="text-info">{{ h.tempo_pole or '-' }}</td>
                        <td class="fw-bold text-warning">{{ h.primeiro.nickname if h.primeiro else '-' }}</td>
                        <td>{{ h.segundo.nickname if h.segundo else '-' }}</td>
                        <td>{{ h.terceiro.nickname if h.terceiro else '-' }}</td>
                        <td class="text-info">{{ h.melhor_tempo_pista or '-' }}</td>
                        <td>{{ h.piloto_do_dia.nickname if h.piloto_do_dia else '-' }}</td>
                        <td class="text-center">
                            <form method="POST" action="{{ url_for('admin.delete_historic', item_id=h.id) }}" 
                                  onsubmit="return confirm('Tem certeza que deseja remover este registro?');" class="d-inline">
                                <button type="submit" class="btn btn-sm btn-outline-danger" title="Remover">
                                    <i class="fa-solid fa-trash"></i>
                                </button>
                            </form>
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="10" class="text-center py-4 text-white-50">
                            <i class="fa-solid fa-inbox fa-2x mb-2 d-block"></i>
                            Nenhum histórico registrado. Clique em <strong>"Novo Registro"</strong> para adicionar.
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>
{% endblock %}
"""

with open(template_path, 'w', encoding='utf-8') as f:
    f.write(new_template)
print("\nPASSO 4: Template historic.html atualizado com sucesso!")
print("\n=== CONCLUIDO! ===")
print("Acesse: http://127.0.0.1:5000/admin/historic")
