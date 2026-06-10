import os
import shutil

def clean_git_sessions():
    print("=== LIMPANDO REFERÊNCIAS CORROMPIDAS DE SESSÃO DO GIT ===")
    
    git_dir = '.git'
    if not os.path.exists(git_dir):
        print("Erro: Pasta .git não encontrada na raiz do projeto.")
        return False
        
    # 1. Deletar a pasta .git/refs/sessions
    refs_sessions_dir = os.path.join(git_dir, 'refs', 'sessions')
    if os.path.exists(refs_sessions_dir):
        try:
            shutil.rmtree(refs_sessions_dir)
            print("[OK] Diretório .git/refs/sessions deletado com sucesso!")
        except Exception as e:
            print(f"[ERRO] Falha ao deletar .git/refs/sessions: {e}")
    else:
        print("[INFO] Diretório .git/refs/sessions não existe ou já foi removido.")
        
    # 2. Deletar a pasta .git/logs/refs/sessions
    logs_sessions_dir = os.path.join(git_dir, 'logs', 'refs', 'sessions')
    if os.path.exists(logs_sessions_dir):
        try:
            shutil.rmtree(logs_sessions_dir)
            print("[OK] Diretório .git/logs/refs/sessions deletado com sucesso!")
        except Exception as e:
            print(f"[ERRO] Falha ao deletar .git/logs/refs/sessions: {e}")
    else:
        print("[INFO] Diretório .git/logs/refs/sessions não existe ou já foi removido.")

    # 3. Limpar referências em .git/packed-refs se existirem
    packed_refs_path = os.path.join(git_dir, 'packed-refs')
    if os.path.exists(packed_refs_path):
        print("Verificando se há referências de sessão em .git/packed-refs...")
        try:
            with open(packed_refs_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            new_lines = []
            removed_count = 0
            for line in lines:
                if 'refs/sessions' in line:
                    removed_count += 1
                    continue
                new_lines.append(line)
                
            if removed_count > 0:
                with open(packed_refs_path, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
                print(f"[OK] Removidas {removed_count} referências de sessão de packed-refs!")
            else:
                print("[INFO] Nenhuma referência de sessão encontrada em packed-refs.")
        except Exception as e:
            print(f"[ERRO] Falha ao limpar packed-refs: {e}")
            
    print("\nLimpeza concluída! Agora você já pode tentar rodar o 'git pull' e o 'git push' novamente.")
    return True

if __name__ == '__main__':
    clean_git_sessions()
