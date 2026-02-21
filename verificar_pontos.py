from run import app
from app.models import db, PilotProfile, Protesto, RaceResult

def auditar_cnh():
    with app.app_context():
        print("\n=== RELATÓRIO DE AUDITORIA DE CNH ===")
        print(f"{'PILOTO':<20} | {'ATUAL':<6} | {'CORRETO':<9} | {'STATUS':<10}")
        print("-" * 60)

        pilotos = PilotProfile.query.all()
        encontrou_erro = False
        
        for p in pilotos:
            # 1. Pontuação Inicial Padrão
            cnh_calculada = 25 
            
            # 2. Descontos por Protestos (Punições)
            protestos = Protesto.query.filter_by(acusado_id=p.id, status='CONCLUIDO').all()
            
            perda_protestos = 0
            adv_count = 0
            
            for prot in protestos:
                v = prot.veredito_final
                if v == 'LEVE': perda_protestos += 3
                elif v == 'MEDIA': perda_protestos += 5
                elif v == 'GRAVE': perda_protestos += 10
                elif v == 'ADVERTENCIA': adv_count += 1
            
            # Regra de Advertência: A cada 3 acumuladas, perde 3 pontos
            perda_adv = (adv_count // 3) * 3
            
            # 3. Descontos por W.O. (FNJ)
            # Busca resultados onde o piloto teve FNJ (Falta Não Justificada)
            fnjs = RaceResult.query.filter_by(pilot_id=p.id, ausencia='FNJ').count()
            perda_fnj = fnjs * 2
            
            # Cálculo Final
            cnh_calculada = cnh_calculada - perda_protestos - perda_adv - perda_fnj
            
            # Comparação
            if p.pontos_cnh != cnh_calculada:
                encontrou_erro = True
                print(f"{p.nickname:<20} | {p.pontos_cnh:<6} | {cnh_calculada:<9} | ERRO ⚠️")
                print(f"   > Detalhes: Protestos: -{perda_protestos} | Adv({adv_count}): -{perda_adv} | FNJ({fnjs}): -{perda_fnj}")

        if not encontrou_erro:
            print("Nenhum erro encontrado. Todos os saldos estão corretos.")
        
        print("-" * 60)

if __name__ == "__main__":
    auditar_cnh()