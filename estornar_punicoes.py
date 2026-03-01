from run import app
from app.models import db, Protesto, RaceResult, Race
from sqlalchemy import text

def estornar_e_vincular():
    with app.app_context():
        print("\n=== INICIANDO ESTORNO DE PONTOS E VINCULAÇÃO DE GRIDS EM PROTESTOS ===")
        
        # 1. Garante que a coluna grid_id existe na tabela protesto (SQLite)
        with db.engine.begin() as conn:
            try:
                conn.execute(text("SELECT grid_id FROM protesto LIMIT 1"))
            except Exception:
                print("  > Adicionando coluna 'grid_id' à tabela protesto...")
                conn.execute(text("ALTER TABLE protesto ADD COLUMN grid_id INTEGER REFERENCES grid_config(id)"))

        protestos = Protesto.query.all()
        total_estornados = 0
        total_vinculados = 0
        
        for p in protestos:
            # Vincular grid_id se estiver nulo (baseado na corrida vinculada)
            if p.grid_id is None and p.etapa:
                p.grid_id = p.etapa.grid_id
                total_vinculados += 1
            
            # Estornar pontos se o protesto estiver concluído
            # Devolvemos os pontos ao RaceResult para que o novo cálculo dinâmico assuma o controle
            if p.status == 'CONCLUIDO':
                pontos_a_devolver = 0
                if p.veredito_final == 'LEVE': pontos_a_devolver = 3
                elif p.veredito_final == 'MEDIA': pontos_a_devolver = 5
                elif p.veredito_final == 'GRAVE': pontos_a_devolver = 10
                
                if pontos_a_devolver > 0:
                    # Busca o resultado da corrida para o acusado nesta etapa específica
                    resultado = RaceResult.query.filter_by(
                        race_id=p.etapa_id, 
                        pilot_id=p.acusado_id
                    ).first()
                    
                    if resultado:
                        resultado.pontos_ganhos += pontos_a_devolver
                        total_estornados += 1
                        print(f"  > Estornados {pontos_a_devolver} pts para {p.acusado.nickname} no GP {p.etapa.nome_gp}")

        db.session.commit()
        print("\n=== PROCESSO CONCLUÍDO ===")
        print(f"Total de grids vinculados em protestos: {total_vinculados}")
        print(f"Total de resultados de corrida corrigidos (estornados): {total_estornados}")
        print("\nAgora o sistema calculará as punições dinamicamente sem afetar a súmula da corrida.")

if __name__ == "__main__":
    estornar_e_vincular()