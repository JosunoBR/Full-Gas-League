import os
import sys

# Adiciona o diretório raiz ao path para poder importar o app Flask
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from run import app
from app.models import db, Race, RaceRegistration, GridConfig, Season

def regularizar_checkin():
    with app.app_context():
        print("--- SCRIPT DE REGULARIZAÇÃO DE CHECK-IN ---")
        
        # 1. Encontrar a temporada ativa
        season = Season.query.filter_by(ativa=True).first()
        if not season:
            print("ERRO: Nenhuma temporada ativa encontrada.")
            return

        # 2. Encontrar a corrida da Austrália do grid Advanced
        # Usamos ilike para ser flexível com o nome (ex: "GP da Austrália" ou "Australia")
        race = Race.query.join(GridConfig, Race.grid_id == GridConfig.id).filter(
            Race.season_id == season.id,
            Race.nome_gp.ilike('%Austr%'),
            GridConfig.nome.ilike('%ADVANCED%')
        ).first()

        if not race:
            print("ERRO: Corrida na Austrália para o grid Advanced não encontrada na temporada ativa.")
            return

        print(f"\nCorrida Encontrada: {race.nome_gp} (ID: {race.id}) - Data: {race.data_corrida}")

        # 3. Buscar os check-ins atuais
        checkins = RaceRegistration.query.filter_by(race_id=race.id).all()
        
        if not checkins:
            print("Não há nenhum check-in registrado para esta corrida. O grid já está PENDENTE.")
            return

        print(f"\nForam encontrados {len(checkins)} registros de check-in:")
        
        # Agrupar check-ins pela data/hora para identificar o "lote" gerado indevidamente
        checkins_por_data = {}
        for c in checkins:
            data_str = c.data_resposta.strftime("%d/%m/%Y %H:%M") if c.data_resposta else "Sem Data"
            checkins_por_data.setdefault(data_str, []).append(c)

        for data_str, lista in checkins_por_data.items():
            print(f" - Às {data_str}: {len(lista)} piloto(s) confirmados/ausentes.")

        print("\nComo apenas 2 realmente responderam, o mais seguro é zerar tudo e avisá-los para responder novamente.")
        print("⚠️  NOTA: Esta operação afeta APENAS a intenção de check-in (tabela RaceRegistration).")
        print("          Os resultados oficiais da corrida (tabela RaceResult) NÃO serão alterados.")
        confirmacao = input(f"Deseja APAGAR TODOS os {len(checkins)} check-ins desta corrida? (S/N): ")

        if confirmacao.strip().upper() == 'S':
            RaceRegistration.query.filter_by(race_id=race.id).delete()
            db.session.commit()
            print("\n✅ Sucesso! Todos os check-ins da Austrália/Advanced foram apagados e voltaram para PENDENTE.")
        else:
            print("\nOperação cancelada. Nenhum check-in foi alterado.")

if __name__ == '__main__':
    regularizar_checkin()
