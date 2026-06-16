from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    # ── Autenticação ───────────────────────────────────────────
    path('login/',  auth_views.LoginView.as_view(template_name='registration/login.html'),  name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # ── Alterar senha (usuário logado) ─────────────────────────
    # success_url com reverse_lazy + namespace evita NoReverseMatch
    path(
        'senha/alterar/',
        auth_views.PasswordChangeView.as_view(
            template_name='registration/password_change.html',
            success_url=reverse_lazy('accounts:password_change_done'),
        ),
        name='password_change',
    ),
    path(
        'senha/alterada/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='registration/password_change_done.html',
        ),
        name='password_change_done',
    ),
 
    # ── Recuperar senha (usuário deslogado) ────────────────────
    # PasswordResetView redireciona para 'done' após enviar e-mail.
    # PasswordResetConfirmView redireciona para 'complete' após redefinir.
    # Ambas precisam de success_url com namespace — sem isso o Django
    # chama reverse('password_reset_done') sem prefixo e quebra.
    path(
        'senha/recuperar/',
        auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset.html',
            email_template_name='registration/password_reset_email.html',
            subject_template_name='registration/password_reset_subject.txt',
            success_url=reverse_lazy('accounts:password_reset_done'),
        ),
        name='password_reset',
    ),
    path(
        'senha/recuperar/enviado/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'senha/redefinir/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html',
            success_url=reverse_lazy('accounts:password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'senha/redefinida/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
    # ── Perfil próprio ─────────────────────────────────────────
    path('perfil/', views.PerfilView.as_view(), name='perfil'),

    # ── Usuários da empresa (admin da empresa) ─────────────────
    path('usuarios/', views.UsuarioEmpresaListView.as_view(), name='usuarios_empresa'),
    path('usuarios/<int:pk>/toggle/', views.ToggleUsuarioEmpresaView.as_view(), name='toggle_usuario'),
    path('usuarios/<int:pk>/editar/', views.EditarPerfilUsuarioView.as_view(), name='editar_usuario'),
]
