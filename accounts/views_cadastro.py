"""
accounts/views_cadastro.py
===========================
View de cadastro com reCAPTCHA v3 + redirecionamento para tenant.

Configuração no settings.py / .env:
    RECAPTCHA_SECRET_KEY = '6LeSOFYtA...'   # chave secreta (server-side)
    RECAPTCHA_SITE_KEY   = '6LeSOFYtA...'   # chave pública (já está no template)
    RECAPTCHA_SCORE_MIN  = 0.5              # score mínimo (0.0 a 1.0)
"""
import requests as http_requests

from django.contrib.auth import login, get_user_model
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View
from django import forms
from django.core.exceptions import ValidationError
from django.conf import settings

User = get_user_model()

# ─────────────────────────────────────────────────────────────
# reCAPTCHA v3
# ─────────────────────────────────────────────────────────────

def _verificar_recaptcha(token: str, ip: str = '') -> tuple[bool, float]:
    """
    Verifica o token reCAPTCHA v3 com a API do Google.
    Retorna (válido: bool, score: float).

    Score:
      1.0 → claramente humano
      0.0 → claramente bot
      0.5 → limiar padrão recomendado pelo Google
    """
    secret = getattr(settings, 'RECAPTCHA_SECRET_KEY', '')
    if not secret:
        # Se não configurou a chave, deixa passar (modo dev)
        return True, 1.0

    if not token:
        return False, 0.0

    try:
        r = http_requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={'secret': secret, 'response': token, 'remoteip': ip},
            timeout=5,
        )
        data    = r.json()
        sucesso = data.get('success', False)
        score   = float(data.get('score', 0.0))
        return sucesso, score
    except Exception:
        # Falha na verificação → deixa passar para não bloquear usuários
        # legítimos por problemas de rede. Ajuste se preferir bloquear.
        return True, 1.0

# ─────────────────────────────────────────────────────────────
# reCAPTCHA v3
# ─────────────────────────────────────────────────────────────

def _verificar_recaptcha(token: str, ip: str = '') -> tuple[bool, float]:
    """
    Verifica o token reCAPTCHA v3 com a API do Google.
    Retorna (válido: bool, score: float).

    Score:
      1.0 → claramente humano
      0.0 → claramente bot
      0.5 → limiar padrão recomendado pelo Google
    """
    secret = getattr(settings, 'RECAPTCHA_SECRET_KEY', '')
    if not secret:
        # Se não configurou a chave, deixa passar (modo dev)
        return True, 1.0

    if not token:
        return False, 0.0

    try:
        r = http_requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={'secret': secret, 'response': token, 'remoteip': ip},
            timeout=5,
        )
        data    = r.json()
        sucesso = data.get('success', False)
        score   = float(data.get('score', 0.0))
        return sucesso, score
    except Exception:
        # Falha na verificação → deixa passar para não bloquear usuários
        # legítimos por problemas de rede. Ajuste se preferir bloquear.
        return True, 1.0


# ─────────────────────────────────────────────────────────────
# FORM
# ─────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────
# HELPER — URL do tenant
# ─────────────────────────────────────────────────────────────

def _url_tenant(schema_name: str, path: str = '/') -> str:
    """
    Dev:  'joao_silva' → http://joao_silva.localhost:8000/
    Prod: 'joao_silva' → https://joao_silva.locagest.com.br/
    """
    base  = getattr(settings, 'TENANT_BASE_DOMAIN', 'localhost')
    debug = getattr(settings, 'DEBUG', False)
    port  = getattr(settings, 'TENANT_DEV_PORT', '8000')
    proto = 'http' if debug else 'https'

    if debug:
        return f'{proto}://{schema_name}.{base}:{port}{path}'
    return f'{proto}://{schema_name}.{base}{path}'


# ─────────────────────────────────────────────────────────────
# VIEW
# ─────────────────────────────────────────────────────────────

class CadastroView(View):
    template_name = 'registration/cadastro.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return render(request, self.template_name, {'form': CadastroForm()})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        
        # ── 1. Valida reCAPTCHA v3 antes de qualquer coisa ────
        token     = request.POST.get('recaptchaToken', '')
        ip        = request.META.get('REMOTE_ADDR', '')
        ok, score = _verificar_recaptcha(token, ip)
        score_min = getattr(settings, 'RECAPTCHA_SCORE_MIN', 0.5)

        if not ok or score < score_min:
            messages.error(
                request,
                'Verificação de segurança falhou. '
                'Por favor, tente novamente.'
            )
            return render(request, self.template_name, {'form': CadastroForm()})

        # ── 1. Valida reCAPTCHA v3 antes de qualquer coisa ────
        token     = request.POST.get('recaptchaToken', '')
        ip        = request.META.get('REMOTE_ADDR', '')
        ok, score = _verificar_recaptcha(token, ip)
        score_min = getattr(settings, 'RECAPTCHA_SCORE_MIN', 0.5)

        if not ok or score < score_min:
            messages.error(
                request,
                'Verificação de segurança falhou. '
                'Por favor, tente novamente.'
            )
            return render(request, self.template_name, {'form': CadastroForm()})

        # ── 2. Valida o formulário ─────────────────────────────
        form = CadastroForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        dados  = form.cleaned_data
        partes = dados['nome'].strip().split(' ', 1)
        first  = partes[0]
        last   = partes[1] if len(partes) > 1 else ''

        # ── 3. Cria o usuário ──────────────────────────────────
        # O signal provisionar_tenant_free() dispara aqui e cria:
        #   TenantCompany → Domain → PerfilUsuario → Assinatura trial
        user = User.objects.create_user(
            username=dados['email'].split('@')[0],
            email=dados['email'],
            password=dados['senha'],
            first_name=first,
            last_name=last,
        )

        # ── 4. Loga imediatamente ──────────────────────────────
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        # ── 5. Redireciona para o subdomínio do tenant ─────────
        try:
            from accounts.models import PerfilUsuario
            perfil  = PerfilUsuario.objects.select_related('empresa').get(user=user)
            empresa = perfil.empresa

            if empresa and empresa.schema_name:
                messages.success(
                    request,
                    f'Bem-vindo, {first}! Seu trial de 14 dias está ativo.'
                )
                return redirect(_url_tenant(empresa.schema_name))

        except Exception:
            messages.warning(
                request,
                'Conta criada! Estamos configurando seu espaço — '
                'aguarde alguns instantes e acesse novamente.'
            )

        # Fallback: domínio principal
        return redirect('dashboard')