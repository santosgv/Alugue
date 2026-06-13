from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from clientes.models import Cliente
from produtos.models import Produto


class Locacao(models.Model):
    STATUS_PENDENTE = 'pendente'
    STATUS_ATIVA = 'ativa'
    STATUS_FINALIZADA = 'finalizada'
    STATUS_CANCELADA = 'cancelada'
    STATUS_ATRASADA = 'atrasada'

    STATUS_CHOICES = [
        (STATUS_PENDENTE, 'Pendente'),
        (STATUS_ATIVA, 'Ativa'),
        (STATUS_FINALIZADA, 'Finalizada'),
        (STATUS_CANCELADA, 'Cancelada'),
        (STATUS_ATRASADA, 'Atrasada'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, verbose_name="Cliente")
    data_inicio = models.DateField(verbose_name="Data de Início")
    data_fim_prevista = models.DateField(verbose_name="Data Fim Prevista")
    data_fim_real = models.DateField(null=True, blank=True, verbose_name="Data Fim Real")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDENTE, verbose_name="Status")
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Valor Total (R$)")
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='locacoes_criadas')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Locação'
        verbose_name_plural = 'Locações'
        ordering = ['-criado_em']

    def __str__(self):
        return f"Locação #{self.pk} - {self.cliente.nome}"

    @property
    def dias_locacao(self):
        return (self.data_fim_prevista - self.data_inicio).days + 1

    @property
    def esta_atrasada(self):
        hoje = timezone.localdate()
        return self.status == self.STATUS_ATIVA and self.data_fim_prevista < hoje

    @property
    def vence_amanha(self):
        from datetime import timedelta
        amanha = timezone.localdate() + timedelta(days=1)
        return self.status == self.STATUS_ATIVA and self.data_fim_prevista == amanha

    def calcular_valor_total(self):
        total = sum(item.valor_total for item in self.itens.all())
        self.valor_total = total
        self.save(update_fields=['valor_total'])
        return total


class ItemLocacao(models.Model):
    locacao = models.ForeignKey(Locacao, on_delete=models.CASCADE, related_name='itens', verbose_name="Locação")
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, verbose_name="Produto")
    quantidade = models.PositiveIntegerField(default=1, verbose_name="Quantidade")
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Unitário (R$)")
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor Total (R$)")

    class Meta:
        verbose_name = 'Item da Locação'
        verbose_name_plural = 'Itens da Locação'

    def __str__(self):
        return f"{self.quantidade}x {self.produto.nome}"

    def save(self, *args, **kwargs):
        dias = self.locacao.dias_locacao
        self.valor_total = self.quantidade * self.valor_unitario * dias
        super().save(*args, **kwargs)