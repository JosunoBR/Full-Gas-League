from run import app
from app.models import db, PilotGridPhoto
from sqlalchemy import text

def consertar_tabela():
    with app.app_context():
        print("--- LIMPANDO RESTRIÇÕES DA TABELA DE FOTOS ---")
        
        with db.engine.connect() as conn:
            # 1. Verifica se a tabela existe
            check = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='pilot_grid_photo'")).fetchone()
            if not check:
                print("Tabela não encontrada. Rodando db.create_all()...")
                db.create_all()
                return

            print("Recriando tabela para remover a obrigatoriedade do campo 'grid' (texto)...")
            
            with db.engine.begin() as trans_conn:
                # Desativa chaves estrangeiras temporariamente para a manobra
                trans_conn.execute(text("PRAGMA foreign_keys = OFF"))
                
                # Renomeia a antiga
                trans_conn.execute(text("ALTER TABLE pilot_grid_photo RENAME TO pilot_grid_photo_old"))
                
                # Cria a nova usando a definição atual do Model (que permite NULL no grid)
                PilotGridPhoto.__table__.create(trans_conn)
                
                # Copia os dados (mapeando o que for possível)
                trans_conn.execute(text("""
                    INSERT INTO pilot_grid_photo (id, pilot_id, grid_id, grid, foto_url)
                    SELECT id, pilot_id, grid_id, grid, foto_url FROM pilot_grid_photo_old
                """))
                
                # Remove a antiga
                trans_conn.execute(text("DROP TABLE pilot_grid_photo_old"))
                
                trans_conn.execute(text("PRAGMA foreign_keys = ON"))
        
        db.session.commit()
        print("✅ Sucesso! A tabela de fotos agora é 100% compatível com o sistema de IDs.")

if __name__ == "__main__":
    consertar_tabela()