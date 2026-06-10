import sqlite3

def parse_time_str(time_str):
    if not time_str:
        return float('inf')
    s = time_str.strip()
    if not s:
        return float('inf')
    try:
        if ':' in s:
            parts = s.split(':')
            if len(parts) == 2:
                val = float(parts[0]) * 60 + float(parts[1])
                print(f"    DEBUG split 2: {parts} -> {val}")
                return val
            elif len(parts) == 3:
                val = float(parts[0]) * 60 + float(parts[1]) + float(parts[2]) / 1000.0
                print(f"    DEBUG split 3: {parts} -> {val}")
                return val
        val = float(s)
        print(f"    DEBUG direct float: {s} -> {val}")
        return val
    except Exception as e:
        print(f"    DEBUG ERROR: {e}")
        return float('inf')

def test():
    conn = sqlite3.connect('f1_league.db')
    cursor = conn.cursor()
    
    print("=== TESTING TIME PARSING ON DATABASE ===")
    cursor.execute("""
        SELECT r.id, r.nome_gp, r.pista, r.pole_time, p.nickname
        FROM race r
        LEFT JOIN pilot_profile p ON r.pole_pilot_id = p.id
    """)
    for row in cursor.fetchall():
        r_id, gp, pista, pole_time, pilot = row
        if pole_time:
            print(f"Race ID={r_id} | GP={gp} | Pista={pista} | Pilot={pilot} | TimeStr='{pole_time}'")
            parsed = parse_time_str(pole_time)
            print(f"  Result: {parsed}")
        
    conn.close()

if __name__ == '__main__':
    test()
