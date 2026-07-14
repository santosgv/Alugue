from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import datetime

from django.conf import settings
from .recursos_config import RECURSOS_CONFIG, is_em_desenvolvimento
from django_tenants.models import TenantMixin,DomainMixin

#─────────────────────────────────────
# PLANO DE ASSINATURA
# ─────────────────────────────────────────────────────────────

class SubscriptionPlan(models.Model):
    PLANO_FREE     = 'trial'
    PLANO_BASICO   = 'basico'
    PLANO_PRO      = 'pro'
    PLANO_PREMIUM  = 'premium'

    PLANO_CHOICES = [
        (PLANO_FREE,    'Trial'),
        (PLANO_BASICO,  'Básico'),
        (PLANO_PRO,     'Pro'),
        (PLANO_PREMIUM, 'Premium'),
    ]

    ICONE_MAP = {
        PLANO_FREE:    'bi bi-rocket-takeoff',
        PLANO_BASICO:  'bi-box',
        PLANO_PRO:     'bi-lightning-charge-fill',
        PLANO_PREMIUM: 'bi-gem',
    }

    COR_MAP = {
        PLANO_FREE:    "#050505",
        PLANO_BASICO:  '#64748b',
        PLANO_PRO:     '#3b82f6',
        PLANO_PREMIUM: '#8b5cf6',
    }

    nome              = models.CharField(max_length=100)
    slug              = models.SlugField(unique=True, choices=PLANO_CHOICES)
    descricao         = models.TextField(blank=True, help_text="Subtítulo exibido na página de planos")
    limite_clientes   = models.IntegerField(default=100,  help_text="0 = ilimitado")
    limite_produtos   = models.IntegerField(default=100,  help_text="0 = ilimitado")
    limite_categorias = models.IntegerField(default=100,  help_text="0 = ilimitado")
    limite_locacoes   = models.IntegerField(default=0,    help_text="0 = ilimitado")
    limite_usuarios   = models.IntegerField(default=2,    help_text="0 = ilimitado")
    recursos          = models.JSONField(
        default=dict,
        help_text=(
            "Chaves suportadas: whatsapp (bool), multiusuario (bool), "
            "relatorios (bool), api_acesso (bool), suporte_prioritario (bool)"
        )
    )
    preco_mensal      = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    preco_anual       = models.DecimalField(max_digits=8, decimal_places=2, default=0,
                                            help_text="Preço total anual (desconto embutido)")
    destaque          = models.BooleanField(default=False, help_text="Exibir badge 'Mais popular'")
    ativo             = models.BooleanField(default=True)
    ordem             = models.PositiveSmallIntegerField(default=0, help_text="Ordem de exibição")
    criado_em         = models.DateTimeField(auto_now_add=True)

    # ── Stripe: IDs criados no dashboard ou via sync_stripe_plans ──
    stripe_product_id      = models.CharField(max_length=100, blank=True)
    stripe_price_id_mensal = models.CharField(max_length=100, blank=True)
    stripe_price_id_anual  = models.CharField(max_length=100, blank=True)
 

    class Meta:
        verbose_name        = 'Plano de Assinatura'
        verbose_name_plural = 'Planos de Assinatura'
        ordering            = ['ordem', 'preco_mensal']

    def __str__(self):
        return self.nome
    
    def get_recurso_status(self, recurso_name):
        """Usando a configuração centralizada"""
        # Verificar se está em desenvolvimento (global)
        if is_em_desenvolvimento(recurso_name):
            return 'em_desenvolvimento'
        
        # Verificar se está ativo neste plano
        if self.tem_recurso(recurso_name):
            return 'ativo'
        
        return 'indisponivel'
    
    def get_recurso_previsao(self, recurso_name):
        """Retorna a previsão de lançamento se disponível"""
        config = RECURSOS_CONFIG.get(recurso_name)
        return config.previsao_lancamento if config else None

    # ── helpers de limites ─────────────────────────────────────
    @property
    def clientes_ilimitados(self):
        return self.limite_clientes == 0

    @property
    def produtos_ilimitados(self):
        return self.limite_produtos == 0
    
    @property
    def categorias_ilimitados(self):
        return self.limite_categorias == 0

    @property
    def locacoes_ilimitadas(self):
        return self.limite_locacoes == 0
    
    @property
    def usuarios_ilimitados(self):
        return self.limite_usuarios == 0
    
    @property
    def eh_gratuito(self) -> bool:
        """Plano free não passa pelo Stripe — ativação é direta, sem checkout."""
        return self.preco_mensal == 0 and self.preco_anual == 0
    
 
    def stripe_price_id(self, ciclo: str) -> str:
        """Retorna o price_id da Stripe correspondente ao ciclo."""
        return self.stripe_price_id_anual if ciclo == 'anual' else self.stripe_price_id_mensal

    # ── helpers de recursos ────────────────────────────────────
    def tem_recurso(self, chave: str) -> bool:
        return bool(self.recursos.get(chave, False))

    @property
    def tem_whatsapp(self):
        return self.tem_recurso('whatsapp')


    @property
    def tem_relatorios(self):
        return self.tem_recurso('relatorios')

    @property
    def tem_api(self):
        return self.tem_recurso('api_acesso')

    @property
    def tem_suporte_prioritario(self):
        return self.tem_recurso('suporte_prioritario')

    # ── display helpers ────────────────────────────────────────
    @property
    def icone(self):
        return self.ICONE_MAP.get(self.slug, 'bi-box')

    @property
    def cor(self):
        return self.COR_MAP.get(self.slug, '#64748b')

    @property
    def label_clientes(self):
        return 'Ilimitado' if self.clientes_ilimitados else str(self.limite_clientes)

    @property
    def label_produtos(self):
        return 'Ilimitado' if self.produtos_ilimitados else str(self.limite_produtos)
    
    @property
    def label_usuarios(self):
        return 'Ilimitado' if self.usuarios_ilimitados else str(self.limite_usuarios)

    @property
    def label_categorias(self):
        return 'Ilimitado' if self.categorias_ilimitados else str(self.limite_categorias)

    @property
    def desconto_anual_pct(self):
        """Percentual de desconto do plano anual vs mensal×12."""
        if not self.preco_mensal or not self.preco_anual:
            return 0
        anual_sem_desconto = self.preco_mensal * 12
        return int(round((1 - self.preco_anual / anual_sem_desconto) * 100))


