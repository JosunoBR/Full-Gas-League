import os

HISTORIC_HTML_CONTENT = """{% extends "base.html" %}

{% block content %}
<style>
  /* ── Variáveis de tema ── */
  :root {
    --red:    #e10600;
    --gold:   #f5c518;
    --silver: #a8a9ad;
    --bronze: #cd7f32;
    --card-bg: #111318;
    --border:  rgba(255,255,255,0.08);
  }

  /* ── Header ── */
  .historic-hero {
    background: linear-gradient(135deg, #0d0d0d 0%, #1a0a0a 50%, #0d0d0d 100%);
    border-bottom: 2px solid var(--red);
    padding: 2rem 0 1.5rem;
    margin-bottom: 2rem;
  }
  .historic-hero h1 {
    font-family: 'Cinzel', serif;
    font-size: 2rem;
    letter-spacing: 3px;
    color: #fff;
  }
  .stat-pill {
    background: rgba(255,255,255,0.06);
    border: 1px solid var(--border);
    border-radius: 50px;
    padding: .35rem 1rem;
    font-size: .8rem;
    color: rgba(255,255,255,0.6);
  }
  .stat-pill strong { color: #fff; }

  /* ── Barra de pesquisa ── */
  #search-input {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.15);
    color: #fff;
    border-radius: 50px;
    padding: .55rem 1.25rem;
    width: 100%;
    max-width: 400px;
    transition: border-color .2s;
  }
  #search-input::placeholder { color: rgba(255,255,255,0.4); }
  #search-input:focus { outline: none; border-color: var(--red); }

  /* ── Circuit card ── */
  .circuit-block {
    margin-bottom: 1.5rem;
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--border);
    background: var(--card-bg);
    transition: border-color .25s;
  }
  .circuit-block:hover { border-color: rgba(225,6,0,.4); }

  .circuit-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem 1.25rem;
    cursor: pointer;
    user-select: none;
    background: linear-gradient(90deg, rgba(225,6,0,.12) 0%, transparent 60%);
    border-bottom: 1px solid var(--border);
    transition: background .2s;
  }
  .circuit-header:hover { background: linear-gradient(90deg, rgba(225,6,0,.2) 0%, transparent 60%); }

  .circuit-icon {
    width: 44px; height: 44px;
    background: rgba(225,6,0,.15);
    border: 1px solid rgba(225,6,0,.3);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
    font-size: 1.1rem; color: var(--red);
  }
  .circuit-name {
    font-family: 'Cinzel', serif;
    font-size: .95rem;
    font-weight: 700;
    color: #fff;
    letter-spacing: 1px;
    flex: 1;
  }
  .circuit-meta { font-size: .75rem; color: rgba(255,255,255,.45); margin-top: 2px; }

  .badge-races {
    background: var(--red);
    color: #fff;
    font-size: .7rem;
    font-weight: 700;
    padding: .25rem .65rem;
    border-radius: 50px;
    white-space: nowrap;
  }

  .circuit-stats-bar {
    display: flex;
    gap: 1.5rem;
    padding: .6rem 1.25rem;
    background: rgba(0,0,0,.3);
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
  }
  .cs-item { font-size: .75rem; color: rgba(255,255,255,.5); }
  .cs-item strong { color: rgba(255,255,255,.85); }
  .cs-item .cs-icon { margin-right: .25rem; }

  .chevron {
    color: rgba(255,255,255,.4);
    transition: transform .3s;
    font-size: .8rem;
  }
  .circuit-block.open .chevron { transform: rotate(180deg); }

  /* ── Race timeline ── */
  .race-list {
    display: none;
    padding: .75rem 1rem 1rem;
  }
  .circuit-block.open .race-list { display: block; }

  .race-card {
    background: rgba(255,255,255,.03);
    border: 1px solid var(--border);
    border-radius: 10px;
    margin-bottom: .75rem;
    padding: 1rem 1.25rem;
    position: relative;
    transition: background .2s, border-color .2s;
  }
  .race-card:hover {
    background: rgba(255,255,255,.06);
    border-color: rgba(255,255,255,.15);
  }
  .race-card:last-child { margin-bottom: 0; }

  /* linha de tempo */
  .race-card::before {
    content: '';
    position: absolute;
    left: -1rem;
    top: 50%;
    transform: translateY(-50%);
    width: 8px; height: 8px;
    background: var(--red);
    border-radius: 50%;
    box-shadow: 0 0 8px rgba(225,6,0,.6);
  }

  .race-top {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: .5rem;
    margin-bottom: .75rem;
  }
  .race-gp {
    font-weight: 700;
    font-size: .95rem;
    color: #fff;
    flex: 1;
    min-width: 160px;
  }
  .race-date {
    font-size: .75rem;
    color: rgba(255,255,255,.45);
    white-space: nowrap;
  }
  .race-badge {
    font-size: .68rem;
    padding: .15rem .55rem;
    border-radius: 50px;
    background: rgba(255,255,255,.08);
    color: rgba(255,255,255,.6);
    white-space: nowrap;
  }

  /* edit btn */
  .btn-edit-race {
    display: inline-flex;
    align-items: center;
    gap: .25rem;
    background: rgba(255,255,255,.06);
    border: 1px solid var(--border);
    color: rgba(255,255,255,.5);
    border-radius: 6px;
    padding: .22rem .55rem;
    font-size: .72rem;
    text-decoration: none;
    transition: background .2s, color .2s, border-color .2s;
    white-space: nowrap;
    flex-shrink: 0;
    margin-left: auto;
  }
  .btn-edit-race:hover { background: rgba(225,6,0,.2); color: var(--red); border-color: var(--red); }

  /* pódio */
  .podium-row {
    display: flex;
    gap: .6rem;
    flex-wrap: wrap;
    margin-bottom: .6rem;
  }
  .podium-item {
    display: flex;
    align-items: center;
    gap: .4rem;
    background: rgba(255,255,255,.05);
    border-radius: 8px;
    padding: .3rem .7rem;
    font-size: .78rem;
    min-width: 110px;
  }
  .podium-item .medal { font-size: 1rem; }
  .podium-item .pilot-name { color: #fff; font-weight: 600; }
  .podium-item .pilot-name.empty { color: rgba(255,255,255,.25); font-weight: 400; }
  .p1 { border-left: 3px solid var(--gold); }
  .p2 { border-left: 3px solid var(--silver); }
  .p3 { border-left: 3px solid var(--bronze); }

  /* extras */
  .extras-row {
    display: flex;
    gap: .5rem;
    flex-wrap: wrap;
  }
  .extra-chip {
    display: flex;
    align-items: center;
    gap: .35rem;
    font-size: .72rem;
    color: rgba(255,255,255,.5);
    background: rgba(255,255,255,.04);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: .2rem .6rem;
  }
  .extra-chip i { font-size: .8rem; }
  .extra-chip span { color: rgba(255,255,255,.8); }

  /* empty state */
  .empty-state {
    text-align: center;
    padding: 4rem 1rem;
    color: rgba(255,255,255,.35);
  }
  .empty-state i { font-size: 3rem; margin-bottom: 1rem; color: rgba(255,255,255,.1); }

  /* search no-result */
  #no-result-msg {
    display: none;
    text-align: center;
    padding: 2rem;
    color: rgba(255,255,255,.35);
    font-size: .9rem;
  }
</style>

<!-- ── Hero ── -->
<div class="historic-hero">
  <div class="d-flex align-items-center justify-content-between flex-wrap gap-3">
    <div>
      <h1><i class="fa-solid fa-clock-rotate-left text-danger me-3"></i>HISTÓRICO DE CIRCUITOS</h1>
      <p class="text-white-50 mb-0 small">Todos os resultados da liga, organizados por pista.</p>
    </div>
    <div class="d-flex gap-2 flex-wrap">
      <span class="stat-pill"><strong>{{ total_circuitos }}</strong> circuito{{ 's' if total_circuitos != 1 else '' }}</span>
      <span class="stat-pill"><strong>{{ total_corridas_geral }}</strong> corrida{{ 's' if total_corridas_geral != 1 else '' }}</span>
      <a href="{{ url_for('admin.dashboard') }}" class="btn btn-outline-secondary btn-sm">
        <i class="fa-solid fa-arrow-left me-1"></i> Painel
      </a>
    </div>
  </div>
</div>

{% if historico %}
<!-- ── Barra de pesquisa ── -->
<div class="mb-4">
  <input id="search-input" type="text" placeholder="&#xf002;  Buscar circuito..." autocomplete="off">
</div>

<div id="circuit-list">
{% for circuito, dados in historico.items() %}
{% set stats = dados.stats %}
{% set corridas = dados.corridas %}

<div class="circuit-block" data-circuit="{{ circuito | lower }}">

  <!-- Header clicável -->
  <div class="circuit-header" onclick="toggleCircuit(this)">
    <div class="circuit-icon"><i class="fa-solid fa-road"></i></div>
    <div class="flex-1">
      <div class="circuit-name">{{ circuito }}</div>
      <div class="circuit-meta">
        Última corrida: {{ stats.ultima_data.strftime('%d/%m/%Y') if stats.ultima_data else '—' }}
      </div>
    </div>
    <span class="badge-races">{{ stats.total_corridas }} corrida{{ 's' if stats.total_corridas != 1 else '' }}</span>
    <i class="fa-solid fa-chevron-down chevron ms-2"></i>
  </div>

  <!-- Barra de estatísticas do circuito -->
  <div class="circuit-stats-bar">
    {% if stats.maior_vencedor %}
    <div class="cs-item">
      <i class="fa-solid fa-trophy cs-icon" style="color: var(--gold);"></i>
      Maior vencedor: <strong>{{ stats.maior_vencedor }}</strong>
      {% if stats.vitorias_lider > 1 %}<span class="ms-1 opacity-50">({{ stats.vitorias_lider }}×)</span>{% endif %}
    </div>
    {% endif %}
    {% if stats.maior_pole %}
    <div class="cs-item">
      <i class="fa-solid fa-flag-checkered cs-icon" style="color: #a78bfa;"></i>
      Mais poles: <strong>{{ stats.maior_pole }}</strong>
      {% if stats.poles_lider > 1 %}<span class="ms-1 opacity-50">({{ stats.poles_lider }}×)</span>{% endif %}
    </div>
    {% endif %}
    {% if stats.record_pilot %}
    <div class="cs-item">
      <i class="fa-solid fa-stopwatch cs-icon" style="color: #60a5fa;"></i>
      Recorde de Pole: <strong>{{ stats.record_pilot }}</strong> <span class="ms-1 text-white-50">({{ stats.record_time }})</span>
    </div>
    {% endif %}
    <div class="cs-item ms-auto">
      <i class="fa-solid fa-users cs-icon"></i>
      {{ stats.total_corridas }} edição{{ 'ões' if stats.total_corridas != 1 else '' }} nesta pista
    </div>
  </div>

  <!-- Lista de corridas (oculta por padrão) -->
  <div class="race-list" style="padding-left: 2rem;">
    {% for h in corridas %}
    <div class="race-card">
      <!-- Topo: nome + data + badges -->
      <div class="race-top">
        <div class="race-gp">{{ h.nome_gp }}</div>
        <span class="race-date">
          <i class="fa-regular fa-calendar me-1"></i>
          {{ h.data.strftime('%d/%m/%Y') if h.data else '—' }}
        </span>
        <span class="race-badge"><i class="fa-solid fa-flag me-1"></i>{{ h.season_name }}</span>
        <span class="race-badge"><i class="fa-solid fa-grip me-1"></i>{{ h.grid_name }}</span>
        {% if h.total_pilotos %}
        <span class="race-badge"><i class="fa-solid fa-users me-1"></i>{{ h.total_pilotos }} pilotos</span>
        {% endif %}
        <a href="{{ url_for('admin.race_results', race_id=h.race_id) }}" class="btn-edit-race" title="Editar">
          <i class="fa-solid fa-pen-to-square me-1"></i>Editar
        </a>
      </div>

      <!-- Pódio -->
      <div class="podium-row">
        <div class="podium-item p1">
          <span class="medal">🏆</span>
          <span class="pilot-name {% if not h.primeiro %}empty{% endif %}">
            {{ h.primeiro.nickname if h.primeiro else '—' }}
          </span>
        </div>
        <div class="podium-item p2">
          <span class="medal">🥈</span>
          <span class="pilot-name {% if not h.segundo %}empty{% endif %}">
            {{ h.segundo.nickname if h.segundo else '—' }}
          </span>
        </div>
        <div class="podium-item p3">
          <span class="medal">🥉</span>
          <span class="pilot-name {% if not h.terceiro %}empty{% endif %}">
            {{ h.terceiro.nickname if h.terceiro else '—' }}
          </span>
        </div>
      </div>

      <!-- Extras: pole, volta rápida, piloto do dia -->
      <div class="extras-row">
        {% if h.pole_sitter %}
        <div class="extra-chip">
          <i class="fa-solid fa-flag-checkered" style="color:#a78bfa;"></i>
          Pole: <span>{{ h.pole_sitter.nickname }}{% if h.pole_time %} — {{ h.pole_time }}{% endif %}</span>
        </div>
        {% endif %}
        {% if h.volta_rapida %}
        <div class="extra-chip">
          <i class="fa-solid fa-stopwatch" style="color:#60a5fa;"></i>
          VR: <span>{{ h.volta_rapida.nickname }}</span>
        </div>
        {% endif %}
        {% if h.piloto_do_dia %}
        <div class="extra-chip">
          <i class="fa-solid fa-star" style="color:var(--gold);"></i>
          Piloto do Dia: <span>{{ h.piloto_do_dia.nickname }}</span>
        </div>
        {% endif %}
      </div>
    </div>
    {% endfor %}
  </div>

</div>
{% endfor %}
</div>

<div id="no-result-msg">
  <i class="fa-solid fa-magnifying-glass fa-2x mb-2 d-block opacity-25"></i>
  Nenhum circuito encontrado para "<span id="search-term"></span>".
</div>

{% else %}
<div class="empty-state">
  <i class="fa-solid fa-inbox d-block"></i>
  <h5 class="text-white">Nenhum histórico encontrado</h5>
  <p>Ainda não há corridas concluídas com resultados registrados.</p>
</div>
{% endif %}

<script>
  function toggleCircuit(header) {
    const block = header.closest('.circuit-block');
    block.classList.toggle('open');
  }

  // Pesquisa em tempo real
  const searchInput = document.getElementById('search-input');
  const noResult    = document.getElementById('no-result-msg');
  const searchTerm  = document.getElementById('search-term');

  if (searchInput) {
    searchInput.addEventListener('input', function () {
      const q = this.value.trim().toLowerCase();
      let visible = 0;
      document.querySelectorAll('.circuit-block').forEach(block => {
        const name = block.dataset.circuit || '';
        const match = !q || name.includes(q);
        block.style.display = match ? '' : 'none';
        if (match) visible++;
      });
      if (noResult && searchTerm) {
        noResult.style.display = (visible === 0 && q) ? 'block' : 'none';
        searchTerm.textContent = this.value.trim();
      }
    });
  }
</script>
{% endblock %}
"""

