from django.contrib import admin
from django.utils.html import format_html
from .models import SubscriptionPlan, TenantCompany, Assinatura, UsoAssinatura,StripeEvent




@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display  = ('nome', 'slug', 'preco_mensal', 'preco_anual',
                     'label_clientes', 'label_produtos', 'destaque', 'ativo', 'ordem')
    list_editable = ('ativo', 'destaque', 'ordem')
    list_filter   = ('ativo', 'destaque')
    #prepopulated_fields = {'slug': ('nome',)}
    fieldsets = (
        ('Identificação', {'fields': ('nome', 'slug', 'descricao', 'ordem', 'destaque', 'ativo')}),
        ('Preços', {'fields': ('preco_mensal', 'preco_anual')}),
        ('Limites', {'fields': ('limite_clientes', 'limite_produtos','limite_categorias', 'limite_locacoes')}),
        ('Recursos (JSON)', {
            'fields': ('recursos',),
            'description': (
                'Exemplo: {"whatsapp": true, "multiusuario": false, '
                '"relatorios": true, "api_acesso": false, "suporte_prioritario": true}'
            )
        }),
    )

    def label_clientes(self, obj):
        return obj.label_clientes
    label_clientes.short_description = 'Clientes'

    def label_produtos(self, obj):
        return obj.label_produtos
    label_produtos.short_description = 'Produtos'


class AssinaturaInline(admin.TabularInline):
    model  = Assinatura
    extra  = 0
    fields = ('plano', 'status', 'ciclo', 'data_inicio', 'data_fim', 'valor_cobrado')
    readonly_fields = ('criado_em',)


@admin.register(TenantCompany)
class TenantCompanyAdmin(admin.ModelAdmin):
    list_display  = ('nome', 'cnpj', 'plano', 'ativo', 'data_cadastro',)
    list_filter   = ('ativo', 'plano')
    search_fields = ('nome', 'cnpj')
    inlines       = [AssinaturaInline]

    def plano_badge(self, obj):
        sub = obj.assinaturas.filter(status__in=['ativa', 'trial']).first()
        if sub:
            cores = {'ativa': 'success', 'trial': 'warning'}
            cor = cores.get(sub.status, 'secondary')
            return format_html(
                '<span class="badge bg-{}">{} — {}</span>',
                cor, sub.plano.nome, sub.get_status_display()
            )
        return format_html('<span class="badge bg-secondary">Sem assinatura</span>')
    plano_badge.short_description = 'Assinatura Ativa'


@admin.register(Assinatura)
class AssinaturaAdmin(admin.ModelAdmin):
    list_display  = ('empresa', 'plano', 'status', 'ciclo',
                     'data_inicio', 'data_fim', 'valor_cobrado', 'dias_restantes_display')
    list_filter   = ('status', 'ciclo', 'plano')
    search_fields = ('empresa__nome',)
    readonly_fields = ('criado_em', 'atualizado_em', 'cancelada_em')
    date_hierarchy = 'data_inicio'

    def dias_restantes_display(self, obj):
        dias = obj.dias_restantes
        if dias is None:
            return '—'
        if dias <= 3:
            return format_html('<span style="color:red;font-weight:bold;">{} dias</span>', dias)
        if dias <= 7:
            return format_html('<span style="color:orange;">{} dias</span>', dias)
        return f'{dias} dias'
    dias_restantes_display.short_description = 'Dias Restantes'


@admin.register(UsoAssinatura)
class UsoAssinaturaAdmin(admin.ModelAdmin):
    list_display  = ('empresa', 'data', 'total_clientes', 'total_produtos', 'total_locacoes')
    list_filter   = ('empresa',)
    date_hierarchy = 'data'
    readonly_fields = ('criado_em',)

admin.site.register(StripeEvent)
