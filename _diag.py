# Diagnostic script to find what Python actually sees
import os

filepath = os.path.join('app', 'routes', 'public.py')

print(f"=== Reading: {os.path.abspath(filepath)} ===")
print(f"File exists: {os.path.exists(filepath)}")
print(f"File size: {os.path.getsize(filepath)} bytes")
print()

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
print()

# Show lines around 140
print("=== Lines 108-145 ===")
for i in range(107, min(145, len(lines))):
    print(f"  L{i+1}: {lines[i].rstrip()}")

print()

# Search for g_cfg anywhere in the file
print("=== Searching for 'g_cfg' in file ===")
for i, line in enumerate(lines):
    if 'g_cfg' in line:
        print(f"  FOUND at L{i+1}: {line.rstrip()}")

# Search for 'g_id = g_cfg' 
print()
print("=== Searching for 'g_id = g_cfg' in file ===")
for i, line in enumerate(lines):
    if 'g_id = g_cfg' in line:
        print(f"  FOUND at L{i+1}: {line.rstrip()}")

# Check if there's a BOM
print()
with open(filepath, 'rb') as f:
    first_bytes = f.read(10)
print(f"First 10 bytes (raw): {first_bytes}")
has_bom = first_bytes[:3] == b'\xef\xbb\xbf'
print(f"Has UTF-8 BOM: {has_bom}")

# Check for any other public.py files
print()
print("=== Searching for other public.py files ===")
for root, dirs, files in os.walk('.'):
    for fname in files:
        if fname == 'public.py':
            full = os.path.join(root, fname)
            print(f"  Found: {full} ({os.path.getsize(full)} bytes)")

# Check __pycache__
print()
pycache_dir = os.path.join('app', 'routes', '__pycache__')
print(f"=== __pycache__ contents ===")
if os.path.exists(pycache_dir):
    for f in os.listdir(pycache_dir):
        full = os.path.join(pycache_dir, f)
        print(f"  {f} ({os.path.getsize(full)} bytes, modified: {os.path.getmtime(full)})")
else:
    print("  Directory does not exist")
