from run import app
from app.models import db, PilotGridPhoto, GridConfig
from sqlalchemy import text

def migrar_fotos_para_grid_id():
    """
    Script para migrar dados da tabela PilotGridPhoto.
    Ele preenche o novo campo 'grid_id' com base no valor de texto do campo antigo 'grid'.
    """
    with app.app_context():
        print("Iniciando migração de fotos de grid para o novo sistema de IDs...")

        # 0. Garante que a coluna grid_id existe na tabela pilot_grid_photo
        with db.engine.begin() as conn:
            try:
                conn.execute(text("SELECT grid_id FROM pilot_grid_photo LIMIT 1"))
            except Exception:
                print("  > Adicionando coluna 'grid_id' à tabela pilot_grid_photo...")
                conn.execute(text("ALTER TABLE pilot_grid_photo ADD COLUMN grid_id INTEGER REFERENCES grid_config(id)"))

        # 1. Mapeia todos os nomes de GridConfig para seus IDs (case-insensitive)
        # Isso evita fazer uma query no banco para cada foto.
        all_configs = GridConfig.query.all()
        valid_ids = {c.id for c in all_configs}
        name_to_id_map = {c.nome.strip().upper(): c.id for c in all_configs}
        
        if not name_to_id_map:
            print("\nERRO: Nenhuma configuração de grid (GridConfig) foi encontrada no sistema.")
            print("Certifique-se de que os grids (ELITE, ADVANCED, etc.) estão criados nas temporadas ativas antes de rodar a migração.")
            return

        print(f"\nEncontradas {len(name_to_id_map)} configurações de grid: {list(name_to_id_map.keys())}")

        # 2. Busca todas as fotos que precisam ser migradas (com nome de grid, mas sem grid_id)
        photos_to_migrate = PilotGridPhoto.query.filter(PilotGridPhoto.grid.isnot(None), PilotGridPhoto.grid_id.is_(None)).all()
        
        if not photos_to_migrate:
            print("\nNenhuma foto para migrar. O banco de dados já parece estar atualizado.")
            return

        print(f"\nEncontradas {len(photos_to_migrate)} fotos para processar...")
        migrated_count = 0
        skipped_count = 0

        # 3. Itera sobre cada foto e atribui o grid_id correto
        for photo in photos_to_migrate:
            grid_val = photo.grid.strip()
            
            # CORREÇÃO: Se o valor já for um número (ID), vincula diretamente
            if grid_val.isdigit():
                grid_id_int = int(grid_val)
                if grid_id_int in valid_ids:
                    photo.grid_id = grid_id_int
                    print(f"  - OK: Foto ID {photo.id} (Piloto {photo.pilot_id}) já continha o ID '{grid_val}'. Vinculado com sucesso.")
                    migrated_count += 1
                    continue

            # Caso contrário, busca pelo nome (ex: 'ELITE')
            grid_name_upper = grid_val.upper()
            matching_grid_id = name_to_id_map.get(grid_name_upper)

            if matching_grid_id:
                photo.grid_id = matching_grid_id
                print(f"  - OK: Foto ID {photo.id} (Piloto {photo.pilot_id}) migrada do nome '{grid_val}' para ID {matching_grid_id}.")
                migrated_count += 1
            else:
                print(f"  - AVISO: Não foi encontrado um GridConfig para o valor '{grid_val}' (Foto ID {photo.id}).")
                skipped_count += 1
        
        if migrated_count > 0:
            db.session.commit()
            print("\nMigração concluída com sucesso!")
        
        print(f"Resumo: {migrated_count} fotos migradas, {skipped_count} fotos ignoradas (sem correspondência).")

if __name__ == "__main__":
    migrar_fotos_para_grid_id()