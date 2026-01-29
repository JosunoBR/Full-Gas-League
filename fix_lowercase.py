from run import app
from app.models import db, User, PilotProfile

with app.app_context():
    print("Iniciando conversão apenas de e-mails para minúsculas...")
    
    # 1. Converter apenas os E-mails para minúsculas (Garante login case-insensitive)
    users = User.query.all()
    for u in users:
        if u.email:
            u.email = u.email.lower()
    
    db.session.commit()
    print("Sucesso! E-mails padronizados.")
