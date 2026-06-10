"""
Fix #2: The constructor correction block outputs {'team': obj, 'points': float}
but the template expects {'equipe': dict, 'pontos': float, 'vitorias': int}.
"""
filepath = 'app/routes/public.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Change team_points structure to use correct keys
old1 = "            team_points.setdefault(team.id, {'team': team, 'points': 0.0})['points'] += net_points"
new1 = """            if team.id not in team_points:
                team_points[team.id] = {
                    'equipe': team.to_dict() if hasattr(team, 'to_dict') else {'id': team.id, 'nome': getattr(team, 'nome', 'N/A'), 'logo': getattr(team, 'logo', None)},
                    'pontos': 0.0,
                    'vitorias': 0
                }
            team_points[team.id]['pontos'] += net_points
            if getattr(rr, 'posicao', None) == 1 and not getattr(rr, 'dsq', False):
                team_points[team.id]['vitorias'] += 1"""

if old1 in content:
    content = content.replace(old1, new1, 1)
    print("FIX 1 OK: team_points structure corrigida")
else:
    print("AVISO: Fix 1 - texto nao encontrado!")

# Fix 2: Change sort key to use 'pontos' instead of 'points'
old2 = "        new_constructors_data[g_id] = sorted(team_points.values(), key=lambda x: x['points'], reverse=True)"
new2 = "        new_constructors_data[g_id] = sorted(team_points.values(), key=lambda x: x['pontos'], reverse=True)"

if old2 in content:
    content = content.replace(old2, new2, 1)
    print("FIX 2 OK: sort key corrigida para 'pontos'")
else:
    print("AVISO: Fix 2 - texto nao encontrado!")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

# Verify
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"\nVerificacao - Linhas 145-168:")
for i in range(144, min(168, len(lines))):
    print(f"  L{i+1}: {lines[i].rstrip()}")
