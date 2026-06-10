"""
Diagnostic: discover EXACTLY what Python sees in public.py
"""
import os, sys, importlib

target = os.path.join('app', 'routes', 'public.py')
abs_target = os.path.abspath(target)

print("=" * 70)
print(f"1. FILE ON DISK: {abs_target}")
print(f"   Exists: {os.path.exists(abs_target)}")
print(f"   Size: {os.path.getsize(abs_target)} bytes")
print()

# Read raw bytes to check for BOM
with open(abs_target, 'rb') as f:
    raw = f.read()
    
print(f"   First 20 bytes (hex): {raw[:20].hex(' ')}")
print(f"   Has UTF-8 BOM: {raw[:3] == b'\\xef\\xbb\\xbf'}")
print(f"   Has UTF-16 LE BOM: {raw[:2] == b'\\xff\\xfe'}")
print(f"   Has UTF-16 BE BOM: {raw[:2] == b'\\xfe\\xff'}")
print()

# Read as text and show lines around 140
with open(abs_target, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"   Total lines: {len(lines)}")
print()
print("2. LINES 108-148 OF THE FILE ON DISK:")
for i in range(107, min(148, len(lines))):
    marker = " >>>" if i == 139 else "    "
    print(f"{marker} L{i+1}: {lines[i].rstrip()}")

print()
print("3. SEARCHING FOR 'g_cfg.id' IN THE FILE:")
found = False
for i, line in enumerate(lines):
    if 'g_cfg' in line:
        print(f"   FOUND 'g_cfg' at L{i+1}: {line.rstrip()}")
        found = True
if not found:
    print("   NOT FOUND anywhere in the file!")

print()
print("4. SEARCHING FOR 'g_id = g_cfg' IN THE FILE:")
found2 = False
for i, line in enumerate(lines):
    if 'g_id = g_cfg' in line:
        print(f"   FOUND at L{i+1}: {line.rstrip()}")
        found2 = True
if not found2:
    print("   NOT FOUND anywhere in the file!")

print()
print("5. ALL FILES NAMED 'public.py' IN PROJECT:")
for root, dirs, files in os.walk('.'):
    # Don't skip any directories - include venv, .venv, etc
    for fname in files:
        if fname == 'public.py':
            full = os.path.join(root, fname)
            sz = os.path.getsize(full)
            print(f"   {full} ({sz} bytes)")

print()
print("6. PYTHON IMPORT RESOLUTION:")
# Check what Python actually resolves
sys.path.insert(0, '.')
try:
    spec = importlib.util.find_spec('app.routes.public')
    if spec and spec.origin:
        print(f"   Python resolves app.routes.public to: {spec.origin}")
        print(f"   Same as our file? {os.path.abspath(spec.origin) == abs_target}")
    else:
        print("   Could not resolve spec!")
except Exception as e:
    print(f"   Error: {e}")

print()
print("7. WHAT IS AT LINE 140 OF THE RESOLVED FILE:")
try:
    if spec and spec.origin:
        resolved = spec.origin
        with open(resolved, 'r', encoding='utf-8') as f:
            rlines = f.readlines()
        print(f"   Total lines in resolved file: {len(rlines)}")
        if len(rlines) >= 140:
            print(f"   L140: {rlines[139].rstrip()}")
        if len(rlines) >= 141:
            print(f"   L141: {rlines[140].rstrip()}")
except Exception as e:
    print(f"   Error: {e}")

print("=" * 70)
