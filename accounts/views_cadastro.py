"""
accounts/views_cadastro.py
===========================
View de cadastro público em /accounts/criar/

Após criar o usuário:
  1. Signal provisionar_tenant_free() cria TenantCompany + Domain + Assinatura
  2. View lê o schema_name da empresa recém-criada
  3. Redireciona para o subdomínio do tenant: schema.localhost:8000/

Adicione em accounts/urls.py:
    from .views_cadastro import CadastroView
    path('criar/', CadastroView.as_view(), name='cadastro'),
"""
from django.contrib.auth import login, get_user_model
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View
from django import forms
from django.core.exceptions import ValidationError
from django.conf import settings

User = get_user_model()


class CadastroForm(forms.Form):
    nome = forms.CharField(
        max_length=150,
        label='Seu nome completo',
        widget=forms.TextInput(attrs={
            'class':       'form-control',
            'placeholder': 'João Silva',
            'autofocus':   True,
        }),
    )
    email = forms.EmailField(
        label='E-mail',
        widget=forms.EmailInput(attrs={
            'class':       'form-control',
            'placeholder': 'voce@email.com',
        }),
    )
    senha = forms.CharField(
        label='Senha',
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class':       'form-control',
            'placeholder': 'Mínimo 8 caracteres',
        }),
    )
    senha_confirmacao = forms.CharField(
        label='Confirme a senha',
        widget=forms.PasswordInput(attrs={
            'class':       'form-control',
            'placeholder': 'Repita a senha',
        }),
    )

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if User.objects.filter(email=email).exists():
            raise ValidationError('Já existe uma conta com este e-mail.')
        return email

    def clean(self):
        cleaned = super().clean()
        senha = cleaned.get('senha')
        conf  = cleaned.get('senha_confirmacao')
        if senha and conf and senha != conf:
            self.add_error('senha_confirmacao', 'As senhas não conferem.')
        return cleaned


def _url_tenant(schema_name: str, path: str = '/') -> str:
    """
    Monta a URL completa do subdomínio do tenant.

    Dev:  schema='joao_silva' → http://joao_silva.localhost:8000/
    Prod: schema='joao_silva' → https://joao_silva.locagest.com.br/
    """
    base  = getattr(settings, 'TENANT_BASE_DOMAIN', 'localhost')
    debug = getattr(settings, 'DEBUG', False)
    port  = getattr(settings, 'TENANT_DEV_PORT', '8000')
    proto = 'http' if debug else 'https'

    if debug:
        return f'{proto}://{schema_name}.{base}:{port}{path}'
    return f'{proto}://{schema_name}.{base}{path}'


class CadastroView(View):
    template_name = 'registration/cadastro.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return render(request, self.template_name, {'form': CadastroForm()})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')

        form = CadastroForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        dados  = form.cleaned_data
        partes = dados['nome'].strip().split(' ', 1)
        first  = partes[0]
        last   = partes[1] if len(partes) > 1 else ''

        # Cria o usuário
        # O signal provisionar_tenant_free() dispara aqui e cria:
        #   TenantCompany → Domain → PerfilUsuario → Assinatura trial
        user = User.objects.create_user(
            username=dados['email'].split('@')[0], #+ '_' + str(User.objects.count()),
            email=dados['email'],
            password=dados['senha'],
            first_name=first,
            last_name=last,
        )

        # Loga imediatamente
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        # ── Redireciona para o subdomínio do tenant ────────────
        # O signal já criou a empresa — buscamos pelo PerfilUsuario
        try:
            from accounts.models import PerfilUsuario
            perfil  = PerfilUsuario.objects.select_related('empresa').get(user=user)
            empresa = perfil.empresa

            if empresa and empresa.schema_name:
                url_tenant = _url_tenant(empresa.schema_name)
                messages.success(
                    request,
                    f'Bem-vindo, {first}! Seu trial de 14 dias está ativo.'
                )
                return redirect(url_tenant)

        except Exception:
            # Se por algum motivo o perfil/empresa não foi criado,
            # fica no domínio principal com mensagem de erro amigável
            messages.warning(
                request,
                f'Conta criada! Estamos configurando seu espaço — '
                f'aguarde alguns instantes e acesse novamente.'
            )

        # Fallback: domínio principal
        return redirect('dashboard')