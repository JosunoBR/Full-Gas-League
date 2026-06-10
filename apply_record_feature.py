import os
import re

def patch_admin_py():
    path = os.path.join('app', 'routes', 'admin.py')
    if not os.path.exists(path):
        print(f"ERRO: {path} nao encontrado!")
        return False
        
    print(f"Lendo {path}...")
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if 'record_pilot' in content and 'parse_time_str' in content:
        print("-> Lógica do recorde de pole ja esta presente no app/routes/admin.py física.")
        return True
        
    print("-> Aplicando patch em app/routes/admin.py...")
    
    # 1. Injetar a funcao parse_time_str logo após a definicao de historic():
    historic_def = "def historic():"
    idx = content.find(historic_def)
    if idx == -1:
        print("ERRO: Nao foi possivel encontrar 'def historic():' em admin.py")
        return False
        
    # Vamos achar o fim da linha de def historic():
    eol = content.find('\n', idx)
    
    # Código a ser injetado logo apos historic()
    parse_fn = """
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
    # Injeta a funcao
    content = content[:eol+1] + parse_fn + content[eol+1:]
    
    # 2. Atualizar o loop para calcular min_seconds, record_pilot, record_time
    loop_start_pattern = r"(for\s+circuito,\s+dados\s+in\s+historico_por_circuito\.items\(\):\s*\n\s*corridas\s*=\s*dados\['corridas'\]\s*\n\s*vitorias\s*=\s*\{\}\s*\n\s*poles\s*=\s*\{\})"
    match = re.search(loop_start_pattern, content)
    if not match:
        # Tenta versao mais simples
        loop_start_pattern = r"(for\s+circuito,\s+dados\s+in\s+historico_por_circuito\.items\(\):)"
        match = re.search(loop_start_pattern, content)
        
    if match:
        original_loop_start = match.group(1)
        replacement_loop_start = original_loop_start + "\n        \n        record_pilot = None\n        record_time = None\n        min_seconds = float('inf')"
        content = content.replace(original_loop_start, replacement_loop_start, 1)
    else:
        print("ERRO: Nao foi possivel encontrar o loop de calculo de estatisticas em admin.py")
        return False
        
    # 3. Atualizar o preenchimento de poles para coletar o menor tempo
    pole_sitter_pattern = r"(if\s+c\['pole_sitter'\]:\s*\n\s*nick\s*=\s*c\['pole_sitter'\]\.nickname\s*\n\s*poles\[nick\]\s*=\s*poles\.get\(nick,\s*0\)\s*\+\s*1)"
    match = re.search(pole_sitter_pattern, content)
    if match:
        original_pole_sitter = match.group(1)
        replacement_pole_sitter = original_pole_sitter + """
                
                if c['pole_time']:
                    t_sec = parse_time_str(c['pole_time'])
                    if t_sec < min_seconds:
                        min_seconds = t_sec
                        record_pilot = nick
                        record_time = c['pole_time']"""
        content = content.replace(original_pole_sitter, replacement_pole_sitter, 1)
    else:
        print("ERRO: Nao foi possivel encontrar o bloco 'if c[\'pole_sitter\']' em admin.py")
        return False
        
    # 4. Inserir record_pilot e record_time no dicionario dados['stats']
    stats_dict_pattern = r"(dados\['stats'\]\s*=\s*\{[^}]+'poles_lider':\s*poles\.get\(maior_pole,\s*0\)\s*if\s*maior_pole\s*else\s*0,)"
    match = re.search(stats_dict_pattern, content)
    if match:
        original_stats_dict = match.group(1)
        replacement_stats_dict = original_stats_dict + "\n            'record_pilot':    record_pilot,\n            'record_time':     record_time,"
        content = content.replace(original_stats_dict, replacement_stats_dict, 1)
    else:
        # Tenta versao mais simples: apenas inserir antes da data ou do fechamento do dicionario
        stats_dict_end_pattern = r"('poles_lider':[^,\n]+,\s*\n)"
        match = re.search(stats_dict_end_pattern, content)
        if match:
            original_line = match.group(1)
            replacement = original_line + "            'record_pilot':    record_pilot,\n            'record_time':     record_time,\n"
            content = content.replace(original_line, replacement, 1)
        else:
            print("ERRO: Nao foi possivel injetar as chaves de estatisticas no dicionario de admin.py")
            return False
            
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("-> app/routes/admin.py atualizado fisicamente no disco!")
    return True

def patch_historic_html():
    path = os.path.join('app', 'templates', 'admin', 'historic.html')
    if not os.path.exists(path):
        print(f"ERRO: {path} nao encontrado!")
        return False
        
    print(f"Lendo {path}...")
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if 'stats.record_pilot' in content:
        print("-> Campo do recorde de pole ja esta presente no app/templates/admin/historic.html física.")
        return True
        
    print("-> Aplicando patch em app/templates/admin/historic.html...")
    
    # Encontra o bloco {% if stats.maior_pole %}
    start_var = "stats.maior_pole"
    start_idx = content.find(f"{{% if {start_var} %}}")
    if start_idx == -1:
        # Tenta sem espacos internos
        start_idx = content.find("{%if stats.maior_pole%}")
        
    if start_idx == -1:
        print("ERRO: Nao foi possivel encontrar o bloco 'stats.maior_pole' no html")
        return False
        
    # Rastreia o {% endif %} correspondente ao maior_pole
    current_idx = start_idx
    if_count = 0
    insert_pos = -1
    
    while current_idx < len(content):
        next_token = content.find("{%", current_idx)
        if next_token == -1:
            break
            
        end_token = content.find("%}", next_token)
        if end_token == -1:
            break
            
        token_content = content[next_token:end_token+2]
        
        # Se for um if
        if "if " in token_content and "endif" not in token_content and "elif" not in token_content:
            if_count += 1
        elif "endif" in token_content:
            if_count -= 1
            if if_count == 0:
                insert_pos = end_token + 2
                break
                
        current_idx = end_token + 2
        
    if insert_pos == -1:
        print("ERRO: Nao foi possivel encontrar o fechamento do bloco 'stats.maior_pole'")
        return False
        
    # HTML a ser inserido
    pole_record_html = """
    {% if stats.record_pilot %}
    <div class="cs-item">
      <i class="fa-solid fa-stopwatch me-1" style="color: #60a5fa;"></i>
      Recorde de Pole: <strong>{{ stats.record_pilot }}</strong>
      {% if stats.record_time %}<span style="opacity: .6;"> ({{ stats.record_time }})</span>{% endif %}
    </div>
    {% endif %}"""
    
    # Injeta o html
    new_content = content[:insert_pos] + pole_record_html + content[insert_pos:]
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("-> app/templates/admin/historic.html atualizado fisicamente no disco!")
    return True

if __name__ == '__main__':
    ok_admin = patch_admin_py()
    ok_html = patch_historic_html()
    if ok_admin and ok_html:
        print("\n=== SUCESSO! ===")
        print("Os arquivos do disco fisico foram atualizados com a funcionalidade de recorde de pole.")
        print("Reinicie o servidor Flask e recarregue a pagina no navegador.")
    else:
        print("\n=== FALHA! ===")
        print("Nao foi possivel aplicar as alteracoes em alguns arquivos.")
