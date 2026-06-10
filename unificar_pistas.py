import sqlite3

MAPPING = {
    # Las Vegas
    "Circuito de Las Vegas Strip": "Las Vegas Strip Circuit",
    
    # Austin / COTA
    "Circuito das Américas (COTA)": "Circuito das Américas (COTA) - Áustin",
    "Circuito das Américas (COTA) - Austin": "Circuito das Américas (COTA) - Áustin",
    
    # Albert Park / Melbourne
    "Circuito de Melbourne": "Circuito de Albert Park",
    "Albert Park": "Circuito de Albert Park",
    
    # Red Bull Ring / Spielberg
    "Circuito de Spielberg": "Red Bull Ring",
    "Spielberg": "Red Bull Ring",
    
    # Hungria / Hungaroring
    "Circuito de Hungaroring": "Hungaroring",
    
    # Jeddah
    "Circuito de Jeddah": "Circuito de Jeddah-Corniche",
    "Jeddah-Corniche": "Circuito de Jeddah-Corniche",
    "Jeddah": "Circuito de Jeddah-Corniche",
    
    # Imola
    "Autodromo Enzo e Dino Ferrari": "Autódromo Enzo e Dino Ferrari - Imola",
    "Imola": "Autódromo Enzo e Dino Ferrari - Imola",
    
    # Bahrein
    "Bahrain": "Circuito Internacional do Bahrein",
    "Circuito de Sakhir": "Circuito Internacional do Bahrein",
    "Sakhir": "Circuito Internacional do Bahrein",
    
    # Interlagos / São Paulo
    "Interlagos": "Autódromo José Carlos Pace",
    "Circuito de Interlagos": "Autódromo José Carlos Pace",
    "Autódromo de Interlagos": "Autódromo José Carlos Pace",
    
    # México
    "Circuito do México": "Autódromo Hermanos Rodríguez",
    "Autódromo Hermanos Rodriguez": "Autódromo Hermanos Rodríguez",
}

def unificar():
    conn = sqlite3.connect('f1_league.db')
    cursor = conn.cursor()
    
    print("=== UNIFICANDO CIRCUITOS NO BANCO DE DADOS ===")
    
    cursor.execute("SELECT id, nome_gp, pista, data_corrida FROM race")
    races = cursor.fetchall()
    
    updated_count = 0
    
    for r_id, nome_gp, pista, data in races:
        if pista in MAPPING:
            new_pista = MAPPING[pista]
            cursor.execute("UPDATE race SET pista = ? WHERE id = ?", (new_pista, r_id))
            print(f"  [ATUALIZADO] Corrida ID={r_id} ({nome_gp} - {data}): '{pista}' -> '{new_pista}'")
            updated_count += 1
            
    conn.commit()
    print(f"\n✅ Concluído! Total de {updated_count} corridas atualizadas.")
    
    # Mostra lista final de pistas distintas com corridas
    print("\n=== CIRCUITOS DISTINTOS APÓS UNIFICAÇÃO ===")
    cursor.execute("SELECT DISTINCT pista FROM race ORDER BY pista")
    pistas = cursor.fetchall()
    for p in pistas:
        cursor.execute("SELECT COUNT(*) FROM race WHERE pista = ?", (p[0],))
        count = cursor.fetchone()[0]
        print(f"  - {p[0]} ({count} corridas)")
        
    conn.close()

if __name__ == '__main__':
    unificar()
