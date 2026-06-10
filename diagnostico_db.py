import os
import sqlite3
from run import app
from app.models import db

def diag():
    print("=== DIAGNÓSTICO DO BANCO DE DADOS NO SERVIDOR ===")
    
    # 1. Caminho configurado
    uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    print(f"1. URI configurada no Flask: {uri}")
    
    # Tenta extrair o caminho do arquivo
    db_path = ""
    if uri.startswith("sqlite:///"):
        db_path = uri.replace("sqlite:///", "")
        print(f"2. Caminho absoluto do arquivo SQLite: {db_path}")
    
    # 2. Verifica se o arquivo existe e o tamanho dele
    if os.path.exists(db_path):
        print(f"3. O arquivo existe? SIM")
        print(f"4. Tamanho do arquivo: {os.path.getsize(db_path)} bytes")
    else:
        print(f"3. O arquivo existe? NÃO")
        
    # 3. Encontra outros arquivos .db no projeto
    print("\n5. Buscando outros arquivos .db no diretório do projeto:")
    found_any = False
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.db'):
                full = os.path.join(root, file)
                print(f"  - Encontrado: {full} ({os.path.getsize(full)} bytes)")
                found_any = True
    if not found_any:
        print("  Nenhum arquivo .db encontrado na busca recursiva.")

    # 4. Inspeciona a tabela 'race' no arquivo configurado
    if os.path.exists(db_path):
        print("\n6. Inspecionando colunas da tabela 'race' no banco configurado:")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(race)")
            columns = cursor.fetchall()
            for col in columns:
                # col[1] é o nome da coluna
                print(f"  - Coluna: {col[1]} ({col[2]})")
            conn.close()
        except Exception as e:
            print(f"  Erro ao inspecionar: {e}")

if __name__ == '__main__':
    diag()
