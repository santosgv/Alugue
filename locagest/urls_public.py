"""
locagest/urls_public.py
========================
URLs do schema PUBLIC do django-tenants.

Regra: fica aqui tudo que precisa ser acessível no domínio raiz
(locagest.com.br ou localhost:8000), ANTES de qualquer resolução
de tenant. Os apps de tenant (clientes, produtos, locações, etc.)
NÃO entram aqui — eles ficam apenas no urls.py principal.

Configuração no settings.py:
    PUBLIC_SCHEMA_URLCONF = 'locagest.urls_public'
    ROOT_URLCONF          = 'locagest.urls'        ← tenant urls (já existente)
"""

from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .sitemap import Sitemap
from core.views import PaginaVendasView,robots
from core.stripe_views import StripeWebhookView 


sitemaps = {
    'sitemap': Sitemap,
}

urlpatterns = [

    # ── Django admin ───────────────────────────────────────────
    path('admin/', admin.site.urls),
    path("sitemap.xml",sitemap,{"sitemaps": sitemaps},name="django.contrib.sitemaps.views.sitemap",),
    path('robots.txt',             robots,                             name='robots_txt'),
    # ── Sitemap público ───────────────────────────────────────

    # ── Autenticação (namespace: accounts) ────────────────────
    # Login, logout, recuperação de senha — sempre no domínio raiz
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('auth/',        include('allauth.urls')),
    path('auth/social/', include('allauth.socialaccount.urls')),
 
    # ── Planos, assinatura e Stripe ────────────────────────────
    # Acessíveis antes do usuário ter um tenant resolvido
    # (ex: página de vendas, checkout, webhook da Stripe)
    path('', include('core.urls')),
    path('clientes/',     include('clientes.urls')),
    path('produtos/',     include('produtos.urls')),
    path('locacoes/',     include('locacoes.urls')),
    path('agenda/',       include('agenda.urls')),
    path('notificacoes/', include('notificacoes.urls')),
    path('relatorios/',   include('relatorios.urls')),
    path('vendas/',                PaginaVendasView.as_view(),          name='pagina_vendas'),

    # ── Painel do dono da plataforma ───────────────────────────
    # /plataforma/ já está dentro de core.urls — incluído acima.

    # ── Webhook Stripe ─────────────────────────────────────────
    # A Stripe faz POST direto aqui, sem tenant.
    # Também já está dentro de core.urls via stripe_views.
    path('webhooks/stripe/', StripeWebhookView.as_view(), name='stripe_webhook'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)