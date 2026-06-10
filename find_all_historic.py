import os

def find():
    print("=== BUSCANDO ARQUIVOS historic.html NO PROJETO ===")
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file == 'historic.html':
                full_path = os.path.join(root, file)
                print(f"Encontrado: {full_path}")
                # Mostra o tamanho e as primeiras/últimas linhas
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        print(f"  Tamanho: {os.path.getsize(full_path)} bytes")
                        print(f"  Total de linhas: {len(lines)}")
                        # Procura se tem DEBUG
                        has_debug = any('[DEBUG:' in line for line in lines)
                        print(f"  Contém '[DEBUG:'? {'SIM' if has_debug else 'NÃO'}")
                except Exception as e:
                    print(f"  Erro ao ler: {e}")

if __name__ == '__main__':
    find()
