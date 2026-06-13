from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.generic import TemplateView, UpdateView, View
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django import forms

from .models import PerfilUsuario


# ─────────────────────────────────────────────────────────────
# GUARD: só admin da empresa pode gerenciar usuários
# ─────────────────────────────────────────────────────────────

class AdminEmpresaMixin:
    """Restringe acesso a usuários com role=admin dentro da empresa."""
    def dispatch(self, request, *args, **kwargs):
        try:
            if request.user.is_superuser or request.user.perfil.is_admin_empresa:
                return super().dispatch(request, *args, **kwargs)
        except Exception:
            pass
        messages.error(request, 'Acesso restrito a administradores da empresa.')
        return redirect('dashboard')


# ─────────────────────────────────────────────────────────────
# FORMS
# ─────────────────────────────────────────────────────────────

class PerfilForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=150, required=False, label='Nome',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    last_name = forms.CharField(
        max_length=150, required=False, label='Sobrenome',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    email = forms.EmailField(
        required=False, label='E-mail',
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
    )

    class Meta:
        model  = PerfilUsuario
        fields = ['role']
        widgets = {'role': forms.Select(attrs={'class': 'form-select'})}

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)
        if instance:
            self.fields['first_name'].initial = instance.user.first_name
            self.fields['last_name'].initial  = instance.user.last_name
            self.fields['email'].initial      = instance.user.email

    def save(self, commit=True):
        perfil = super().save(commit=False)
        perfil.user.first_name = self.cleaned_data['first_name']
        perfil.user.last_name  = self.cleaned_data['last_name']
        perfil.user.email      = self.cleaned_data['email']
        if commit:
            perfil.user.save(update_fields=['first_name', 'last_name', 'email'])
            perfil.save()
        return perfil


class NovoUsuarioEmpresaForm(forms.Form):
    """Form usado pelo admin da empresa para adicionar usuários."""
    nome = forms.CharField(
        max_length=200, label='Nome completo',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    email = forms.EmailField(
        label='E-mail de acesso',
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
    )
    role = forms.ChoiceField(
        choices=PerfilUsuario.ROLE_CHOICES, label='Perfil',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Já existe um usuário com este e-mail.')
        return email


# ─────────────────────────────────────────────────────────────
# PERFIL PRÓPRIO
# ─────────────────────────────────────────────────────────────

class PerfilView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/perfil.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            ctx['perfil'] = self.request.user.perfil
        except Exception:
            ctx['perfil'] = None
        return ctx


# ─────────────────────────────────────────────────────────────
# USUÁRIOS DA EMPRESA (visão do admin da empresa)
# ─────────────────────────────────────────────────────────────


class UsuarioEmpresaListView(LoginRequiredMixin, AdminEmpresaMixin, TemplateView):
    template_name = 'accounts/usuarios_empresa.html'
 
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        empresa = getattr(self.request, 'empresa', None)
 
        usuarios_qs = (
            PerfilUsuario.objects
            .filter(empresa=empresa)
            .select_related('user')
            .order_by('user__first_name', 'user__username')
        ) if empresa else PerfilUsuario.objects.none()
 
        ctx['usuarios'] = usuarios_qs
        ctx['empresa']  = empresa
        ctx['form_novo'] = NovoUsuarioEmpresaForm()
 
        # Credenciais geradas no POST anterior — exibe uma única vez
        ctx['credenciais_novo_usuario'] = self.request.session.pop(
            'credenciais_novo_usuario', None
        )
 
        # Uso do plano — para mostrar barra de limite de usuários
        plano = getattr(self.request, 'plano_ativo', None)
        if plano:
            total_atual = usuarios_qs.exclude(user__is_superuser=True).count()
            ctx['limite_usuarios'] = plano.limite_usuarios
            ctx['total_usuarios']  = total_atual
            ctx['usuarios_ilimitado'] = plano.usuarios_ilimitados
            ctx['usuarios_pct'] = (
                0 if plano.usuarios_ilimitados
                else min(100, round(total_atual / plano.limite_usuarios * 100))
            )
            ctx['usuarios_restantes'] = (
                None if plano.usuarios_ilimitados
                else max(0, plano.limite_usuarios - total_atual)
            )
            ctx['limite_atingido'] = (
                False if plano.usuarios_ilimitados
                else total_atual >= plano.limite_usuarios
            )
        return ctx
 
    def post(self, request, *args, **kwargs):
        empresa = getattr(request, 'empresa', None)
        if not empresa:
            messages.error(request, 'Empresa não encontrada.')
            return redirect('usuarios_empresa')
 
        form = NovoUsuarioEmpresaForm(request.POST)
        if not form.is_valid():
            for field, erros in form.errors.items():
                for erro in erros:
                    messages.error(request, erro)
            return redirect('usuarios_empresa')
 
        from accounts.services import UsuarioEmpresaService
        user, senha = UsuarioEmpresaService.criar_admin_empresa(
            empresa  = empresa,
            email    = form.cleaned_data['email'],
            nome     = form.cleaned_data['nome'],
            role     = form.cleaned_data['role'],
        )
        # Guarda credenciais na sessão para exibir uma vez
        request.session['credenciais_novo_usuario'] = {
            'username': user.username,
            'senha':    senha,
            'email':    user.email,
            'nome':     user.get_full_name() or user.username,
        }
        messages.success(request, f'Usuário "{user.username}" criado com sucesso.')
        return redirect('accounts:usuarios_empresa')
 

class ToggleUsuarioEmpresaView(LoginRequiredMixin, AdminEmpresaMixin, View):
    """Admin da empresa ativa/desativa usuários da sua empresa."""
    def post(self, request, pk):
        empresa = getattr(request, 'empresa', None)
        perfil  = get_object_or_404(PerfilUsuario, pk=pk, empresa=empresa)

        # Não pode desativar a si mesmo
        if perfil.user == request.user:
            messages.error(request, 'Você não pode desativar seu próprio usuário.')
            return redirect('accounts:usuarios_empresa')

        perfil.ativo          = not perfil.ativo
        perfil.user.is_active = perfil.ativo
        perfil.save(update_fields=['ativo'])
        perfil.user.save(update_fields=['is_active'])

        acao = 'ativado' if perfil.ativo else 'desativado'
        messages.success(request, f'Usuário "{perfil.user.username}" {acao}.')
        return redirect('accounts:usuarios_empresa')


class EditarPerfilUsuarioView(LoginRequiredMixin, AdminEmpresaMixin, View):
    """Admin da empresa edita role/dados de outro usuário da empresa."""
    template_name = 'accounts/editar_usuario.html'

    def get(self, request, pk):
        from django.shortcuts import render
        empresa = getattr(request, 'empresa', None)
        perfil  = get_object_or_404(PerfilUsuario, pk=pk, empresa=empresa)
        form    = PerfilForm(instance=perfil)
        return render(request, self.template_name, {'form': form, 'perfil': perfil})

    def post(self, request, pk):
        from django.shortcuts import render
        empresa = getattr(request, 'empresa', None)
        perfil  = get_object_or_404(PerfilUsuario, pk=pk, empresa=empresa)
        form    = PerfilForm(request.POST, instance=perfil)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuário atualizado com sucesso.')
            return redirect('accounts:usuarios_empresa')
        return render(request, self.template_name, {'form': form, 'perfil': perfil})
