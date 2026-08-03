import sys
import os
sys.path.insert(0, r"c:\Users\Josué\Documents\Sistema FullGas")

from run import app
from jinja2 import Environment, FileSystemLoader

with app.app_context():
    try:
        env = Environment(loader=FileSystemLoader(r"c:\Users\Josué\Documents\Sistema FullGas\app\templates"))
        template1 = env.get_template("pilot/profile.html")
        template2 = env.get_template("admin/view_protest.html")
        
        # Test importing func in public
        from app.routes.public import func
        print("Importação de 'func' e 'abort' em public.py OK!")
    except Exception as e:
        print(f"Erro no teste: {e}")
