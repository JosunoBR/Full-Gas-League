"""Show lines 138-200 of public.py to find all g_cfg usages"""
with open('app/routes/public.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
print()
for i in range(137, min(220, len(lines))):
    line = lines[i].rstrip()
    marker = " >>>" if 'g_cfg.' in line else "    "
    print(f"{marker} L{i+1}: {line}")
