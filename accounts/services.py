"""
Serviço de criação de usuários por empresa.
Usado pelo painel da plataforma ao cadastrar um novo cliente.
"""
import secrets
import string

from django.contrib.auth.models import User
from django.db import transaction

from .models import PerfilUsuario


def _gerar_senha(tamanho: int = 12) -> str:
    alfabeto = string.ascii_letters + string.digits + '!@#$'
    # Garante ao menos 1 de cada categoria
    senha = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice('!@#$'),
    ]
    senha += [secrets.choice(alfabeto) for _ in range(tamanho - 4)]
    secrets.SystemRandom().shuffle(senha)
    return ''.join(senha)


def _gerar_username(nome_empresa: str) -> str:
    """Gera um username único baseado no nome da empresa."""
    base = (
        nome_empresa.lower()
        .replace(' ', '_')
        .encode('ascii', 'ignore')
        .decode()
    )
    base = ''.join(c for c in base if c.isalnum() or c == '_')[:20] or 'empresa'

    username = base
    contador = 1
    while User.objects.filter(username=username).exists():
        username = f'{base}_{contador}'
        contador += 1
    return username


class UsuarioEmpresaService:

    @classmethod
    @transaction.atomic
    def criar_admin_empresa(
        cls,
        empresa,
        email: str = '',
        nome: str = '',
        username: str = '',
        senha: str = '',
        role: str = PerfilUsuario.ROLE_ADMIN,
    ) -> tuple[User, str]:
        """
        Cria um usuário administrador vinculado à empresa.

        Retorna (user, senha_gerada).
        Se `senha` não for fornecida, gera uma aleatória segura.
        """
        senha_final = senha or _gerar_senha()
        username_final = username or _gerar_username(empresa.nome)

        # Divide nome em first/last
        partes = (nome or empresa.nome).split(' ', 1)
        first = partes[0]
        last  = partes[1] if len(partes) > 1 else ''

        user = User.objects.create_user(
            username   = username_final,
            email      = email or empresa.email,
            password   = senha_final,
            first_name = first,
            last_name  = last,
            is_active  = True,
            is_staff   = False,
        )

        # Garante que o signal já criou o perfil, depois atualiza
        perfil, _ = PerfilUsuario.objects.get_or_create(user=user)
        perfil.empresa = empresa
        perfil.role    = role
        perfil.ativo   = True
        perfil.save(update_fields=['empresa', 'role', 'ativo'])

        return user, senha_final

    @classmethod
    @transaction.atomic
    def desativar_usuarios_empresa(cls, empresa) -> int:
        """Desativa todos os usuários de uma empresa (ex: assinatura cancelada)."""
        perfis = PerfilUsuario.objects.filter(empresa=empresa, ativo=True)
        count = perfis.count()
        perfis.update(ativo=False)
        User.objects.filter(
            perfil__empresa=empresa
        ).update(is_active=False)
        return count

    @classmethod
    @transaction.atomic
    def reativar_usuarios_empresa(cls, empresa) -> int:
        """Reativa usuários ao renovar assinatura."""
        perfis = PerfilUsuario.objects.filter(empresa=empresa, ativo=False)
        count = perfis.count()
        perfis.update(ativo=True)
        User.objects.filter(
            perfil__empresa=empresa
        ).update(is_active=True)
        return count

