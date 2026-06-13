from django.db import models
from django.contrib.auth.models import User


class CategoriaProduto(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Produto(models.Model):
    STATUS_ATIVO = 'ativo'
    STATUS_INATIVO = 'inativo'
    STATUS_MANUTENCAO = 'manutencao'

    STATUS_CHOICES = [
        (STATUS_ATIVO, 'Ativo'),
        (STATUS_INATIVO, 'Inativo'),
        (STATUS_MANUTENCAO, 'Em Manutenção'),
    ]

    nome = models.CharField(max_length=200, verbose_name="Nome")
    categoria = models.ForeignKey(CategoriaProduto, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Categoria")
    codigo_interno = models.CharField(max_length=50, unique=True, verbose_name="Código Interno")
    quantidade_total = models.PositiveIntegerField(default=1, verbose_name="Quantidade Total")
    quantidade_disponivel = models.PositiveIntegerField(default=1, verbose_name="Quantidade Disponível")
    valor_diario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Diário (R$)")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    foto = models.ImageField(upload_to='produtos/', blank=True, null=True, verbose_name="Foto")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ATIVO, verbose_name="Status")
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'
        ordering = ['nome']

    def __str__(self):
        return f"{self.codigo_interno} - {self.nome}"

    @property
    def quantidade_locada(self):
        return self.quantidade_total - self.quantidade_disponivel

    @property
    def percentual_ocupacao(self):
        if self.quantidade_total == 0:
            return 0
        return round((self.quantidade_locada / self.quantidade_total) * 100)