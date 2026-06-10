import sqlite3
import os

def fix_db():
    db_path = '/home/fullgasleague/Full-Gas-League/f1_league.db'
    if not os.path.exists(db_path):
        # Fallback para local ou se a pasta for diferente
        db_path = 'f1_league.db'
        
    print(f"Conectando ao banco de dados em: {os.path.abspath(db_path)}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Adiciona a coluna pole_pilot_id
    try:
        cursor.execute("ALTER TABLE race ADD COLUMN pole_pilot_id VARCHAR(50)")
        print("[SUCESSO] Coluna 'pole_pilot_id' adicionada à tabela 'race'.")
    except Exception as e:
        print(f"[INFO] Coluna 'pole_pilot_id' não foi adicionada: {e}")
        
    # Adiciona a coluna pole_time
    try:
        cursor.execute("ALTER TABLE race ADD COLUMN pole_time VARCHAR(20)")
        print("[SUCESSO] Coluna 'pole_time' adicionada à tabela 'race'.")
    except Exception as e:
        print(f"[INFO] Coluna 'pole_time' não foi adicionada: {e}")
        
    conn.commit()
    conn.close()
    print("Concluído!")

if __name__ == '__main__':
    fix_db()