ADMIN_PY_ROUTE_CODE = """
@admin_bp.route('/historic')
@login_required
def historic():
    \"\"\"
    Lê todas as corridas com resultados, agrupa por circuito e calcula
    estatísticas por pista (vencedor mais frequente, total de corridas, etc.).
    \"\"\"
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

    corridas_com_resultados = Race.query.join(RaceResult).distinct().order_by(
        Race.pista.asc(), Race.data_corrida.desc()
    ).all()

    historico_por_circuito = {}

    for race in corridas_com_resultados:
        resultados = RaceResult.query.filter_by(race_id=race.id).all()

        primeiro = next((r.pilot for r in resultados if r.posicao == 1 and not r.dsq), None)
        segundo  = next((r.pilot for r in resultados if r.posicao == 2 and not r.dsq), None)
        terceiro = next((r.pilot for r in resultados if r.posicao == 3 and not r.dsq), None)
        piloto_dia   = next((r.pilot for r in resultados if r.piloto_do_dia), None)
        volta_rapida = next((r.pilot for r in resultados if r.volta_rapida), None)

        dados_corrida = {
            'nome_gp':    race.nome_gp,
            'data':       race.data_corrida,
            'season_name': race.season.nome,
            'grid_name':  race.grid_config.nome if race.grid_config else race.grid,
            'pole_sitter': race.pole_sitter,
            'pole_time':  race.pole_time,
            'primeiro':   primeiro,
            'segundo':    segundo,
            'terceiro':   terceiro,
            'volta_rapida': volta_rapida,
            'piloto_do_dia': piloto_dia,
            'race_id':    race.id,
            'total_pilotos': len(resultados),
        }

        circuito = race.pista
        if circuito not in historico_por_circuito:
            historico_por_circuito[circuito] = {'corridas': [], 'stats': {}}
        historico_por_circuito[circuito]['corridas'].append(dados_corrida)

    # Calcula estatísticas por circuito
    for circuito, dados in historico_por_circuito.items():
        corridas = dados['corridas']
        vitorias = {}
        poles    = {}
        
        record_pilot = None
        record_time = None
        min_seconds = float('inf')
        
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
            'ultima_data':     corridas[0]['data'],   # já vem desc por data
        }

    total_corridas_geral = sum(d['stats']['total_corridas'] for d in historico_por_circuito.values())

    return render_template(
        'admin/historic.html',
        historico=historico_por_circuito,
        total_circuitos=len(historico_por_circuito),
        total_corridas_geral=total_corridas_geral,
    )
"""

