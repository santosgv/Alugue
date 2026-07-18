from django.urls import path
from . import views, admin_views
from .stripe_views import (
        IniciarCheckoutView, CheckoutSucessoView,
        BillingPortalView, StripeWebhookView,
    )
from django_ratelimit.decorators import ratelimit

urlpatterns = [
    # ── App do usuário final ───────────────────────────────────
    path('',ratelimit(key='ip', method='GET', rate='10/m')                      (views.DashboardView.as_view()),            name='dashboard'),
    path('vendas/',ratelimit(key='ip', method='GET', rate='10/m')                (views.PaginaVendasView.as_view()),          name='pagina_vendas'),
    path('planos/',ratelimit(key='ip', method='GET', rate='10/m')                (views.PlanosView.as_view()),               name='planos'),
    path('assinatura/',ratelimit(key='ip', method='GET', rate='10/m')            (views.AssinaturaPainelView.as_view()),     name='assinatura_painel'),
    path('assinatura/mudar/',ratelimit(key='ip', method='GET', rate='10/m')      (views.MudarPlanoView.as_view()),           name='mudar_plano'),
    path('assinatura/cancelar/',ratelimit(key='ip', method='GET', rate='10/m')   (views.CancelarAssinaturaView.as_view()),   name='cancelar_assinatura'),
    path('configuracoes/',ratelimit(key='ip', method='GET', rate='10/m')         (views.EmpresaConfigView.as_view()),        name='empresa_config'),
    path('robots.txt',ratelimit(key='ip', method='GET', rate='10/m')             (views.robots),                             name='robots_txt'),

    # ── Painel do dono da plataforma (superuser) ───────────────
    path('plataforma/',
         admin_views.PlataformaDashboardView.as_view(),  name='admin_plataforma'),

    path('plataforma/empresas/',
         admin_views.EmpresaListView.as_view(),          name='admin_empresas'),

    path('plataforma/empresas/nova/',
         admin_views.EmpresaCreateView.as_view(),        name='admin_empresa_criar'),

    path('plataforma/empresas/<int:pk>/',
         admin_views.EmpresaDetailView.as_view(),        name='admin_empresa_detalhe'),

    path('plataforma/empresas/<int:pk>/editar/',
         admin_views.EmpresaUpdateView.as_view(),        name='admin_empresa_editar'),

    path('plataforma/empresas/<int:pk>/assinatura/',
         admin_views.AtribuirAssinaturaView.as_view(),   name='admin_atribuir_assinatura'),

    path('plataforma/assinaturas/<int:pk>/renovar/',
         admin_views.RenovarAssinaturaView.as_view(),    name='admin_renovar_assinatura'),


    path('plataforma/empresas/<int:pk>/usuarios/adicionar/',
         admin_views.AdicionarUsuarioEmpresaView.as_view(), name='admin_adicionar_usuario'),

    path('plataforma/usuarios/<int:pk>/toggle/',
         admin_views.ToggleUsuarioView.as_view(),        name='admin_toggle_usuario'),


     path('assinatura/checkout/<int:plano_id>/<str:ciclo>/',
             IniciarCheckoutView.as_view(), name='stripe_checkout'),
     path('assinatura/sucesso/',
             CheckoutSucessoView.as_view(), name='stripe_sucesso'),
     path('assinatura/portal/',
             BillingPortalView.as_view(), name='stripe_portal'),
     path('webhooks/stripe/',
             StripeWebhookView.as_view(), name='stripe_webhook'),
]
