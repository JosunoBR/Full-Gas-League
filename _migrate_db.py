"""
Migração direta: adiciona colunas faltantes ao banco SQLite sem usar flask db.
Execute: python _migrate_db.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'f1_league.db')

def get_columns(cursor, table):
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}

def get_tables(cursor):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row[0] for row in cursor.fetchall()}

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

tables = get_tables(cur)
print(f"Banco: {DB_PATH}")
print(f"Tabelas existentes: {sorted(tables)}\n")

alterations = []

# --- Tabela: race ---
if 'race' in tables:
    race_cols = get_columns(cur, 'race')
    if 'pole_pilot_id' not in race_cols:
        alterations.append(("race", "ADD COLUMN pole_pilot_id INTEGER REFERENCES pilot_profile(id)"))
    if 'pole_time' not in race_cols:
        alterations.append(("race", "ADD COLUMN pole_time VARCHAR(20)"))
    if 'pole_sitter' not in race_cols:
        # Coluna legada de texto — pode existir em alguns bancos
        pass

# --- Tabela: circuit_history (se não existir, cria) ---
if 'circuit_history' not in tables:
    alterations.append(("__CREATE__", """
        CREATE TABLE circuit_history (
            id INTEGER NOT NULL PRIMARY KEY,
            circuito VARCHAR(100) NOT NULL,
            data DATE NOT NULL,
            pole_position_id INTEGER REFERENCES pilot_profile(id),
            primeiro_id INTEGER REFERENCES pilot_profile(id),
            segundo_id INTEGER REFERENCES pilot_profile(id),
            terceiro_id INTEGER REFERENCES pilot_profile(id),
            piloto_do_dia_id INTEGER REFERENCES pilot_profile(id),
            tempo_pole VARCHAR(20),
            melhor_tempo_pista VARCHAR(20)
        )
    """))

# --- Aplica as alterações ---
if not alterations:
    print("✅ Nenhuma migração necessária. Banco já está atualizado.")
else:
    for table, stmt in alterations:
        if table == "__CREATE__":
            try:
                cur.execute(stmt)
                print(f"✅ Tabela criada: circuit_history")
            except Exception as e:
                print(f"⚠️  Erro ao criar tabela: {e}")
        else:
            try:
                sql = f"ALTER TABLE {table} {stmt}"
                cur.execute(sql)
                print(f"✅ {table}: {stmt}")
            except Exception as e:
                print(f"⚠️  {table} - {stmt}: {e}")

    conn.commit()
    print("\n✅ Migrações aplicadas com sucesso!")

conn.close()
print("\nAgora execute: python run.py")