def restore_dashboard_card():
    path = os.path.join('app', 'templates', 'admin', 'dashboard.html')
    if not os.path.exists(path):
        print("Erro: dashboard.html não encontrado localmente.")
        return False
        
    print("Atualizando dashboard.html...")
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if 'admin.historic' in content:
        print("-> Card do histórico já existe no dashboard.html.")
        return True
        
    seasons_card_end = """                <div class="d-grid mt-3">
                    <a href="{{ url_for('admin.seasons') }}" class="btn btn-outline-danger btn-sm text-white">CALENDÁRIO</a>
                </div>
            </div>
        </div>
    </div>"""

    historic_card = """                <div class="d-grid mt-3">
                    <a href="{{ url_for('admin.seasons') }}" class="btn btn-outline-danger btn-sm text-white">CALENDÁRIO</a>
                </div>
            </div>
        </div>
    </div>

    <div class="col-md-4 col-lg-3">
        <div class="card shadow border-silver h-100 bg-dark hover-effect">
            <div class="card-body text-center p-4">
                <i class="fa-solid fa-clock-rotate-left fa-3x text-danger mb-3"></i>
                <h5 class="card-title text-white fw-bold">Histórico</h5>
                <p class="card-text text-white-50 small">Histórico de circuitos, poles, vitórias e recordes.</p>
                <div class="d-grid mt-3">
                    <a href="{{ url_for('admin.historic') }}" class="btn btn-outline-danger btn-sm text-white fw-bold">VER HISTÓRICO</a>
                </div>
            </div>
        </div>
    </div>"""

    if seasons_card_end in content:
        content = content.replace(seasons_card_end, historic_card)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("-> Card de Histórico adicionado com sucesso no dashboard.html!")
        return True
    else:
        print("-> [FALHA] Não foi possível encontrar a tag correta para injetar o card no dashboard.")
        return False

