import os
import sqlite3

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATHS = [
    os.path.join(BASE_DIR, 'f1_league.db'),
    os.path.join(BASE_DIR, 'instance', 'f1_league.db')
]

def migrate_database(db_path):
    if not os.path.exists(db_path):
        print(f"[PULADO] Arquivo nao encontrado: {db_path}")
        return

    print(f"[PROCESSANDO] Banco: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(protesto)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if not columns:
            print(f"[AVISO] Tabela protesto nao encontrada em {db_path}")
            conn.close()
            return

        if 'tipo_ban' in columns:
            print(f"[OK] Coluna 'tipo_ban' ja existe na tabela protesto.")
        else:
            print("[EXECUTANDO] Adicionando coluna 'tipo_ban' na tabela protesto...")
            cursor.execute("ALTER TABLE protesto ADD COLUMN tipo_ban VARCHAR(30) DEFAULT 'NENHUM'")
            conn.commit()
            print("[SUCESSO] Coluna 'tipo_ban' adicionada com sucesso!")

        # Valida se esta presente
        cursor.execute("PRAGMA table_info(protesto)")
        updated_cols = [row[1] for row in cursor.fetchall()]
        print(f"[COLUNAS] {updated_cols}")

    except Exception as e:
        print(f"[ERRO] Falha durante migracao em {db_path}: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    for p in DB_PATHS:
        migrate_database(p)
