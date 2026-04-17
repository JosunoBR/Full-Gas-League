from pathlib import Path
import re
import py_compile

repo = Path(r'c:/Users/Josué/Documents/Sistema FullGas')
admin_path = repo / 'app' / 'routes' / 'admin.py'
run_path = repo / 'run.py'
public_path = repo / 'app' / 'routes' / 'public.py'

# Patch admin.py
text = admin_path.read_text(encoding='utf-8')
pattern = re.compile(
    r"(def data_health\(\):\n)([ \t]*all_active_seasons = Season\.query\.filter_by\(ativa=True\)\.order_by\(Season\.id\.desc\(\)\)\.all\(\)\n)([ \t]*selected_season_id = request\.args\.get\('s', type=int\)\n)",
    flags=re.MULTILINE
)
replacement = r"\1    all_seasons = Season.query.order_by(Season.id.desc()).all()\n\2\3"
new_text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit('Failed to patch admin.py: target block not found')
admin_path.write_text(new_text, encoding='utf-8')

# Patch run.py
run_text = run_path.read_text(encoding='utf-8')
needle = 'db.init_app(app)\n\n# Habilita o CORS'
replacement = (
    'db.init_app(app)\n\n'
    "UPLOAD_FOLDER = app.config.get('UPLOAD_FOLDER')\n"
    'if UPLOAD_FOLDER:\n'
    '    os.makedirs(UPLOAD_FOLDER, exist_ok=True)\n\n# Habilita o CORS'
)
if needle not in run_text:
    raise SystemExit('Failed to patch run.py: insertion point not found')
run_path.write_text(run_text.replace(needle, replacement), encoding='utf-8')

# Normalize public.py without BOM
public_text = public_path.read_text(encoding='utf-8-sig')
public_path.write_text(public_text, encoding='utf-8')

# Validate compilation
for p in (admin_path, run_path, public_path):
    py_compile.compile(str(p), doraise=True)

print('patched and compiled')
