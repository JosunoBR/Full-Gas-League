from datetime import timedelta
from app.models import db, Protesto
from app.utils import get_brasilia_now

class ProtestService:
    @staticmethod
    def is_defense_open(protesto):
        """Verifica se o protesto ainda está dentro da janela de 48h de defesa."""
        if not protesto or not protesto.data_criacao:
            return False
        deadline = protesto.data_criacao + timedelta(hours=48)
        return get_brasilia_now() <= deadline

    @staticmethod
    def atualizar_protestos_expirados():
        """
        Verifica todos os protestos com status 'AGUARDANDO_DEFESA' cujo prazo de 48h
        já expirou e atualiza automaticamente seu status para 'EM_VOTACAO'.
        """
        agora = get_brasilia_now()
        limite = agora - timedelta(hours=48)
        
        expirados = Protesto.query.filter(
            Protesto.status == 'AGUARDANDO_DEFESA',
            Protesto.data_criacao.isnot(None),
            Protesto.data_criacao <= limite
        ).all()
        
        if expirados:
            for p in expirados:
                p.status = 'EM_VOTACAO'
            db.session.commit()
            
        return expirados
