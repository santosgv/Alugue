from django.db import models
from django.contrib.auth.models import User

class Notificacao(models.Model):
    TIPO_INFO = 'info'
    TIPO_ALERTA = 'alerta'
    TIPO_URGENTE = 'urgente'
    TIPO_SUCESSO = 'sucesso'

    TIPO_CHOICES = [
        (TIPO_INFO, 'Informação'),
        (TIPO_ALERTA, 'Alerta'),
        (TIPO_URGENTE, 'Urgente'),
        (TIPO_SUCESSO, 'Sucesso'),
    ]

    # Canal preparado para futuro WhatsApp/Email
    CANAL_INTERNO = 'interno'
    CANAL_EMAIL = 'email'
    CANAL_WHATSAPP = 'whatsapp'

    CANAL_CHOICES = [
        (CANAL_INTERNO, 'Interno'),
        (CANAL_EMAIL, 'E-mail'),
        (CANAL_WHATSAPP, 'WhatsApp'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notificacoes')
    titulo = models.CharField(max_length=200)
    mensagem = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default=TIPO_INFO)
    canal = models.CharField(max_length=20, choices=CANAL_CHOICES, default=CANAL_INTERNO)
    lida = models.BooleanField(default=False)
    enviada = models.BooleanField(default=False, help_text="Para canais externos (email/whatsapp)")
    locacao_ref = models.ForeignKey('locacoes.Locacao', on_delete=models.SET_NULL, null=True, blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_leitura = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Notificação'
        verbose_name_plural = 'Notificações'
        ordering = ['-data_criacao']

    def __str__(self):
        return f"{self.titulo} - {self.usuario.username}"

    def marcar_como_lida(self):
        from django.utils import timezone
        if not self.lida:
            self.lida = True
            self.data_leitura = timezone.now()
            self.save(update_fields=['lida', 'data_leitura'])

from .whatsapp_models import WhatsAppConfig