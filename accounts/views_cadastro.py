from django.contrib.auth import login, get_user_model
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View
from django import forms
from django.core.exceptions import ValidationError

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

        form = CadastroForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        dados = form.cleaned_data
        partes = dados['nome'].strip().split(' ', 1)
        first  = partes[0]
        last   = partes[1] if len(partes) > 1 else ''

        # Cria o usuário — o signal criar_empresa_e_trial dispara aqui
        user = User.objects.create_user(
            username=dados['email'].split('@')[0] + '_' + str(User.objects.count()),
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