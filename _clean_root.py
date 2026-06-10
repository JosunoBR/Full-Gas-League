import os

files_to_delete = [
    # Files starting with '_'
    *[f for f in os.listdir('.') if f.startswith('_') and f.endswith('.py') and f != '_clean_root.py'],
    # Other legacy/one-off files
    'atualizar_bd.py',
    'auditar_pontos_equipe.py',
    'cadastrar_equipes_finais.py',
    'consertar_tabela_fotos.py',
    'corrigir_equipes.py',
    'corrigir_pontos.py',
    'corrigir_vinculos_pilotos.py',
    'db_diag_home.py',
    'estornar_penalidades_manuais.py',
    'estornar_punicoes.py',
    'fix_lowercase.py',
    'fix_site_startup.py',
    'limpar_cache.py',
    'limpar_pilotos_grid_ids.py',
    'limpeza_total_ids.py',
    'migrar_arquitetura.py',
    'migrar_dados_legado.py',
    'migrar_fotos_grid.py',
    'remover_equipes_inativas.py',
    'reparar_fotos_grid.py',
    'restaurar_home.py',
    'restaurar_vinculos_do_backup.py',
    'verificar_pontos.py',
    'vincular_grids_temporadas.py',
    'sincronizar_pilotos_equipes.py',
    'sincronizar_resultados_equipes.py',
    'relatorio_erros_pilotos_equipes.csv',
    'relatorio_erros_pilotos_equipes.txt',
    'db_check.py',
    'db_diag_las_vegas.py',
    'unificar_pistas.py',
    'db_check_result.txt',
    'check_vegas_pole.py',
    'test_parse.py',
    'find_all_historic.py'
]

print("Files to delete:")
for f in files_to_delete:
    if os.path.exists(f):
        try:
            os.remove(f)
            print(f"  [DELETED] {f}")
        except Exception as e:
            print(f"  [ERROR] {f}: {e}")
    else:
        print(f"  [NOT FOUND] {f}")
