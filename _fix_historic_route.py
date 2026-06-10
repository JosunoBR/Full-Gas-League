"""
Diagnóstico + correção da rota /historic em admin.py.
Executa direto no banco para verificar os dados e reescreve a rota.
"""
import sqlite3, os, re

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'f1_league.db')
ADMIN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'routes', 'admin.py')

# ── 1. Diagnóstico direto no banco ──────────────────────────────────────────
print("=== DIAGNÓSTICO DO BANCO ===")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM race")
total_races = cur.fetchone()[0]
print(f"Total de corridas na tabela race: {total_races}")

cur.execute("SELECT COUNT(*) FROM race_result")
total_results = cur.fetchone()[0]
print(f"Total de resultados em race_result: {total_results}")

cur.execute("""
    SELECT r.id, r.nome_gp, r.pista, r.data_corrida, COUNT(rr.id) as n_results
    FROM race r
    JOIN race_result rr ON rr.race_id = r.id
    GROUP BY r.id
    LIMIT 10
""")
rows = cur.fetchall()
print(f"\nCorridas com resultados (primeiras 10 de {len(rows)+1}):")
for row in rows:
    print(f"  ID={row[0]} | {row[1]} | pista={row[2]} | data={row[3]} | resultados={row[4]}")

conn.close()

