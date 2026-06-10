"""
Fix: change g_cfg.id to g_cfg['id'] in public.py line 140
"""
filepath = 'app/routes/public.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# The exact line to fix
old = "        g_id = g_cfg.id"
new = "        g_id = g_cfg['id']"

if old in content:
    content = content.replace(old, new, 1)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"CORRIGIDO: '{old.strip()}' -> '{new.strip()}'")
else:
    print("AVISO: Linha original nao encontrada!")

# Verify
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"\nVerificacao - Linhas 138-142:")
for i in range(137, min(142, len(lines))):
    print(f"  L{i+1}: {lines[i].rstrip()}")