def restore_base_html_link():
    path = os.path.join('app', 'templates', 'base.html')
    if not os.path.exists(path):
        print("Erro: base.html não encontrado localmente.")
        return False
        
    print("Atualizando base.html...")
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if 'admin.historic' in content:
        print("-> Link do histórico já existe no base.html.")
        return True
        
    target_menu_item = """<li><a class="dropdown-item" href="{{ url_for('admin.list_teams') }}">Equipes</a></li> <li><a class="dropdown-item" href="{{ url_for('admin.seasons') }}">Temporadas</a></li>"""
    replacement_menu_item = """<li><a class="dropdown-item" href="{{ url_for('admin.list_teams') }}">Equipes</a></li> <li><a class="dropdown-item" href="{{ url_for('admin.seasons') }}">Temporadas</a></li>
                                <li><a class="dropdown-item" href="{{ url_for('admin.historic') }}">Histórico de Corridas</a></li>"""
                                
    if target_menu_item in content:
        content = content.replace(target_menu_item, replacement_menu_item)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("-> Link do Histórico adicionado com sucesso no menu superior de base.html!")
        return True
    else:
        # Busca sem espaço
        alt_target = """<li><a class="dropdown-item" href="{{ url_for('admin.list_teams') }}">Equipes</a></li><li><a class="dropdown-item" href="{{ url_for('admin.seasons') }}">Temporadas</a></li>"""
        if alt_target in content:
            content = content.replace(alt_target, replacement_menu_item)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            print("-> Link do Histórico adicionado no base.html usando fallback.")
            return True
        else:
            print("-> [FALHA] Não foi possível encontrar o menu dropdown de gestão no base.html.")
            return False