# ─────────────────────────────────────────────────────────────
# EMPRESA (TENANT)
# ─────────────────────────────────────────────────────────────

class TenantCompany(TenantMixin, models.Model):

    #Empresa / Tenant.

    #Herança:
    #─ MVP (sem django-tenants): TenantMixin é um stub abstract, sem campos extras.
    #─ Com django-tenants: TenantMixin adiciona `schema_name` (obrigatório),
    #  `create_schema` e `drop_schema`. O campo auto_create_schema=True
    #  faz o django-tenants criar o schema PostgreSQL automaticamente
    #  ao salvar o primeiro registro.
#
    #Ponto de migração:
    #─ Quando ativar django-tenants, rode:
    #    python manage.py migrate_schemas --shared
    #─ Para criar um novo tenant:
    #    python manage.py create_tenant
    #\"\"\"

    # django-tenants: cria schema automaticamente ao salvar
    # Em modo MVP este atributo é ignorado (TenantMixin é stub)
    auto_create_schema = True
    auto_drop_schema = True

    nome           = models.CharField(max_length=200)
    cnpj           = models.CharField(max_length=18, blank=True)
    email          = models.EmailField(blank=True)
    telefone       = models.CharField(max_length=20, blank=True)
    plano          = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT,
        null=True, blank=True, related_name='empresas'
    )
    ativo          = models.BooleanField(default=True)
    data_cadastro  = models.DateTimeField(auto_now_add=True)
    data_expiracao = models.DateField(null=True, blank=True)

    # ── Stripe: customer vinculado a esta empresa ───────────────
    stripe_customer_id = models.CharField(max_length=100, blank=True, db_index=True)

    class Meta:
        verbose_name        = 'Empresa'
        verbose_name_plural = 'Empresas'
        ordering            = ['nome']

    def __str__(self):
        return self.nome

    @property
    def assinatura_ativa(self):
        sub = self.assinaturas.filter(status=Assinatura.STATUS_ATIVA).first()
        return sub

    @property
    def plano_atual(self):
        sub = self.assinatura_ativa
        return sub.plano if sub else self.plano
    
    @property
    def primary_domain(self):
        return self.domains.filter(is_primary=True).first()

    @property
    def url(self):
        domain = self.primary_domain

        if not domain:
            return ""

        protocolo = "https" if not settings.DEBUG else "http"
        return f"{protocolo}://{domain.domain}"


class Domain(DomainMixin):

    #Domínio / subdomínio vinculado a um TenantCompany.

    #Com django-tenants:
    #─ Cada empresa pode ter um ou mais domínios.
    #─ Ex: empresa1.locagest.com.br → schema empresa1
    #─ O campo `tenant` (FK) e `domain` (CharField) vêm do DomainMixin.
    #─ O campo `is_primary` define o domínio principal.

    #Em modo MVP:
    #─ DomainMixin é stub abstract, esta tabela não é criada.
    #─ A migração é gerada mas não aplicada (sem django-tenants instalado).
  
    pass

