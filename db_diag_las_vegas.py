import sqlite3

conn = sqlite3.connect('f1_league.db')
cursor = conn.cursor()

print("=== CORRIDAS CADASTRADAS (GP de Las Vegas ou similares) ===")
cursor.execute("""
    SELECT r.id, r.nome_gp, r.pista, r.data_corrida, r.status,
           (SELECT COUNT(*) FROM race_result rr WHERE rr.race_id = r.id) as num_resultados
    FROM race r
    WHERE r.nome_gp LIKE '%Vegas%' OR r.pista LIKE '%Vegas%'
""")
rows = cursor.fetchall()
for row in rows:
    print(f"ID={row[0]} | GP={row[1]} | Pista={row[2]} | Data={row[3]} | Status={row[4]} | Resultados={row[5]}")

print("\n=== TODOS OS CIRCUITOS DISTINTOS ===")
cursor.execute("SELECT DISTINCT pista FROM race")
pistas = cursor.fetchall()
for p in pistas:
    print(f"- {p[0]}")

conn.close()
