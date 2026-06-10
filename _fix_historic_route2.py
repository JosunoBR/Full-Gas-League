"""
Substitui cirurgicamente a função historic() em admin.py
lendo o conteúdo real do arquivo antes de fazer qualquer alteração.
"""
import os

ADMIN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'routes', 'admin.py')

with open(ADMIN_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Encontra o bloco exato da função historic()
START_MARKER = "@admin_bp.route('/historic')"
start = content.find(START_MARKER)
if start < 0:
    print("ERRO: rota /historic não encontrada!")
    exit(1)

# Encontra o próximo @admin_bp.route depois desta função
end = content.find("\n@admin_bp.route(", start + len(START_MARKER))
if end < 0:
    print("ERRO: não encontrou o fim da função!")
    exit(1)

old_func = content[start:end]
print("=== FUNÇÃO ATUAL NO DISCO (primeiras 10 linhas) ===")
for i, line in enumerate(old_func.splitlines()[:10], 1):
    print(f"  {i}: {line}")

NEW_FUNC = """@admin_bp.route('/historic')
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

new_content = content[:start] + NEW_FUNC + content[end:]

with open(ADMIN_PATH, 'w', encoding='utf-8') as f:
    f.write(new_content)

# Verificação
with open(ADMIN_PATH, 'r', encoding='utf-8') as f:
    verify = f.read()

if "Race.query.join(RaceResult).distinct()" in verify:
    print("\n✅ admin.py atualizado com sucesso!")
    print("   A rota agora usa Race.query.join(RaceResult) - lendo os dados reais do banco.")
else:
    print("\n❌ Falha na verificação - a substituição não foi salva.")

print("\nReinicie o servidor: python run.py")
