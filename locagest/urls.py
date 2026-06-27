from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap




urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),


        # ── Autenticação (namespace: accounts) ─────────────────────
    # Necessário no tenant para login/logout funcionar no subdomínio.
    # O OAuth (Google) é interceptado pelo TenantOAuthMiddleware
    # e redirecionado para o domínio principal antes de ir ao Google.
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('accounts/', include('accounts.urls')),
  
 

    # ── Google OAuth / allauth ─────────────────────────────────
    # Presente aqui para rotas de gerenciamento de conta social
    # (desconectar conta Google, etc.) funcionarem no subdomínio.
    # O fluxo de LOGIN via Google é sempre redirecionado para o
    # domínio principal pelo TenantOAuthMiddleware.
    path('auth/',        include('allauth.urls')),
    path('auth/social/', include('allauth.socialaccount.urls')),
 

    # ── Apps de tenant ─────────────────────────────────────────
    # Estas rotas são isoladas por schema PostgreSQL pelo django-tenants.
    # Cada empresa tem seus próprios dados.
    path('clientes/',     include('clientes.urls')),
    path('produtos/',     include('produtos.urls')),
    path('locacoes/',     include('locacoes.urls')),
    path('agenda/',       include('agenda.urls')),
    path('notificacoes/', include('notificacoes.urls')),
    path('relatorios/',   include('relatorios.urls')),
] 

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)