import sqlite3

conn = sqlite3.connect('f1_league.db')
cursor = conn.cursor()

# Busca a primeira corrida concluída
cursor.execute("SELECT id, nome_gp, pista FROM race WHERE status='Concluida' LIMIT 1")
race = cursor.fetchone()

if race:
    race_id, gp, pista = race
    print(f"Corrida encontrada: ID {race_id} - {gp} ({pista})")

    # Busca resultados da corrida
    cursor.execute("SELECT id, posicao, pilot_id FROM race_result WHERE race_id=? ORDER BY posicao ASC", (race_id,))
    results = cursor.fetchall()
    print(f"Total resultados: {len(results)}")

    sample_details = [
        (1, 3, "46:30.058", "1:26.596", "M,H", None),
        (2, 6, "+0.270", "1:26.951", "M,H", None),
        (3, 1, "+19.421", "1:26.590", "M,H", "2 pen (+6s)"),
        (4, 2, "+23.569", "1:26.977", "M,H", None),
        (5, 9, "+24.470", "1:27.865", "S,M,H", "1 pen (+3s)"),
        (6, 11, "+26.847", "1:28.119", "M,H", None),
        (7, 17, "+31.939", "1:27.661", "M,H", "1 pen (+3s)"),
        (8, 10, "+33.643", "1:27.943", "M,H", None),
        (9, 15, "+40.776", "1:27.948", "M,H", None),
        (10, 5, "+51.356", "1:26.468", "M,H,M,S", "1 pen (+3s)"),
    ]

    for idx, res in enumerate(results):
        res_id, pos, pilot_id = res
        if idx < len(sample_details):
            p_pos, grid_start, tempo, vr_tempo, pneus, pen = sample_details[idx]
            cursor.execute("""
                UPDATE race_result
                SET grid_largada=?, tempo_total=?, melhor_volta=?, pneus_stints=?, penalidades_texto=?
                WHERE id=?
            """, (grid_start, tempo, vr_tempo, pneus, pen, res_id))

    conn.commit()
    print("Dados avançados de teste inseridos com sucesso!")
else:
    print("Nenhuma corrida concluída encontrada no banco.")

conn.close()
