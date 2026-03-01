import os
import shutil
from datetime import datetime

# Configurações
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_FILE = os.path.join(BASE_DIR, 'f1_league.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups_seguranca')

def realizar_backup():
    print("--- INICIANDO BACKUP DE SEGURANÇA ---")
    
    # 1. Cria a pasta de backup se não existir
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        print(f"Pasta de destino: {BACKUP_DIR}")

    # 2. Verifica se o banco existe
    if not os.path.exists(DB_FILE):
        print(f"❌ Erro: Banco de dados não encontrado em {DB_FILE}")
        return

    # 3. Define o nome do arquivo com Data e Hora
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    backup_name = f"f1_league_PRE_MIGRACAO_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    # 4. Copia o arquivo
    try:
        shutil.copy2(DB_FILE, backup_path)
        print(f"✅ Backup realizado com sucesso!")
        print(f"📁 Arquivo: {backup_name}")
        print("Pode prosseguir com a migração com segurança.")
    except Exception as e:
        print(f"❌ Falha ao copiar arquivo: {e}")

if __name__ == "__main__":
    realizar_backup()