def restore_admin_route():
    path = os.path.join('app', 'routes', 'admin.py')
    if not os.path.exists(path):
        print("Erro: admin.py não encontrado localmente.")
        return False
        
    print("Atualizando admin.py...")
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if 'def historic()' in content:
        print("-> Rota historic() já existe no admin.py.")
        return True
        
    target_marker = "@admin_bp.route('/manual')"
    if target_marker in content:
        replacement = ADMIN_PY_ROUTE_CODE + "\n" + target_marker
        content = content.replace(target_marker, replacement, 1)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("-> Rota /historic injetada com sucesso em admin.py!")
        return True
    else:
        print("-> [FALHA] Não foi possível encontrar '@admin_bp.route('/manual')' em admin.py.")
        return False

def write_historic_html():
    path = os.path.join('app', 'templates', 'admin', 'historic.html')
    print(f"Escrevendo template em {path}...")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(HISTORIC_HTML_CONTENT)
    print("-> historic.html escrito com sucesso!")
    return True

if __name__ == '__main__':
    write_historic_html()
    ok_dash = restore_dashboard_card()
    ok_base = restore_base_html_link()
    ok_route = restore_admin_route()
    
    if ok_dash and ok_base and ok_route:
        print("\n=== TODOS OS ARQUIVOS FORAM RESTAURADOS COM SUCESSO NO PC LOCAL! ===")
        print("Agora você pode commitar, enviar para o GitHub e atualizar no servidor.")
    else:
        print("\n=== ALERTA: Alguns arquivos não puderam ser restaurados automaticamente ===")
