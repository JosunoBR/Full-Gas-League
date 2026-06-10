import sqlite3

def check():
    conn = sqlite3.connect('f1_league.db')
    cursor = conn.cursor()
    
    print("=== POLE STATUS FOR ALL RACES ===")
    cursor.execute("""
        SELECT r.id, r.nome_gp, r.pista, r.data_corrida, r.pole_pilot_id, p.nickname, r.pole_time
        FROM race r
        LEFT JOIN pilot_profile p ON r.pole_pilot_id = p.id
    """)
    for row in cursor.fetchall():
        print(f"ID={row[0]} | GP={row[1]} | Pista={row[2]} | Data={row[3]} | Pole ID={row[4]} | Pilot={row[5]} | Time={row[6]}")
        
    conn.close()

if __name__ == '__main__':
    check()
