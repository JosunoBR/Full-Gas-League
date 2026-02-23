import os
import shutil
from datetime import datetime

# Configurações
# O script assume que está na mesma pasta do f1_league.db
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_FILE = os.path.join(BASE_DIR, 'f1_league.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups_seguranca')

def realizar_backup():
    # 1. Cria a pasta de backup se não existir
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        print(f"Pasta criada: {BACKUP_DIR}")

    # 2. Define o nome do arquivo com Data e Hora
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    backup_name = f"f1_league_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    # 3. Copia o arquivo
    if os.path.exists(DB_FILE):
        shutil.copy2(DB_FILE, backup_path)
        print(f"✅ Backup realizado com sucesso: {backup_name}")
    else:
        print(f"❌ Erro: Banco de dados não encontrado em {DB_FILE}")

    # 4. Limpeza: Mantém apenas os últimos 30 backups para economizar espaço
    backups = sorted([os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.endswith('.db')])
    
    while len(backups) > 30:
        arquivo_velho = backups.pop(0)
        os.remove(arquivo_velho)
        print(f"🗑️ Backup antigo removido: {os.path.basename(arquivo_velho)}")

if __name__ == "__main__":
    realizar_backup()