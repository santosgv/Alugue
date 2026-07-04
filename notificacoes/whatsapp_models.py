"""
notificacoes/whatsapp_models.py
================================
Model de configuração do WhatsApp por empresa.

Adicione ao notificacoes/models.py:
    from .whatsapp_models import WhatsAppConfig

E registre em notificacoes/admin.py:
    from .whatsapp_models import WhatsAppConfig
    admin.site.register(WhatsAppConfig, WhatsAppConfigAdmin)

Após criar, gere a migration:
    python manage.py makemigrations notificacoes
    python manage.py migrate
"""

from django.db import models
from django.utils import timezone


class WhatsAppConfig(models.Model):
    """
    Configuração do WhatsApp Business por empresa (tenant).

    Como obter os dados:
      1. Acesse developers.facebook.com
      2. Crie um App do tipo 'Business'
      3. Adicione o produto 'WhatsApp'
      4. Em 'WhatsApp > Introdução':
         - Phone Number ID   → campo phone_number_id
         - Access Token      → campo access_token (token temporário
                               ou permanente via System User)
      5. Configure o webhook apontando para:
         https://seudominio.com/whatsapp/webhook/
    """

    empresa         = models.OneToOneField(
        'core.TenantCompany',
        on_delete=models.CASCADE,
        related_name='whatsapp_config',
        verbose_name='Empresa',
    )
    phone_number_id = models.CharField(
        max_length=50,
        verbose_name='Phone Number ID',
        help_text='ID do número de telefone no Meta Business (ex: 123456789012345)',
    )
    access_token    = models.TextField(
        verbose_name='Access Token',
        help_text='Token de acesso da Meta API. Mantenha em segredo.',
    )
    numero_whatsapp = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Número WhatsApp',
        help_text='Número de exibição com DDI (ex: +55 11 99999-8888)',
    )
    ativo           = models.BooleanField(
        default=True,
        verbose_name='Ativo',
    )
    # Controle de notificações automáticas
    notif_locacao_criada    = models.BooleanField(default=True,  verbose_name='Notificar ao criar locação')
    notif_devolucao_amanha  = models.BooleanField(default=True,  verbose_name='Notificar devolução (dia anterior)')
    notif_atraso            = models.BooleanField(default=True,  verbose_name='Notificar atrasos')
    notif_cancelamento      = models.BooleanField(default=False, verbose_name='Notificar cancelamentos')

    # Auditoria
    configurado_em  = models.DateTimeField(auto_now_add=True)
    atualizado_em   = models.DateTimeField(auto_now=True)
    ultimo_envio_em = models.DateTimeField(null=True, blank=True)
    total_enviados  = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name        = 'Configuração WhatsApp'
        verbose_name_plural = 'Configurações WhatsApp'

    def __str__(self):
        return f"WhatsApp — {self.empresa.nome} ({self.numero_whatsapp or self.phone_number_id})"

    def registrar_envio(self):
        """Atualiza contadores após envio bem-sucedido."""
        self.ultimo_envio_em = timezone.now()
        self.total_enviados  += 1
        self.save(update_fields=['ultimo_envio_em', 'total_enviados'])