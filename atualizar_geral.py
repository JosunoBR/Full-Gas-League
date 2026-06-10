import sqlite3
import os

MAP_PISTAS = {
    "las vegas": "Las Vegas Strip Circuit",
    "vegas": "Las Vegas Strip Circuit",
    "spa": "Circuito de Spa-Francorchamps",
    "belgica": "Circuito de Spa-Francorchamps",
    "bélgica": "Circuito de Spa-Francorchamps",
    "monaco": "Circuito de Mônaco",
    "mônaco": "Circuito de Mônaco",
    "austria": "Red Bull Ring",
    "áustria": "Red Bull Ring",
    "red bull": "Red Bull Ring",
    "hungria": "Hungaroring",
    "hungaroring": "Hungaroring",
    "bahrain": "Circuito Internacional do Bahrein",
    "barein": "Circuito Internacional do Bahrein",
    "jeddah": "Circuito de Jeddah-Corniche",
    "jedah": "Circuito de Jeddah-Corniche",
    "arabia": "Circuito de Jeddah-Corniche",
    "arábia": "Circuito de Jeddah-Corniche",
    "albert park": "Circuito de Albert Park",
    "australia": "Circuito de Albert Park",
    "austrália": "Circuito de Albert Park",
    "suzuka": "Circuito de Suzuka",
    "japao": "Circuito de Suzuka",
    "japão": "Circuito de Suzuka",
    "xangai": "Circuito Internacional de Xangai",
    "shanghai": "Circuito Internacional de Xangai",
    "china": "Circuito Internacional de Xangai",
    "miami": "Autódromo Internacional de Miami",
    "imola": "Autódromo Enzo e Dino Ferrari - Imola",
    "barcelona": "Circuito de Barcelona-Catalunha",
    "espanha": "Circuito de Barcelona-Catalunha",
    "catalunha": "Circuito de Barcelona-Catalunha",
    "madrid": "Circuito de Madrid (IFEMA)",
    "montreal": "Circuito Gilles Villeneuve",
    "canada": "Circuito Gilles Villeneuve",
    "canadá": "Circuito Gilles Villeneuve",
    "silverstone": "Circuito de Silverstone",
    "inglaterra": "Circuito de Silverstone",
    "zandvoort": "Circuito de Zandvoort",
    "holanda": "Circuito de Zandvoort",
    "monza": "Autódromo Nacional de Monza",
    "italia": "Autódromo Nacional de Monza",
    "itália": "Autódromo Nacional de Monza",
    "baku": "Circuito Urbano de Baku",
    "azerbaijao": "Circuito Urbano de Baku",
    "azerbaijão": "Circuito Urbano de Baku",
    "singapura": "Circuito de Marina Bay",
    "marina bay": "Circuito de Marina Bay",
    "cota": "Circuito das Américas (COTA) - Áustin",
    "texas": "Circuito das Américas (COTA) - Áustin",
    "austin": "Circuito das Américas (COTA) - Áustin",
    "áustin": "Circuito das Américas (COTA) - Áustin",
    "hermanos": "Autódromo Hermanos Rodríguez",
    "mexico": "Autódromo Hermanos Rodríguez",
    "méxico": "Autódromo Hermanos Rodríguez",
    "interlagos": "Autódromo José Carlos Pace",
    "sao paulo": "Autódromo José Carlos Pace",
    "são paulo": "Autódromo José Carlos Pace",
    "lusail": "Circuito Internacional de Lusail",
    "qatar": "Circuito Internacional de Lusail",
    "catar": "Circuito Internacional de Lusail",
    "yas marina": "Circuito de Yas Marina",
    "abu dhabi": "Circuito de Yas Marina",
    "algarve": "Autódromo Internacional do Algarve",
    "portugal": "Autódromo Internacional do Algarve",
    "paul ricard": "Circuito Paul Ricard",
    "frança": "Circuito Paul Ricard",
    "franca": "Circuito Paul Ricard"
}

def update_db():
    # Detecta onde está o banco
    db_path = '/home/fullgasleague/Full-Gas-League/f1_league.db'
    if not os.path.exists(db_path):
        db_path = 'f1_league.db'
        
    print(f"=== ATUALIZANDO BANCO EM: {os.path.abspath(db_path)} ===")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Criar colunas se não existirem
    print("\n1. Verificando estrutura do banco...")
    try:
        cursor.execute("ALTER TABLE race ADD COLUMN pole_pilot_id VARCHAR(50)")
        print("-> Coluna 'pole_pilot_id' criada.")
    except Exception as e:
        print(f"-> Coluna 'pole_pilot_id' já existente ou erro: {e}")
        
    try:
        cursor.execute("ALTER TABLE race ADD COLUMN pole_time VARCHAR(20)")
        print("-> Coluna 'pole_time' criada.")
    except Exception as e:
        print(f"-> Coluna 'pole_time' já existente ou erro: {e}")
        
    # 2. Unificar nomes de pistas
    print("\n2. Iniciando unificação de pistas...")
    cursor.execute("SELECT id, pista FROM race")
    races = cursor.fetchall()
    
    updates = 0
    for race_id, pista_nome in races:
        pista_limpa = pista_nome.strip().lower()
        
        # Procura correspondência
        pista_oficial = None
        for key, val in MAP_PISTAS.items():
            if key in pista_limpa:
                pista_oficial = val
                break
                
        if pista_oficial and pista_oficial != pista_nome:
            print(f"-> Corrida ID {race_id}: Alterando '{pista_nome}' para '{pista_oficial}'")
            cursor.execute("UPDATE race SET pista = ? WHERE id = ?", (pista_oficial, race_id))
            updates += 1
            
    conn.commit()
    conn.close()
    print(f"\nUnificação concluída! {updates} corridas foram corrigidas.")

if __name__ == '__main__':
    update_db()
