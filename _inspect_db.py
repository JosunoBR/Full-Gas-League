"""Inspeciona dados existentes para o histórico"""
import sqlite3, os

db_path = os.path.join('instance', 'f1_league.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# 1. Últimas corridas concluídas
print("=== Ultimas 8 corridas concluidas ===")
cursor = conn.execute("""
    SELECT r.id, r.nome_gp, r.pista, r.data_corrida, r.status, r.grid, r.season_id
    FROM race r WHERE r.status = 'Concluida'
    ORDER BY r.data_corrida DESC LIMIT 8
""")
for row in cursor:
    print(f"  ID={row['id']} | {row['nome_gp']} | {row['pista']} | {row['data_corrida']} | Grid={row['grid']} | Season={row['season_id']}")

# 2. Pódio da última corrida
print("\n=== Podio + DOTD da ultima corrida ===")
last = conn.execute("SELECT id, nome_gp FROM race WHERE status='Concluida' ORDER BY data_corrida DESC LIMIT 1").fetchone()
if last:
    print(f"  Corrida: {last['nome_gp']} (ID={last['id']})")
    cursor = conn.execute("""
        SELECT rr.posicao, pp.nickname, rr.volta_rapida, rr.piloto_do_dia
        FROM race_result rr JOIN pilot_profile pp ON pp.id = rr.pilot_id
        WHERE rr.race_id = ? AND rr.posicao <= 3 AND rr.dsq = 0
        ORDER BY rr.posicao
    """, (last['id'],))
    for row in cursor:
        vr = " [VR]" if row['volta_rapida'] else ""
        dotd = " [DOTD]" if row['piloto_do_dia'] else ""
        print(f"  P{row['posicao']}: {row['nickname']}{vr}{dotd}")
    
    # Piloto do dia
    dotd = conn.execute("""
        SELECT pp.nickname FROM race_result rr JOIN pilot_profile pp ON pp.id = rr.pilot_id
        WHERE rr.race_id = ? AND rr.piloto_do_dia = 1
    """, (last['id'],)).fetchone()
    if dotd:
        print(f"  Piloto do Dia: {dotd['nickname']}")

# 3. Total
total = conn.execute("SELECT COUNT(*) as c FROM race WHERE status='Concluida'").fetchone()
print(f"\nTotal de corridas concluidas: {total['c']}")

# 4. Seasons
print("\n=== Seasons ===")
for row in conn.execute("SELECT id, nome, ativa FROM season ORDER BY id"):
    print(f"  ID={row['id']} | {row['nome']} | Ativa={row['ativa']}")

conn.close()
