from run import app
from app.models import db, HomeCache

def limpar():
    with app.app_context():
        print("Limpando cache da Home...")
        deleted = HomeCache.query.delete()
        db.session.commit()
        print(f"Cache limpo! ({deleted} registros removidos)")
        print("Recarregue a página Home para ver as alterações.")

if __name__ == "__main__":
    limpar()