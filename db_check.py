import sqlite3

def run_check():
    conn = sqlite3.connect('f1_league.db')
    cursor = conn.cursor()
    
    out = []
    out.append("=== DIAGNÓSTICO DO BANCO DE DADOS ===")
    
    # 1. Todas as corridas com "Vegas"
    cursor.execute("""
        SELECT r.id, r.nome_gp, r.pista, r.data_corrida, r.status, r.season_id, s.nome, r.grid_id, g.nome
        FROM race r
        LEFT JOIN season s ON r.season_id = s.id
        LEFT JOIN grid_config g ON r.grid_id = g.id
        WHERE r.nome_gp LIKE '%Vegas%' OR r.pista LIKE '%Vegas%'
    """)
    races = cursor.fetchall()
    out.append(f"\nCorridas encontradas (Vegas): {len(races)}")
    for r in races:
        # Conta resultados
        cursor.execute("SELECT COUNT(*) FROM race_result WHERE race_id = ?", (r[0],))
        res_count = cursor.fetchone()[0]
        out.append(f"  ID={r[0]} | GP={r[1]} | Pista={r[2]} | Data={r[3]} | Status={r[4]} | Temporada={r[6]} (ID={r[5]}) | Grid={r[8]} (ID={r[7]}) | Resultados={res_count}")
        
        # Se houver resultados, mostra os 3 primeiros
        if res_count > 0:
            cursor.execute("""
                SELECT rr.posicao, p.nickname, rr.pontos_ganhos
                FROM race_result rr
                JOIN pilot_profile p ON rr.pilot_id = p.id
                WHERE rr.race_id = ?
                ORDER BY rr.posicao ASC LIMIT 3
            """, (r[0],))
            top3 = cursor.fetchall()
            out.append("    Top 3 lançados:")
            for pos, nick, pts in top3:
                out.append(f"      P{pos}: {nick} ({pts} pts)")
    
    # 2. Todos os circuitos cadastrados no banco
    cursor.execute("SELECT DISTINCT pista FROM race ORDER BY pista")
    pistas = [p[0] for p in cursor.fetchall()]
    out.append(f"\nCircuitos cadastrados no banco (Total {len(pistas)}):")
    for p in pistas:
        out.append(f"  - {p}")
        
    with open('db_check_result.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
        
    print("Relatório gerado em db_check_result.txt")

if __name__ == '__main__':
    run_check()
