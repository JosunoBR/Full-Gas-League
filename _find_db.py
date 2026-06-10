"""Encontra o banco de dados correto"""
import sqlite3, os

# Verificar todos os .db no projeto
print("=== Arquivos .db no projeto ===")
for root, dirs, files in os.walk('.'):
    # Pular venv
    if 'venv' in root or '.venv' in root:
        continue
    for f in files:
        if f.endswith('.db'):
            full = os.path.join(root, f)
            size = os.path.getsize(full)
            print(f"  {full} ({size:,} bytes)")
            
            # Verifica conteúdo
            try:
                conn = sqlite3.connect(full)
                total_races = conn.execute("SELECT COUNT(*) FROM race WHERE status='Concluida'").fetchone()[0]
                total_seasons = conn.execute("SELECT COUNT(*) FROM season").fetchone()[0]
                print(f"    -> Corridas concluidas: {total_races}, Seasons: {total_seasons}")
                
                if total_races > 0:
                    last = conn.execute("SELECT nome_gp, data_corrida FROM race WHERE status='Concluida' ORDER BY data_corrida DESC LIMIT 1").fetchone()
                    print(f"    -> Ultima corrida: {last[0]} ({last[1]})")
                conn.close()
            except Exception as e:
                print(f"    -> Erro: {e}")

# Verificar config
print("\n=== Config do Flask ===")
with open('config.py', 'r', encoding='utf-8') as f:
    print(f.read())
