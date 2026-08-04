import os
import time
import unittest
from run import app
from app.services.simhub_service import SimHubService

class CSVRetentionTestCase(unittest.TestCase):
    def test_csv_save_and_15_days_cleanup(self):
        basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        csv_dir = os.path.join(basedir, 'CSV')
        os.makedirs(csv_dir, exist_ok=True)

        # 1. Cria um arquivo CSV simulado com mais de 16 dias de idade
        old_filename = "test_old_race_2026.csv"
        old_filepath = os.path.join(csv_dir, old_filename)
        with open(old_filepath, "w") as f:
            f.write("=== RACE ===\n1,OldDriver,Old,Ferrari,01:30.000,0\n")

        # Modifica o mtime para 16 dias no passado (16 * 86400s)
        sixteen_days_ago = time.time() - (16 * 86400)
        os.utime(old_filepath, (sixteen_days_ago, sixteen_days_ago))

        # 2. Chama a função de salvamento e limpeza com retenção de 15 dias
        new_filename = "test_new_race_2026.csv"
        new_content = "=== RACE ===\n1,NewDriver,New,McLaren,01:29.000,0\n"
        saved_path = SimHubService.save_csv_and_cleanup_old(new_filename, new_content, days_retention=15)

        # 3. Validações
        self.assertTrue(os.path.exists(saved_path), "O novo arquivo CSV deve ser salvo na pasta CSV/")
        self.assertFalse(os.path.exists(old_filepath), "O arquivo com mais de 15 dias deve ser excluído automaticamente")

        # Limpeza do arquivo de teste recente criado
        if os.path.exists(saved_path):
            os.remove(saved_path)

if __name__ == '__main__':
    unittest.main()
