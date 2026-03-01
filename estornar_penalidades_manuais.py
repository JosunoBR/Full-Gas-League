from run import app
from app.models import db, PilotProfile

def estornar_penalidades_manuais():
    with app.app_context():
        print("\n=== INICIANDO ESTORNO DE PENALIDADES ADMINISTRATIVAS (MANUAIS) ===")
        
        # Busca pilotos que possuem penalidade diferente de zero no perfil (penalidade_campeonato)
        pilotos = PilotProfile.query.filter(PilotProfile.penalidade_campeonato != 0).all()
        
        if not pilotos:
            print("Nenhuma penalidade manual (administrativa) encontrada para estornar.")
            return

        total_estornado = 0
        for p in pilotos:
            valor = p.penalidade_campeonato
            motivo = p.motivo_penalidade
            p.penalidade_campeonato = 0.0
            p.motivo_penalidade = None
            total_estornado += 1
            print(f"  > Piloto {p.nickname} (ID: {p.id}): Estornados {valor} pts (Motivo era: {motivo})")

        db.session.commit()
        print(f"\n=== PROCESSO CONCLUÍDO ===")
        print(f"Total de pilotos corrigidos: {total_estornado}")

if __name__ == "__main__":
    estornar_penalidades_manuais()