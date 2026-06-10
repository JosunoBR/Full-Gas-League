import os

def clean_historic_html():
    path = os.path.join('app', 'templates', 'admin', 'historic.html')
    if not os.path.exists(path):
        print(f"ERRO: {path} não encontrado no computador local.")
        return False
        
    print(f"Lendo {path}...")
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Remove a linha com o DEBUG se ela existir
    debug_pattern = '[DEBUG:'
    lines = content.splitlines()
    new_lines = []
    removed = False
    
    for line in lines:
        if debug_pattern in line:
            print(f"-> Removendo linha de debug: {line.strip()}")
            removed = True
            continue
        new_lines.append(line)
        
    updated_content = '\n'.join(new_lines) + '\n'
    
    # Se não houver a lógica do Recorde de Pole no arquivo físico local, vamos garantir que ela exista
    if 'stats.record_pilot' not in updated_content:
        print("-> Inserindo a lógica do Recorde de Pole ao lado de 'Mais poles' no html local...")
        # Encontra o bloco {% if stats.maior_pole %}
        start_var = "stats.maior_pole"
        start_idx = updated_content.find(f"{{% if {start_var} %}}")
        if start_idx == -1:
            start_idx = updated_content.find("{%if stats.maior_pole%}")
            
        if start_idx != -1:
            current_idx = start_idx
            if_count = 0
            insert_pos = -1
            
            while current_idx < len(updated_content):
                next_token = updated_content.find("{%", current_idx)
                if next_token == -1:
                    break
                    
                end_token = updated_content.find("%}", next_token)
                if end_token == -1:
                    break
                    
                token_content = updated_content[next_token:end_token+2]
                
                if "if " in token_content and "endif" not in token_content and "elif" not in token_content:
                    if_count += 1
                elif "endif" in token_content:
                    if_count -= 1
                    if if_count == 0:
                        insert_pos = end_token + 2
                        break
                        
                current_idx = end_token + 2
                
            if insert_pos != -1:
                pole_record_html = """
    {% if stats.record_pilot %}
    <div class="cs-item">
      <i class="fa-solid fa-stopwatch me-1" style="color: #60a5fa;"></i>
      Recorde de Pole: <strong>{{ stats.record_pilot }}</strong>
      {% if stats.record_time %}<span style="opacity: .6;"> ({{ stats.record_time }})</span>{% endif %}
    </div>
    {% endif %}"""
                updated_content = updated_content[:insert_pos] + pole_record_html + updated_content[insert_pos:]
                print("-> Lógica do Recorde de Pole inserida com sucesso!")
        else:
            print("AVISO: Bloco 'stats.maior_pole' não encontrado no html. Não foi possível inserir o recorde de pole automaticamente.")
            
    with open(path, 'w', encoding='utf-8') as f:
        f.write(updated_content)
        
    print("-> Arquivo app/templates/admin/historic.html local atualizado com sucesso!")
    return True

if __name__ == '__main__':
    clean_historic_html()
