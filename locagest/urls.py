from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from .sitemap import Sitemap


sitemaps = {
    'sitemap': Sitemap,
}
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
        path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path('accounts/', include('accounts.urls')),
    path('auth/', include('allauth.urls')),
    path('auth/social/', include('allauth.socialaccount.urls')),
    path('clientes/', include('clientes.urls')),
    path('produtos/', include('produtos.urls')),
    path('locacoes/', include('locacoes.urls')),
    path('agenda/', include('agenda.urls')),
    path('notificacoes/', include('notificacoes.urls')),
    path('relatorios/',include('relatorios.urls')),
    path('blog/', include('blog.urls'))
] 

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)