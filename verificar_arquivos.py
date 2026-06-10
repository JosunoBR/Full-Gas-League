import os
import sys

def check():
    print("=== VERIFICAÇÃO DE INTEGRIDADE NO SERVIDOR ===")
    
    # 1. Verifica arquivo HTML
    html_path = 'app/templates/admin/historic.html'
    if os.path.exists(html_path):
        print(f"[OK] {html_path} existe (Tamanho: {os.path.getsize(html_path)} bytes)")
    else:
        print(f"[FALHA] {html_path} NÃO EXISTE!")
        
    # 2. Verifica rota em admin.py
    admin_py_path = 'app/routes/admin.py'
    if os.path.exists(admin_py_path):
        print(f"[OK] {admin_py_path} existe (Tamanho: {os.path.getsize(admin_py_path)} bytes)")
        with open(admin_py_path, 'r', encoding='utf-8') as f:
            content = f.read()
        if 'def historic(' in content:
            print("-> [OK] Rota 'def historic()' encontrada em admin.py")
        else:
            print("-> [FALHA] Rota 'def historic()' NÃO foi encontrada em admin.py!")
    else:
        print(f"[FALHA] {admin_py_path} NÃO EXISTE!")
        
    # 3. Testa importação e rotas do Flask
    try:
        from run import app
        print("[OK] Flask app importado com sucesso!")
        print("\nRotas /admin registradas no Flask:")
        found_historic = False
        for rule in app.url_map.iter_rules():
            if 'admin' in rule.rule:
                print(f"  - {rule.rule} (Endpoint: {rule.endpoint})")
                if 'historic' in rule.rule:
                    found_historic = True
        if found_historic:
            print("\n-> [OK] Rota '/admin/historic' está ativamente registrada no Flask!")
        else:
            print("\n-> [FALHA] Rota '/admin/historic' NÃO está registrada no Flask!")
    except Exception as e:
        print(f"[FALHA] Erro ao carregar app Flask ou rotas: {e}")

if __name__ == '__main__':
    check()
