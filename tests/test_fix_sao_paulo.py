import unittest
from run import app, db
from app.models import Race, RaceResult, PilotProfile, Team, HomeCache
from app.services.race_result_service import RaceResultService

class FixSaoPauloTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_fix_gp_sao_paulo_and_verify(self):
        # Busca o GP de São Paulo ou a corrida mais recente
        race = Race.query.filter(Race.nome_gp.ilike('%são paulo%')).order_by(Race.id.desc()).first()
        if not race:
            race = Race.query.order_by(Race.id.desc()).first()
        
        self.assertIsNotNone(race, "Deve existir ao menos uma corrida cadastrada")
        print(f"\n[TEST FIX] Processando corrida: ID {race.id} - {race.nome_gp} ({race.pista})")
        
        # 1. Atualiza total de voltas para 36
        race.total_voltas = 36

        # 2. Busca os resultados atuais e monta a estrutura do form_data
        existing_results = RaceResult.query.filter_by(race_id=race.id).all()
        
        running_results = [r for r in existing_results if r.status_presenca == 'OK' and (r.posicao > 0 or r.dsq or r.dnf)]
        running_results.sort(key=lambda r: r.posicao if (r.posicao and r.posicao > 0) else 9999)

        form_data = {
            'sc_vsc_info': race.sc_vsc_info or '',
            'clima_temp': race.clima_temp or '',
            'total_voltas': '36',
            'pole_pilot_id': str(race.pole_pilot_id) if race.pole_pilot_id else '',
            'pole_time': race.pole_time or ''
        }

        for idx, res in enumerate(running_results, start=1):
            form_data[f'pos_{idx}_pilot'] = str(res.pilot_id)
            if res.grid_largada:
                form_data[f'pos_{idx}_grid_largada'] = str(res.grid_largada)
            if res.tempo_total:
                form_data[f'pos_{idx}_tempo_total'] = res.tempo_total
            if res.melhor_volta:
                form_data[f'pos_{idx}_melhor_volta'] = res.melhor_volta
            if res.tempo_qualy:
                form_data[f'pos_{idx}_tempo_qualy'] = res.tempo_qualy
            if res.pit_stops is not None:
                form_data[f'pos_{idx}_pit_stops'] = str(res.pit_stops or 0)
            if res.pneus_stints:
                form_data[f'pos_{idx}_pneus_stints'] = res.pneus_stints
            if res.penalidades_texto:
                form_data[f'pos_{idx}_penalidades_texto'] = res.penalidades_texto
            if res.dnf:
                form_data[f'pos_{idx}_dnf'] = 'on'
            if res.dsq:
                form_data[f'pos_{idx}_dsq'] = 'on'
            if res.volta_rapida:
                form_data[f'pos_{idx}_vr'] = 'on'
            if res.piloto_do_dia:
                form_data[f'pos_{idx}_dotd'] = 'on'
            if res.piloto_torcida:
                form_data[f'pos_{idx}_fan'] = 'on'

        # Adiciona ausentes
        absent_results = [r for r in existing_results if r.status_presenca in ['FJ', 'FNJ']]
        for abs_res in absent_results:
            form_data[f'status_ausente_{abs_res.pilot_id}'] = abs_res.status_presenca

        # 3. Executa o salvamento atualizado que aplica a regra desportiva e a busca de equipes reservas
        RaceResultService.save_race_results_by_position(race.id, form_data)
        
        # Limpa cache da home
        HomeCache.query.filter_by(season_id=race.season_id).delete()
        db.session.commit()

        # Validações
        self.assertEqual(race.total_voltas, 36)
        
        new_results = RaceResult.query.filter_by(race_id=race.id).order_by(RaceResult.posicao.asc()).all()
        
        # Garante que não existem lacunas entre os classificados válidos
        valid_positions = [nr.posicao for nr in new_results if not nr.dsq and nr.status_presenca == 'OK']
        self.assertEqual(valid_positions, list(range(1, len(valid_positions) + 1)), "Posições dos classificados devem ser contínuas sem lacunas")
        
        # Garante que os pilotos em DSQ estão ao final
        dsq_results = [nr for nr in new_results if nr.dsq]
        for dsq in dsq_results:
            self.assertGreater(dsq.posicao, len(valid_positions), "Pilotos em DSQ devem ficar após os classificados válidos")
            self.assertEqual(dsq.pontos_ganhos, 0.0, "Pilotos em DSQ não devem ganhar pontos")

        print(f"\n[SUCESSO] GP de São Paulo atualizado com 36 voltas, {len(valid_positions)} posições contínuas sem lacunas e {len(dsq_results)} DSQ no final.")

if __name__ == '__main__':
    unittest.main()
