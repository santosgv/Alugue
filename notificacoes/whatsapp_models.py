from django.db import models
from django.utils import timezone


class WhatsAppConfig(models.Model):
    """
    Configuração da instância WhatsApp por empresa (TenantCompany).

    Cada empresa tem sua própria instância na Evolution API,
    identificada por um instance_name único (ex: 'locagest_empresa_5').
    O número do WhatsApp vinculado fica na Evolution API — aqui
    guardamos apenas os metadados e preferências de notificação.
    """

    ESTADO_DESCONECTADO = 'desconectado'
    ESTADO_CONECTANDO   = 'conectando'
    ESTADO_CONECTADO    = 'conectado'

    empresa = models.OneToOneField(
        'core.TenantCompany',
        on_delete=models.CASCADE,
        related_name='whatsapp_config',
        verbose_name='Empresa',
    )

    # Nome da instância na Evolution API — único por empresa
    instance_name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Nome da Instância',
        help_text='Identificador interno na Evolution API (ex: locagest_empresa_5)',
    )

    # Número vinculado — preenchido após escanear o QR
    numero_vinculado = models.CharField(
        max_length=30,
        blank=True,
        verbose_name='Número Vinculado',
        help_text='Número do WhatsApp conectado (preenchido automaticamente)',
    )

    ativo = models.BooleanField(default=True, verbose_name='Ativo')

    # ── Preferências de notificação automática ────────────────
    notif_locacao_criada   = models.BooleanField(
        default=True, verbose_name='Confirmar locação criada',
    )
    notif_devolucao_amanha = models.BooleanField(
        default=True, verbose_name='Lembrete devolução (dia anterior)',
    )
    notif_atraso           = models.BooleanField(
        default=True, verbose_name='Avisos de atraso (diário)',
    )
    notif_cancelamento     = models.BooleanField(
        default=False, verbose_name='Informar cancelamento',
    )

    # ── Auditoria ─────────────────────────────────────────────
    configurado_em   = models.DateTimeField(auto_now_add=True)
    atualizado_em    = models.DateTimeField(auto_now=True)
    ultimo_envio_em  = models.DateTimeField(null=True, blank=True)
    total_enviados   = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name        = 'Configuração WhatsApp'
        verbose_name_plural = 'Configurações WhatsApp'

    def __str__(self):
        return f"WhatsApp — {self.empresa.nome} ({self.numero_vinculado or self.instance_name})"

    def registrar_envio(self):
        """Atualiza contadores após envio bem-sucedido."""
        self.ultimo_envio_em  = timezone.now()
        self.total_enviados  += 1
        self.save(update_fields=['ultimo_envio_em', 'total_enviados'])

    def estado_atual(self) -> str:
        """
        Consulta o estado real da instância na Evolution API.
        Não armazenado em banco — sempre consultado ao vivo.
        """
        from .whatsapp_service import status_instancia
        try:
            data  = status_instancia(self.instance_name)
            state = data.get('instance', {}).get('state', 'close')
            if state == 'open':
                return self.ESTADO_CONECTADO
            if state == 'connecting':
                return self.ESTADO_CONECTANDO
        except Exception:
            pass
        return self.ESTADO_DESCONECTADO

    @property
    def esta_conectado(self) -> bool:
        return self.estado_atual() == self.ESTADO_CONECTADO
