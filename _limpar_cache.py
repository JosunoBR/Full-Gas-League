# Script para limpar todos os caches e reiniciar
import os
import shutil

# Encontra e remove todos os __pycache__
count = 0
for root, dirs, files in os.walk('.'):
    for d in dirs:
        if d == '__pycache__':
            full_path = os.path.join(root, d)
            try:
                shutil.rmtree(full_path)
                print(f"REMOVIDO: {full_path}")
                count += 1
            except Exception as e:
                print(f"ERRO ao remover {full_path}: {e}")

# Remove .pyc soltos
for root, dirs, files in os.walk('.'):
    for f in files:
        if f.endswith('.pyc'):
            full_path = os.path.join(root, f)
            try:
                os.remove(full_path)
                print(f"REMOVIDO: {full_path}")
                count += 1
            except Exception as e:
                print(f"ERRO ao remover {full_path}: {e}")

print(f"\nTotal de caches removidos: {count}")
print("Agora reinicie o servidor com: python run.py")
