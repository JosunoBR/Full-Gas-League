from run import app
from app.models import db, PilotGridPhoto, GridConfig, Season

def reparar_migracao_fotos():
    """
    Repara o vínculo de fotos, garantindo que usem os IDs da Temporada Ativa.
    """
    with app.app_context():
        print("\n=== REPARANDO VÍNCULO DE FOTOS POR GRID ===")

        # 1. Identifica a temporada ativa
        season_ativa = Season.query.filter_by(ativa=True).order_by(Season.id.desc()).first()
        if not season_ativa:
            print("ERRO: Nenhuma temporada ativa encontrada.")
            return
        
        print(f"Temporada de referência: {season_ativa.nome} (ID: {season_ativa.id})")

        # 2. Mapeia nomes para IDs desta temporada específica
        configs = GridConfig.query.filter_by(season_id=season_ativa.id).all()
        # Também buscamos grids globais (sem season_id) como fallback (ex: RESERVA)
        global_configs = GridConfig.query.filter_by(season_id=None).all()
        
        name_to_id_map = {c.nome.strip().upper(): c.id for c in configs + global_configs}
        
        print(f"Grids mapeados para esta temporada: {list(name_to_id_map.keys())}")

        # 3. Busca TODAS as fotos que possuem o nome do grid (texto)
        # Note que não filtramos por 'grid_id is None' para podermos corrigir o erro anterior
        photos = PilotGridPhoto.query.filter(PilotGridPhoto.grid.isnot(None)).all()
        
        print(f"Analisando {len(photos)} registros de fotos...")
        
        corrigidos = 0
        mantidos = 0
        nao_encontrados = 0

        for photo in photos:
            nome_original = photo.grid.strip().upper()
            id_correto = name_to_id_map.get(nome_original)

            if id_correto:
                if photo.grid_id != id_correto:
                    print(f"  [CORRIGINDO] Foto {photo.id} (Piloto {photo.pilot_id}): '{nome_original}' -> ID {id_correto}")
                    photo.grid_id = id_correto
                    corrigidos += 1
                else:
                    mantidos += 1
            else:
                print(f"  [AVISO] Grid '{nome_original}' não encontrado na temporada ativa (Foto {photo.id})")
                nao_encontrados += 1

        if corrigidos > 0:
            db.session.commit()
            print(f"\n✅ Sucesso! {corrigidos} fotos foram vinculadas aos IDs corretos.")
        else:
            print("\nNenhuma correção foi necessária.")

if __name__ == "__main__":
    reparar_migracao_fotos()