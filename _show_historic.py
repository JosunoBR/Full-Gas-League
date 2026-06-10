"""Show CircuitHistory model and historic route"""
# 1. Show CircuitHistory model
print("=== CircuitHistory Model ===")
with open('app/models.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
in_model = False
for i, line in enumerate(lines):
    if 'class CircuitHistory' in line:
        in_model = True
    if in_model:
        print(f"  L{i+1}: {line.rstrip()}")
        if line.strip() == '' and in_model and i > 0 and lines[i-1].strip() == '':
            break
        if i > 0 and line.strip().startswith('class ') and 'CircuitHistory' not in line:
            break

# 2. Show historic route in admin.py
print("\n=== Historic Route in admin.py ===")
with open('app/routes/admin.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'historic' in line.lower() or (i > 0 and 'historic' in lines[i-1].lower() and line.strip()):
        # Show context
        start = max(0, i-1)
        end = min(len(lines), i+5)
        for j in range(start, end):
            print(f"  L{j+1}: {lines[j].rstrip()}")
        print("  ...")
        break

# 3. Show historic.html template
print("\n=== historic.html template ===")
with open('app/templates/admin/historic.html', 'r', encoding='utf-8') as f:
    content = f.read()
print(content[:3000])
