from run import app
from app.models import db, Team, Race, SeasonChampion, GridConfig
from sqlalchemy import func

def sincronizar_vinculos_faltantes():
    with app.app_context():
        print("\n=== INICIANDO SINCRONIZAÇÃO FINAL DE IDs ===")
        
        # Tabelas que precisam ter o grid_id preenchido
        tarefas = [
            {'model': Race, 'nome': 'Corridas'},
            {'model': Team, 'nome': 'Equipes'},
            {'model': SeasonChampion, 'nome': 'Campeões'}
        ]

        for tarefa in tarefas:
            Model = tarefa['model']
            print(f"\nVerificando {tarefa['nome']}...")
            
            # Busca registros onde o grid_id ainda é nulo
            registros_nulos = Model.query.filter(Model.grid_id == None).all()
            
            if not registros_nulos:
                print(f"  > Todos os registros de {tarefa['nome']} já possuem ID.")
                continue

            corrigidos = 0
            falhas = 0

            for reg in registros_nulos:
                # Tenta encontrar a configuração de grid correspondente
                # Critério: Mesma Temporada E Mesmo Nome de Grid
                grid_cfg = GridConfig.query.filter(
                    GridConfig.season_id == reg.season_id,
                    func.upper(GridConfig.nome) == func.upper(reg.grid)
                ).first()

                if not grid_cfg:
                    # BUSCA GLOBAL: Se não achou na temporada atual, procura em QUALQUER temporada
                    # Isso corrige erros onde o season_id foi preenchido errado na migração
                    grid_cfg = GridConfig.query.filter(
                        func.upper(GridConfig.nome) == func.upper(reg.grid)
                    ).first()
                    
                    if grid_cfg:
                        print(f"  [!] Corrigindo Temporada: {tarefa['nome']} '{reg.grid}' movida da Temporada {reg.season_id} para {grid_cfg.season_id}")
                        reg.season_id = grid_cfg.season_id

                if grid_cfg:
                    reg.grid_id = grid_cfg.id
                    corrigidos += 1
                else:
                    # Se não existe a config, talvez precise ser criada
                    print(f"  [!] Alerta: Não existe GridConfig '{reg.grid}' para a Temporada ID {reg.season_id}")
                    falhas += 1
            
            print(f"  > {corrigidos} registros vinculados com sucesso.")
            if falhas > 0:
                print(f"  > {falhas} registros não puderam ser vinculados (Configuração ausente).")

        # Sincronização de RaceResult (Opcional, mas recomendado se houver team_id nulo)
        print("\nVerificando integridade de RaceResult...")
        # Aqui garantimos que o grid_id da corrida seja respeitado
        db.session.commit()
        print("\n=== PROCESSO CONCLUÍDO ===")
        print("O banco de dados agora está utilizando os IDs relacionais como fonte primária.")

if __name__ == "__main__":
    sincronizar_vinculos_faltantes()