# ─────────────────────────────────────────────────────────────
# ASSINATURA
# ─────────────────────────────────────────────────────────────

class Assinatura(models.Model):
    STATUS_TRIAL     = 'trial'
    STATUS_ATIVA     = 'ativa'
    STATUS_SUSPENSA  = 'suspensa'
    STATUS_CANCELADA = 'cancelada'
    STATUS_EXPIRADA  = 'expirada'
    STATUS_PENDENTE_PAGAMENTO = 'pendente_pagamento'

    STATUS_CHOICES = [
        (STATUS_TRIAL,     'Trial'),
        (STATUS_ATIVA,     'Ativa'),
        (STATUS_SUSPENSA,  'Suspensa'),
        (STATUS_CANCELADA, 'Cancelada'),
        (STATUS_EXPIRADA,  'Expirada'),
        (STATUS_PENDENTE_PAGAMENTO, 'Pagamento Pendente'),
    ]

    CICLO_MENSAL = 'mensal'
    CICLO_ANUAL  = 'anual'

    CICLO_CHOICES = [
        (CICLO_MENSAL, 'Mensal'),
        (CICLO_ANUAL,  'Anual'),
    ]

    empresa        = models.ForeignKey(
        TenantCompany, on_delete=models.CASCADE, related_name='assinaturas'
    )
    plano          = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT, related_name='assinaturas'
    )
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_TRIAL)
    ciclo          = models.CharField(max_length=10, choices=CICLO_CHOICES, default=CICLO_MENSAL)
    data_inicio    = models.DateField()
    data_fim       = models.DateField(null=True, blank=True)
    data_renovacao = models.DateField(null=True, blank=True)
    valor_cobrado  = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    cancelada_em   = models.DateTimeField(null=True, blank=True)
    motivo_cancel  = models.TextField(blank=True)
    criado_por     = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    criado_em      = models.DateTimeField(auto_now_add=True)
    atualizado_em  = models.DateTimeField(auto_now=True)

    # ── Stripe: vínculos da assinatura ───────────────────────────
    stripe_subscription_id     = models.CharField(max_length=100, blank=True, db_index=True)
    stripe_checkout_session_id = models.CharField(max_length=100, blank=True)
 
    criado_por     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    criado_em      = models.DateTimeField(auto_now_add=True)
    atualizado_em  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Assinatura'
        verbose_name_plural = 'Assinaturas'
        ordering            = ['-criado_em']

    def __str__(self):
        return f"{self.empresa} — {self.plano} ({self.get_status_display()})"

    @property
    def esta_ativa(self):
        return self.status in [self.STATUS_ATIVA, self.STATUS_TRIAL]

    @property
    def dias_restantes(self):
        if not self.data_fim:
            return None
        delta = self.data_fim - timezone.localdate()
        return max(0, delta.days)

    @property
    def vencida(self):
        if not self.data_fim:
            return False
        return timezone.localdate() > self.data_fim


# ─────────────────────────────────────────────────────────────
# USO / MÉTRICAS (snapshot diário por empresa)
# ─────────────────────────────────────────────────────────────

class UsoAssinatura(models.Model):
    """Registra uso diário para histórico e billing futuro."""
    empresa          = models.ForeignKey(TenantCompany, on_delete=models.CASCADE, related_name='usos')
    data             = models.DateField(default=timezone.localdate)
    total_clientes   = models.PositiveIntegerField(default=0)
    total_categorias = models.PositiveIntegerField(default=0)
    total_produtos   = models.PositiveIntegerField(default=0)
    total_locacoes   = models.PositiveIntegerField(default=0)
    criado_em        = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Uso da Assinatura'
        verbose_name_plural = 'Uso das Assinaturas'
        unique_together     = ('empresa', 'data')
        ordering            = ['-data']

    def __str__(self):
        return f"{self.empresa} — {self.data}"



class StripeEvent(models.Model):
    """
    Log de eventos recebidos do webhook da Stripe.
    Garante idempotência (não processa o mesmo evento duas vezes)
    e serve de auditoria/debug.
    """
    stripe_event_id = models.CharField(max_length=120, unique=True)
    tipo            = models.CharField(max_length=80)
    payload         = models.JSONField()
    processado      = models.BooleanField(default=False)
    erro            = models.TextField(blank=True)
    recebido_em     = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        ordering = ['-recebido_em']