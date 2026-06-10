import os

def fix_edit_button():
    path = os.path.join('app', 'templates', 'admin', 'historic.html')
    if not os.path.exists(path):
        print(f"ERRO: {path} não encontrado no computador local.")
        return False
        
    print(f"Lendo {path}...")
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 1. Substituir o estilo CSS do botão de editar
    old_css = """  /* edit btn */
  .btn-edit-race {
    position: absolute;
    top: .75rem; right: .75rem;
    background: rgba(255,255,255,.06);
    border: 1px solid var(--border);
    color: rgba(255,255,255,.5);
    border-radius: 6px;
    padding: .2rem .5rem;
    font-size: .72rem;
    text-decoration: none;
    transition: background .2s, color .2s;
  }
  .btn-edit-race:hover { background: rgba(225,6,0,.2); color: var(--red); border-color: var(--red); }"""

    new_css = """  /* edit btn */
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
  .btn-edit-race:hover { background: rgba(225,6,0,.2); color: var(--red); border-color: var(--red); }"""

    if old_css in content:
        content = content.replace(old_css, new_css)
        print("-> CSS do botão de editar atualizado.")
    else:
        # Tenta uma busca mais flexível
        print("-> Estilo CSS exato não encontrado. Verificando se já foi alterado.")

    # 2. Mover o botão editar para dentro do .race-top
    old_html_block = """    <div class="race-card">
      <a href="{{ url_for('admin.race_results', race_id=h.race_id) }}" class="btn-edit-race" title="Editar">
        <i class="fa-solid fa-pen-to-square me-1"></i>Editar
      </a>

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
      </div>"""

    new_html_block = """    <div class="race-card">
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
      </div>"""

    if old_html_block in content:
        content = content.replace(old_html_block, new_html_block)
        print("-> Estrutura HTML do botão de editar reposicionada com sucesso!")
    else:
        # Tenta uma variação com espaçamentos ligeiramente diferentes
        # Remove espaços extras para comparar
        print("-> Bloco HTML exato não encontrado. Tentando substituição secundária...")
        
        # Uma busca alternativa pelo botão editar absoluto seguido de race-top
        alt_pattern = """      <a href="{{ url_for('admin.race_results', race_id=h.race_id) }}" class="btn-edit-race" title="Editar">
        <i class="fa-solid fa-pen-to-square me-1"></i>Editar
      </a>"""
      
        if alt_pattern in content:
            # Remove o botão do topo absoluto
            content = content.replace(alt_pattern, "")
            # Insere antes do fechamento da div race-top
            race_top_end = "{% if h.total_pilotos %}\n        <span class=\"race-badge\"><i class=\"fa-solid fa-users me-1\"></i>{{ h.total_pilotos }} pilotos</span>\n        {% endif %}\n      </div>"
            
            replacement = """{% if h.total_pilotos %}
        <span class="race-badge"><i class="fa-solid fa-users me-1"></i>{{ h.total_pilotos }} pilotos</span>
        {% endif %}
        <a href="{{ url_for('admin.race_results', race_id=h.race_id) }}" class="btn-edit-race" title="Editar">
          <i class="fa-solid fa-pen-to-square me-1"></i>Editar
        </a>
      </div>"""
            if race_top_end in content:
                content = content.replace(race_top_end, replacement)
                print("-> Estrutura HTML reposicionada usando fallback.")
            else:
                # Busca mais simples
                simple_end = "pilotos</span>\n        {% endif %}\n      </div>"
                simple_repl = "pilotos</span>\n        {% endif %}\n        <a href=\"{{ url_for('admin.race_results', race_id=h.race_id) }}\" class=\"btn-edit-race\" title=\"Editar\"><i class=\"fa-solid fa-pen-to-square me-1\"></i>Editar</a>\n      </div>"
                if simple_end in content:
                    content = content.replace(simple_end, simple_repl)
                    print("-> Estrutura HTML reposicionada usando fallback simples.")
                else:
                    print("ERRO: Não foi possível reposicionar o botão no HTML automaticamente.")
                    return False

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("-> Correção de layout concluída localmente!")
    return True

if __name__ == '__main__':
    fix_edit_button()