# ── 2. Lê o admin.py atual ───────────────────────────────────────────────────
print("\n=== VERIFICANDO admin.py ===")
with open(ADMIN_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Verifica qual versão da rota está no arquivo
if "historico_por_circuito[circuito] = {'corridas': [], 'stats': {}}" in content:
    print("✅ admin.py já tem a rota nova (com stats). Nenhuma alteração necessária.")
elif "historico_por_circuito[circuito] = []" in content:
    print("⚠️  admin.py ainda tem a rota ANTIGA. Aplicando correção...")

    OLD = """@admin_bp.route('/historic')
@login_required
def historic():
    \"\"\"
    Gera uma página de histórico lendo os resultados de todas as corridas,
    agrupando-os por circuito e ordenando por data.
    \"\"\"
    # 1. Buscar todas as corridas que possuem resultados, ordenadas por circuito e data.
    corridas_com_resultados = Race.query.join(RaceResult).distinct().order_by(Race.pista.asc(), Race.data_corrida.desc()).all()

    historico_por_circuito = {}

    for race in corridas_com_resultados:
        # 2. Extrair as informações de cada corrida.
        resultados = RaceResult.query.filter_by(race_id=race.id).all()
        
        primeiro = next((r.pilot for r in resultados if r.posicao == 1 and not r.dsq), None)
        segundo = next((r.pilot for r in resultados if r.posicao == 2 and not r.dsq), None)
        terceiro = next((r.pilot for r in resultados if r.posicao == 3 and not r.dsq), None)
        piloto_dia = next((r.pilot for r in resultados if r.piloto_do_dia), None)
        piloto_volta_rapida = next((r.pilot for r in resultados if r.volta_rapida), None)

        dados_corrida = {
            'nome_gp': race.nome_gp,
            'data': race.data_corrida,
            'season_name': race.season.nome,
            'grid_name': race.grid_config.nome if race.grid_config else race.grid,
            'pole_sitter': race.pole_sitter,
            'pole_time': race.pole_time,
            'primeiro': primeiro,
            'segundo': segundo,
            'terceiro': terceiro,
            'melhor_tempo_piloto': piloto_volta_rapida,
            'piloto_do_dia': piloto_dia,
            'race_id': race.id
        }
        
        # 3. Agrupar no dicionário pelo nome do circuito.
        circuito = race.pista
        if circuito not in historico_por_circuito:
            historico_por_circuito[circuito] = []
        
        historico_por_circuito[circuito].append(dados_corrida)

    return render_template('admin/historic.html', historico=historico_por_circuito)"""

    NEW = """@admin_bp.route('/historic')
@login_required
def historic():
    \"\"\"
    Lê todas as corridas com resultados, agrupa por circuito e calcula
    estatísticas por pista (vencedor mais frequente, total de corridas, etc.).
    \"\"\"
    corridas_com_resultados = Race.query.join(RaceResult).distinct().order_by(
        Race.pista.asc(), Race.data_corrida.desc()
    ).all()

    historico_por_circuito = {}

    for race in corridas_com_resultados:
        resultados = RaceResult.query.filter_by(race_id=race.id).all()

        primeiro     = next((r.pilot for r in resultados if r.posicao == 1 and not r.dsq), None)
        segundo      = next((r.pilot for r in resultados if r.posicao == 2 and not r.dsq), None)
        terceiro     = next((r.pilot for r in resultados if r.posicao == 3 and not r.dsq), None)
        piloto_dia   = next((r.pilot for r in resultados if r.piloto_do_dia), None)
        volta_rapida = next((r.pilot for r in resultados if r.volta_rapida), None)

        dados_corrida = {
            'nome_gp':       race.nome_gp,
            'data':          race.data_corrida,
            'season_name':   race.season.nome,
            'grid_name':     race.grid_config.nome if race.grid_config else race.grid,
            'pole_sitter':   race.pole_sitter,
            'pole_time':     race.pole_time,
            'primeiro':      primeiro,
            'segundo':       segundo,
            'terceiro':      terceiro,
            'volta_rapida':  volta_rapida,
            'piloto_do_dia': piloto_dia,
            'race_id':       race.id,
            'total_pilotos': len(resultados),
        }

        circuito = race.pista
        if circuito not in historico_por_circuito:
            historico_por_circuito[circuito] = {'corridas': [], 'stats': {}}
        historico_por_circuito[circuito]['corridas'].append(dados_corrida)

    # Calcula estatísticas por circuito
    for circuito, dados in historico_por_circuito.items():
        corridas = dados['corridas']
        vitorias, poles = {}, {}
        for c in corridas:
            if c['primeiro']:
                nick = c['primeiro'].nickname
                vitorias[nick] = vitorias.get(nick, 0) + 1
            if c['pole_sitter']:
                nick = c['pole_sitter'].nickname
                poles[nick] = poles.get(nick, 0) + 1

        maior_vencedor = max(vitorias, key=vitorias.get) if vitorias else None
        maior_pole     = max(poles,    key=poles.get)    if poles    else None

        dados['stats'] = {
            'total_corridas':  len(corridas),
            'maior_vencedor':  maior_vencedor,
            'vitorias_lider':  vitorias.get(maior_vencedor, 0) if maior_vencedor else 0,
            'maior_pole':      maior_pole,
            'poles_lider':     poles.get(maior_pole, 0) if maior_pole else 0,
            'ultima_data':     corridas[0]['data'],
        }

    total_corridas_geral = sum(d['stats']['total_corridas'] for d in historico_por_circuito.values())

    return render_template(
        'admin/historic.html',
        historico=historico_por_circuito,
        total_circuitos=len(historico_por_circuito),
        total_corridas_geral=total_corridas_geral,
    )"""

    if OLD in content:
        content = content.replace(OLD, NEW, 1)
        with open(ADMIN_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ Rota historic() atualizada com sucesso em admin.py!")
    else:
        print("⚠️  Texto exato não encontrado. Buscando pela assinatura da função...")
        # Fallback: substitui pela posição da função
        idx = content.find("@admin_bp.route('/historic')")
        if idx >= 0:
            # Encontra o próximo @admin_bp.route depois desta função
            next_route = content.find("\n@admin_bp.route(", idx + 10)
            if next_route < 0:
                next_route = content.find("\n@admin_bp.route(", idx + 5)
            if next_route > idx:
                new_content = content[:idx] + NEW + "\n" + content[next_route+1:]
                with open(ADMIN_PATH, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print("✅ Rota substituída pelo método fallback!")
            else:
                print("❌ Não conseguiu localizar o fim da função historic().")
        else:
            print("❌ Rota /historic não encontrada no arquivo!")
else:
    print("❓ Estado desconhecido da rota. Verificando manualmente...")
    idx = content.find("@admin_bp.route('/historic')")
    if idx >= 0:
        print(f"  Rota encontrada na posição {idx}. Trecho:")
        print("  " + content[idx:idx+200].replace('\n', '\n  '))
    else:
        print("  ❌ Rota /historic NÃO encontrada no admin.py!")

print("\n=== CONCLUÍDO ===")
print("Reinicie o servidor: python run.py")
