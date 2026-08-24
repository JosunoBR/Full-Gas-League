import unittest
from app.utils import ORDEM_CARROS
from app.services.presentation_service import PresentationService

class BallastOrderTestCase(unittest.TestCase):
    def test_ballast_cars_order(self):
        expected_unique_teams = [
            'Cadillac',
            'Aston Martin',
            'Audi',
            'Haas',
            'Alpine',
            'Racing Bulls',
            'Williams',
            'Red Bull',
            'Ferrari',
            'McLaren',
            'Mercedes'
        ]
        
        self.assertEqual(len(ORDEM_CARROS), 22)
        
        expected_pairs = []
        for team in expected_unique_teams:
            expected_pairs.extend([team, team])
            
        self.assertEqual(ORDEM_CARROS, expected_pairs)

    def test_presentation_service_assign_ballast(self):
        class MockGridConfig:
            exibir_lastro = True

        standings = [{'pos': i + 1, 'nome': f'Piloto {i+1}'} for i in range(23)]
        PresentationService.assign_ballast(standings, MockGridConfig())

        # P1 e P2: Cadillac
        self.assertEqual(standings[0]['carro'], 'Cadillac')
        self.assertEqual(standings[1]['carro'], 'Cadillac')

        # P3 e P4: Aston Martin
        self.assertEqual(standings[2]['carro'], 'Aston Martin')
        self.assertEqual(standings[3]['carro'], 'Aston Martin')

        # P5 e P6: Audi
        self.assertEqual(standings[4]['carro'], 'Audi')
        self.assertEqual(standings[5]['carro'], 'Audi')

        # P7 e P8: Haas
        self.assertEqual(standings[6]['carro'], 'Haas')
        self.assertEqual(standings[7]['carro'], 'Haas')

        # P9 e P10: Alpine
        self.assertEqual(standings[8]['carro'], 'Alpine')
        self.assertEqual(standings[9]['carro'], 'Alpine')

        # P11 e P12: Racing Bulls
        self.assertEqual(standings[10]['carro'], 'Racing Bulls')
        self.assertEqual(standings[11]['carro'], 'Racing Bulls')

        # P13 e P14: Williams
        self.assertEqual(standings[12]['carro'], 'Williams')
        self.assertEqual(standings[13]['carro'], 'Williams')

        # P15 e P16: Red Bull
        self.assertEqual(standings[14]['carro'], 'Red Bull')
        self.assertEqual(standings[15]['carro'], 'Red Bull')

        # P17 e P18: Ferrari
        self.assertEqual(standings[16]['carro'], 'Ferrari')
        self.assertEqual(standings[17]['carro'], 'Ferrari')

        # P19 e P20: McLaren
        self.assertEqual(standings[18]['carro'], 'McLaren')
        self.assertEqual(standings[19]['carro'], 'McLaren')

        # P21 e P22: Mercedes
        self.assertEqual(standings[20]['carro'], 'Mercedes')
        self.assertEqual(standings[21]['carro'], 'Mercedes')

        # P23: Extra
        self.assertEqual(standings[22]['carro'], 'Mercedes (Extra)')

if __name__ == '__main__':
    unittest.main()
