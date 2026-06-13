from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class PerfilUsuario(models.Model):
    """
    Estende o User do Django vinculando-o a uma TenantCompany.

    Papel na arquitetura:
    - No MVP (shared schema): isola dados por empresa via FK nas queries.
    - Com django-tenants: o perfil deixa de ser necessário para isolamento
      (cada tenant tem seu próprio schema), mas pode permanecer para guardar
      preferências e permissões por usuário dentro do tenant.

    ROLE define o nível de acesso dentro da empresa:
    - admin   → acesso total à empresa (cadastros, locações, configurações)
    - operador → acesso operacional (sem configurações de plano/assinatura)
    - readonly → somente leitura (relatórios e consultas)
    """
    ROLE_ADMIN    = 'admin'
    ROLE_OPERADOR = 'operador'
    ROLE_READONLY = 'readonly'

    ROLE_CHOICES = [
        (ROLE_ADMIN,    'Administrador'),
        (ROLE_OPERADOR, 'Operador'),
        (ROLE_READONLY, 'Somente leitura'),
    ]

    user    = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    empresa = models.ForeignKey(
        'core.TenantCompany',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='usuarios',
    )
    role        = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_ADMIN)
    ativo       = models.BooleanField(default=True)
    criado_em   = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Perfil de Usuário'
        verbose_name_plural = 'Perfis de Usuário'

    def __str__(self):
        empresa = self.empresa.nome if self.empresa else 'sem empresa'
        return f'{self.user.username} ({empresa}) — {self.get_role_display()}'

    @property
    def is_admin_empresa(self):
        return self.role == self.ROLE_ADMIN

    @property
    def is_operador(self):
        return self.role == self.ROLE_OPERADOR

    @property
    def is_readonly(self):
        return self.role == self.ROLE_READONLY


@receiver(post_save, sender=User)
def criar_perfil_usuario(sender, instance, created, **kwargs):
    """Garante que todo User tenha um PerfilUsuario."""
    if created:
        PerfilUsuario.objects.get_or_create(user=instance)
