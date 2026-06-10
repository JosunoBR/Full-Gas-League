with open('run.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total linhas: {len(lines)}")
print("=== Primeiras 20 linhas ===")
for i, line in enumerate(lines[:20], 1):
    print(f"{i:3}: {line}", end='')
