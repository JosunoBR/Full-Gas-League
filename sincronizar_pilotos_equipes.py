from run import app
from app.models import db, PilotProfile, Team, Season, GridConfig, RaceResult, Race
from sqlalchemy import func

def sincronizar():
    with app.app_context():
        print("\n=== SINCRONIZANDO PILOTOS, EQUIPES E GRIDS ===")
        
        # 1. Identifica a temporada ativa
        season = Season.query.filter_by(ativa=True).order_by(Season.id.desc()).first()
        if not season:
            print("Erro: Nenhuma temporada ativa encontrada.")
            return
        
        print(f"Temporada Ativa: {season.nome} (ID: {season.id})")
        
        # 2. Busca todos os pilotos e configurações de grid
        pilotos = PilotProfile.query.all()
        grid_configs = GridConfig.query.filter_by(season_id=season.id).all()
        grid_names = {g.nome.upper() for g in grid_configs}
        
        total_removidos_equipe = 0

        for p in pilotos:
            # Grids que o piloto possui no campo de texto do perfil (ex: "ELITE,ADVANCED")
            grids_perfil = set(g.strip().upper() for g in p.grid.split(',') if g.strip())
            
            # Equipes que o piloto pertence nesta temporada
            equipes_titular = [t for t in p.teams if t.season_id == season.id]
            equipes_reserva = [t for t in p.reserve_teams if t.season_id == season.id]
            
            grids_reais_com_equipe = set()
            for t in equipes_titular + equipes_reserva:
                g_nome = (t.grid_config.nome if t.grid_config else t.grid).upper()
                grids_reais_com_equipe.add(g_nome)
            
            # --- CASO 1: Piloto "retirado do grid" no perfil, mas ainda vinculado à equipe ---
            # Se o grid da equipe não está mais no perfil do piloto, removemos o vínculo da equipe.
            for t in equipes_titular:
                g_nome = (t.grid_config.nome if t.grid_config else t.grid).upper()
                if g_nome not in grids_perfil and g_nome in grid_names:
                    print(f"  [REMOVENDO] {p.nickname} da equipe {t.nome} (Não está mais no grid {g_nome} no perfil)")
                    t.pilots.remove(p)
                    total_removidos_equipe += 1
            
            for t in equipes_reserva:
                g_nome = (t.grid_config.nome if t.grid_config else t.grid).upper()
                if g_nome not in grids_perfil and g_nome in grid_names:
                    print(f"  [REMOVENDO RESERVA] {p.nickname} da equipe {t.nome} (Não está mais no grid {g_nome} no perfil)")
                    t.reserves.remove(p)
                    total_removidos_equipe += 1

            # --- CASO 2: Piloto "cadastrado no grid" no perfil, mas sem equipe ---
            # Avisa quais pilotos novos precisam de ação manual no painel de Equipes.
            for g_nome in grids_perfil:
                if g_nome in grid_names and g_nome not in grids_reais_com_equipe:
                    # Verifica se ele já correu (se correu, ele aparece pelos resultados)
                    tem_resultado = RaceResult.query.join(Race).filter(
                        RaceResult.pilot_id == p.id,
                        Race.season_id == season.id,
                        func.upper(Race.grid) == g_nome
                    ).first()
                    
                    if not tem_resultado:
                        print(f"  [AVISO] {p.nickname} está marcado como {g_nome} no perfil, mas NÃO possui equipe vinculada.")
                        print(f"          -> Ação: Vá em 'Gestão > Equipes', edite uma equipe e adicione-o.")

        db.session.commit()
        print(f"\n=== PROCESSO CONCLUÍDO ===")
        print(f"Vínculos de equipes obsoletos removidos: {total_removidos_equipe}")
        print("DICA: Após rodar, dê um Reload na aba Web do PythonAnywhere.")

if __name__ == "__main__":
    sincronizar()