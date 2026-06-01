from app.models import db, User, PilotProfile
from sqlalchemy import or_

class AuthService:
    @staticmethod
    def register_pilot(email, nickname, nome_real, telefone, password, confirm_password):
        """
        Executa a lógica de validação e criação de usuário e perfil de piloto.
        Retorna uma tupla: (sucesso: bool, mensagem_ou_erro: str)
        """
        email = (email or '').strip().lower()
        nickname = (nickname or '').strip()
        nome_real = (nome_real or '').strip()
        telefone = (telefone or '').strip()

        # Validação de campos obrigatórios
        if not email: return False, 'O campo E-mail é obrigatório.'
        if not nickname: return False, 'O campo Nickname é obrigatório.'
        if not nome_real: return False, 'O campo Nome Real é obrigatório.'
        if not password: return False, 'O campo Senha é obrigatório.'

        if nickname.lower() == nome_real.lower():
            return False, 'O Nickname (nome de piloto) não pode ser igual ao seu Nome Real.'

        if password != confirm_password:
            return False, 'As senhas não conferem.'

        # Verifica se email ou nickname já existem
        user_exists = User.query.filter(or_(User.email == email, User.username == nickname)).first()
        if user_exists:
            if user_exists.email == email:
                return False, 'Este e-mail já está cadastrado.'
            else:
                return False, 'Este nickname já está em uso. Por favor, escolha outro.'
        
        try:
            # Criação do Usuário
            new_user = User()
            new_user.email = email
            new_user.username = nickname[:50]
            new_user.role = 'PILOTO'
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.flush()

            # Criação do Perfil de Piloto
            new_profile = PilotProfile()
            new_profile.user_id = new_user.id
            new_profile.nickname = nickname[:50]
            new_profile.nome_real = nome_real[:100]
            new_profile.grid = 'SEM_GRID'
            new_profile.telefone = telefone[:20] if telefone else None
            
            db.session.add(new_profile)
            db.session.commit()

            return True, 'Conta criada com sucesso! Faça login para continuar.'
        except Exception as e:
            db.session.rollback()
            return False, f'Erro interno ao criar a conta: {str(e)}'
