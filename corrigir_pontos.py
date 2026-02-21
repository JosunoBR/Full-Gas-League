from run import app
from app.models import db, PilotProfile, Protesto, RaceResult

def corrigir_cnh():
    with app.app_context():
        print("\n=== INICIANDO CORREÇÃO AUTOMÁTICA DE CNH ===")
        print(f"{'PILOTO':<20} | {'ANTES':<6} | {'DEPOIS':<9} | {'AJUSTE'}")
        print("-" * 60)

        pilotos = PilotProfile.query.all()
        total_corrigidos = 0
        
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
            fnjs = RaceResult.query.filter_by(pilot_id=p.id, ausencia='FNJ').count()
            perda_fnj = fnjs * 2
            
            # Cálculo Final
            cnh_calculada = cnh_calculada - perda_protestos - perda_adv - perda_fnj
            
            # Aplica a correção se houver divergência
            if p.pontos_cnh != cnh_calculada:
                antigo = p.pontos_cnh
                p.pontos_cnh = cnh_calculada
                
                diferenca = cnh_calculada - antigo
                sinal = "+" if diferenca > 0 else ""
                
                print(f"{p.nickname:<20} | {antigo:<6} | {cnh_calculada:<9} | {sinal}{diferenca} pts")
                total_corrigidos += 1

        if total_corrigidos > 0:
            db.session.commit()
            print("-" * 60)
            print(f"SUCESSO! {total_corrigidos} pilotos tiveram sua CNH corrigida.")
        else:
            print("Nenhuma correção necessária. Todos os dados estão íntegros.")

if __name__ == "__main__":
    corrigir_cnh()