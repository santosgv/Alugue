from django.contrib.auth import login, get_user_model
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View
from django import forms
from django.core.exceptions import ValidationError
from django.conf import settings
import requests as http_requests

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
        senha  = cleaned.get('senha')
        conf   = cleaned.get('senha_confirmacao')
        if senha and conf and senha != conf:
            self.add_error('senha_confirmacao', 'As senhas não conferem.')
        return cleaned


class CadastroView(View):
    template_name = 'registration/cadastro.html'

    def get(self, request):
        # Usuário já logado → vai para o dashboard
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

        form = CadastroForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        dados = form.cleaned_data
        partes = dados['nome'].strip().split(' ', 1)
        first  = partes[0]
        last   = partes[1] if len(partes) > 1 else ''

        # Cria o usuário — o signal criar_empresa_e_trial dispara aqui
        user = User.objects.create_user(
            username=dados['email'].split('@')[0],# + '_' + str(User.objects.count()),
            email=dados['email'],
            password=dados['senha'],
            first_name=first,
            last_name=last,
        )

        # Loga automaticamente após cadastro
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(
            request,
            f'Bem-vindo, {first}! Seu trial de 14 dias está ativo. Explore o sistema!'
        )
        return redirect('dashboard')