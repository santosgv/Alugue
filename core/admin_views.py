"""
Views do painel de administração da plataforma (superadmin).
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DetailView, View
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.db.models import Count, Q
from django.utils import timezone
from django import forms
import datetime

from .models import Domain, SubscriptionPlan, TenantCompany, Assinatura
from .services import AssinaturaService, LimiteService
from accounts.models import PerfilUsuario
from accounts.services import UsuarioEmpresaService


# ─────────────────────────────────────────────────────────────
# GUARD
# ─────────────────────────────────────────────────────────────

class SuperAdminMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser


# ─────────────────────────────────────────────────────────────
# FORMS
# ─────────────────────────────────────────────────────────────

class EmpresaAdminForm(forms.ModelForm):
    class Meta:
        model  = TenantCompany
        fields = ['nome', 'cnpj', 'email', 'telefone', 'plano', 'ativo']
        widgets = {
            'nome':     forms.TextInput(attrs={'class': 'form-control'}),
            'cnpj':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00.000.000/0001-00'}),
            'email':    forms.EmailInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control'}),
            'plano':    forms.Select(attrs={'class': 'form-select'}),
            'ativo':    forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CriarAssinaturaForm(forms.Form):
    plano = forms.ModelChoiceField(
        queryset=SubscriptionPlan.objects.filter(ativo=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Plano',
    )
    ciclo = forms.ChoiceField(
        choices=Assinatura.CICLO_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Ciclo de cobrança',
    )
    trial = forms.BooleanField(
        required=False,
        label='Iniciar como trial (14 dias gratuitos)',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )


class CriarUsuarioEmpresaForm(forms.Form):
    """Formulário para criar o usuário administrador da empresa."""
    criar_usuario = forms.BooleanField(
        required=False,
        initial=True,
        label='Criar usuário administrador para esta empresa',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_criar_usuario'}),
    )
    nome_contato = forms.CharField(
        max_length=200,
        required=False,
        label='Nome do responsável',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'João Silva'}),
    )
    email_usuario = forms.EmailField(
        required=False,
        label='E-mail de acesso',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'joao@empresa.com'}),
        help_text='Será usado como login. Deixe em branco para usar o e-mail da empresa.',
    )
    username = forms.CharField(
        max_length=50,
        required=False,
        label='Username (login)',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Gerado automaticamente'}),
        help_text='Deixe em branco para gerar automaticamente.',
    )
    senha = forms.CharField(
        max_length=50,
        required=False,
        label='Senha',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Gerada automaticamente'}),
        help_text='Deixe em branco para gerar uma senha segura aleatória.',
    )
    role = forms.ChoiceField(
        choices=PerfilUsuario.ROLE_CHOICES,
        initial=PerfilUsuario.ROLE_ADMIN,
        label='Perfil de acesso',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('criar_usuario'):
            # Username não pode colidir com existente
            username = cleaned.get('username')
            if username and User.objects.filter(username=username).exists():
                self.add_error('username', 'Este username já está em uso.')
        return cleaned


class UsuarioEmpresaAdicionarForm(forms.Form):
    """Adiciona mais usuários a uma empresa já existente."""
    nome_contato  = forms.CharField(
        max_length=200, label='Nome completo',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    email_usuario = forms.EmailField(
        label='E-mail de acesso',
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
    )
    username = forms.CharField(
        max_length=50, required=False, label='Username',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Gerado automaticamente'}),
    )
    role = forms.ChoiceField(
        choices=PerfilUsuario.ROLE_CHOICES,
        label='Perfil de acesso',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def clean_email_usuario(self):
        email = self.cleaned_data.get('email_usuario')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError('Já existe um usuário com este e-mail.')
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username and User.objects.filter(username=username).exists():
            raise forms.ValidationError('Username já em uso.')
        return username


# ─────────────────────────────────────────────────────────────
# DASHBOARD DA PLATAFORMA
# ─────────────────────────────────────────────────────────────

class PlataformaDashboardView(SuperAdminMixin, ListView):
    model = TenantCompany
    template_name = 'core/admin/dashboard.html'
    context_object_name = 'empresas'

    def get_queryset(self):
        return (
            TenantCompany.objects
            .select_related('plano')
            .prefetch_related('assinaturas')
            .annotate(total_usuarios=Count('usuarios', distinct=True))
            .order_by('-data_cadastro')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        hoje    = timezone.localdate()
        em7dias = hoje + datetime.timedelta(days=7)

        ativas = Assinatura.objects.filter(status=Assinatura.STATUS_ATIVA)
        trials = Assinatura.objects.filter(status=Assinatura.STATUS_TRIAL)

        ctx['total_empresas']   = TenantCompany.objects.filter(ativo=True).count()
        ctx['total_ativas']     = ativas.count()
        ctx['total_trials']     = trials.count()
        ctx['total_canceladas'] = Assinatura.objects.filter(status=Assinatura.STATUS_CANCELADA).count()
        ctx['total_usuarios']   = PerfilUsuario.objects.filter(ativo=True).exclude(
            user__is_superuser=True
        ).count()

        ctx['mrr'] = round(sum(
            float(a.valor_cobrado) / (12 if a.ciclo == 'anual' else 1)
            for a in ativas.select_related('plano')
        ), 2)

        ctx['trials_expirando'] = trials.filter(
            data_fim__lte=em7dias, data_fim__gte=hoje
        ).select_related('empresa', 'plano').order_by('data_fim')

        ctx['expiradas'] = Assinatura.objects.filter(
            status=Assinatura.STATUS_EXPIRADA
        ).select_related('empresa', 'plano').order_by('-data_fim')[:10]

        ctx['por_plano'] = (
            SubscriptionPlan.objects.filter(ativo=True)
            .annotate(qtd_ativas=Count(
                'assinaturas',
                filter=Q(assinaturas__status__in=['ativa', 'trial'])
            ))
            .order_by('ordem')
        )
        return ctx


# ─────────────────────────────────────────────────────────────
# EMPRESA — LISTA
# ─────────────────────────────────────────────────────────────

class EmpresaListView(SuperAdminMixin, ListView):
    model = TenantCompany
    template_name = 'core/admin/empresa_lista.html'
    context_object_name = 'empresas'
    paginate_by = 20

    def get_queryset(self):
        qs = (
            TenantCompany.objects
            .select_related('plano')
            .prefetch_related('assinaturas__plano', 'usuarios__user')
            .annotate(total_usuarios=Count('usuarios', distinct=True))
            .order_by('-data_cadastro')
        )
        q      = self.request.GET.get('q')
        status = self.request.GET.get('status')
        if q:
            qs = qs.filter(Q(nome__icontains=q) | Q(cnpj__icontains=q) | Q(email__icontains=q))
        if status == 'ativa':
            qs = qs.filter(assinaturas__status='ativa').distinct()
        elif status == 'trial':
            qs = qs.filter(assinaturas__status='trial').distinct()
        elif status == 'sem_assinatura':
            qs = qs.exclude(assinaturas__status__in=['ativa', 'trial'])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q']      = self.request.GET.get('q', '')
        ctx['status'] = self.request.GET.get('status', '')
        return ctx


# ─────────────────────────────────────────────────────────────
# EMPRESA — CRIAR (com usuário + assinatura)
# ─────────────────────────────────────────────────────────────

class EmpresaCreateView(SuperAdminMixin, CreateView):
    model      = TenantCompany
    form_class = EmpresaAdminForm
    template_name = 'core/admin/empresa_form.html'
    success_url   = reverse_lazy('admin_empresas')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo']          = 'Nova Empresa'
        ctx['form_assinatura'] = CriarAssinaturaForm(self.request.POST or None)
        ctx['form_usuario']    = CriarUsuarioEmpresaForm(self.request.POST or None)
        return ctx

    def form_valid(self, form):
        empresa = form.save()
        # Cria o domínio
        subdomain = form.cleaned_data['subdomain']
        domain = Domain.objects.create(
                        tenant=empresa,
                        domain=f'{subdomain}.seusite.com',
                        is_primary=True
                    )
        msgs    = [f'Empresa "{empresa.nome}" criada com sucesso.']


        # ── 1. Assinatura ──────────────────────────────────────
        form_sub = CriarAssinaturaForm(self.request.POST)
        if form_sub.is_valid():
            plano    = form_sub.cleaned_data['plano']
            ciclo    = form_sub.cleaned_data['ciclo']
            is_trial = form_sub.cleaned_data.get('trial', False)

            if is_trial:
                AssinaturaService.criar_trial(empresa, plano, usuario=self.request.user)
                msgs.append(f'Trial de 14 dias ativado no plano {plano.nome}.')
            else:
                sub = Assinatura(empresa=empresa, plano=plano, data_inicio=timezone.localdate())
                AssinaturaService.ativar(sub, ciclo, usuario=self.request.user)
                msgs.append(f'Assinatura {plano.nome} ({ciclo}) ativada.')

        # ── 2. Usuário administrador ───────────────────────────
        form_usr = CriarUsuarioEmpresaForm(self.request.POST)
        if form_usr.is_valid() and form_usr.cleaned_data.get('criar_usuario'):
            user, senha = UsuarioEmpresaService.criar_admin_empresa(
                empresa      = empresa,
                email        = form_usr.cleaned_data.get('email_usuario') or '',
                nome         = form_usr.cleaned_data.get('nome_contato') or '',
                username     = form_usr.cleaned_data.get('username') or '',
                senha        = form_usr.cleaned_data.get('senha') or '',
                role         = form_usr.cleaned_data.get('role', PerfilUsuario.ROLE_ADMIN),
            )
            msgs.append(
                f'Usuário criado: <strong>{user.username}</strong> / '
                f'Senha: <code>{senha}</code> — '
                f'<em>Anote agora, não será exibida novamente.</em>'
            )
            # Guarda na sessão para exibir no redirect
            self.request.session['nova_empresa_credenciais'] = {
                'empresa': empresa.nome,
                'schema_name': empresa.nome,
                'username': user.username,
                'senha': senha,
                'email': user.email,
            }

        messages.success(self.request, ' '.join(msgs))
        return redirect('admin_empresa_detalhe', pk=empresa.pk)


# ─────────────────────────────────────────────────────────────
# EMPRESA — DETALHE
# ─────────────────────────────────────────────────────────────

class EmpresaDetailView(SuperAdminMixin, DetailView):
    model = TenantCompany
    template_name = 'core/admin/empresa_detalhe.html'
    context_object_name = 'empresa'

    def get_queryset(self):
        return super().get_queryset().select_related('plano').prefetch_related(
            'assinaturas__plano',
            'usuarios__user',
            'usos',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        empresa = self.object

        ctx['assinatura_ativa']       = AssinaturaService.assinatura_ativa(empresa)
        ctx['historico_assinaturas']  = empresa.assinaturas.select_related('plano').order_by('-criado_em')
        ctx['planos']                 = SubscriptionPlan.objects.filter(ativo=True).order_by('ordem')
        ctx['form_assinatura']        = CriarAssinaturaForm()
        ctx['form_add_usuario']       = UsuarioEmpresaAdicionarForm()
        ctx['usuarios']               = empresa.usuarios.select_related('user').order_by('user__username')
        ctx['historico_uso']          = empresa.usos.order_by('-data')[:30]

        # Credenciais geradas na criação (exibe uma única vez)
        ctx['credenciais_novas'] = self.request.session.pop('nova_empresa_credenciais', None)

        plano = AssinaturaService.plano_ativo_da_empresa(empresa)
        if plano:
            from clientes.models import Cliente
            from produtos.models import Produto,CategoriaProduto
            from locacoes.models import Locacao
            ctx['uso_plano'] = LimiteService.uso_atual(
                plano,
                total_clientes=Cliente.objects.filter(ativo=True).count(),
                total_produtos=Produto.objects.filter(status='ativo').count(),
                total_categorias= CategoriaProduto.objects.count(),
                total_usuarios= PerfilUsuario.objects.filter(empresa=empresa,ativo=True).count(),
                total_locacoes=Locacao.objects.filter(status__in=['ativa', 'pendente']).count(),
            )
        return ctx


# ─────────────────────────────────────────────────────────────
# EMPRESA — EDITAR
# ─────────────────────────────────────────────────────────────

class EmpresaUpdateView(SuperAdminMixin, UpdateView):
    model      = TenantCompany
    form_class = EmpresaAdminForm
    template_name = 'core/admin/empresa_form.html'
    success_url   = reverse_lazy('admin_empresas')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar — {self.object.nome}'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Empresa atualizada com sucesso!')
        return super().form_valid(form)


# ─────────────────────────────────────────────────────────────
# ASSINATURA — ATRIBUIR / MUDAR
# ─────────────────────────────────────────────────────────────

class AtribuirAssinaturaView(SuperAdminMixin, View):
    def post(self, request, pk):
        empresa = get_object_or_404(TenantCompany, pk=pk)
        form    = CriarAssinaturaForm(request.POST)

        if not form.is_valid():
            messages.error(request, 'Dados inválidos.')
            return redirect('admin_empresa_detalhe', pk=pk)

        plano    = form.cleaned_data['plano']
        ciclo    = form.cleaned_data['ciclo']
        is_trial = form.cleaned_data.get('trial', False)

        if is_trial:
            AssinaturaService.criar_trial(empresa, plano, usuario=request.user)
            messages.success(request, f'Trial de 14 dias criado para "{empresa.nome}" no plano {plano.nome}.')
        else:
            AssinaturaService.mudar_plano(empresa, plano, ciclo, usuario=request.user)
            messages.success(request, f'Assinatura de "{empresa.nome}" atualizada para {plano.nome} ({ciclo}).')

        return redirect('admin_empresa_detalhe', pk=pk)


# ─────────────────────────────────────────────────────────────
# ASSINATURA — RENOVAR
# ─────────────────────────────────────────────────────────────

class RenovarAssinaturaView(SuperAdminMixin, View):
    def post(self, request, pk):
        assinatura = get_object_or_404(Assinatura, pk=pk)
        ciclo      = request.POST.get('ciclo', assinatura.ciclo)
        try:
            AssinaturaService.ativar(assinatura, ciclo, usuario=request.user)
            messages.success(
                request,
                f'Assinatura de "{assinatura.empresa.nome}" renovada até {assinatura.data_fim:%d/%m/%Y}.'
            )
        except Exception as e:
            messages.error(request, str(e))
        return redirect('admin_empresa_detalhe', pk=assinatura.empresa.pk)


# ─────────────────────────────────────────────────────────────
# USUÁRIO — ADICIONAR À EMPRESA
# ─────────────────────────────────────────────────────────────

class AdicionarUsuarioEmpresaView(SuperAdminMixin, View):
    def post(self, request, pk):
        empresa = get_object_or_404(TenantCompany, pk=pk)
        form    = UsuarioEmpresaAdicionarForm(request.POST)

        if not form.is_valid():
            for field, erros in form.errors.items():
                for erro in erros:
                    messages.error(request, f'{field}: {erro}')
            return redirect('admin_empresa_detalhe', pk=pk)

        user, senha = UsuarioEmpresaService.criar_admin_empresa(
            empresa      = empresa,
            email        = form.cleaned_data['email_usuario'],
            nome         = form.cleaned_data['nome_contato'],
            username     = form.cleaned_data.get('username') or '',
            role         = form.cleaned_data['role'],
        )
        request.session['nova_empresa_credenciais'] = {
            'empresa':  empresa.nome,
            'username': user.username,
            'senha':    senha,
            'email':    user.email,
        }
        messages.success(
            request,
            f'Usuário "{user.username}" adicionado à empresa "{empresa.nome}".'
        )
        return redirect('admin_empresa_detalhe', pk=pk)


# ─────────────────────────────────────────────────────────────
# USUÁRIO — DESATIVAR
# ─────────────────────────────────────────────────────────────

class ToggleUsuarioView(SuperAdminMixin, View):
    def post(self, request, pk):
        perfil  = get_object_or_404(PerfilUsuario, pk=pk)
        empresa = perfil.empresa

        perfil.ativo         = not perfil.ativo
        perfil.user.is_active = perfil.ativo
        perfil.save(update_fields=['ativo'])
        perfil.user.save(update_fields=['is_active'])

        acao = 'ativado' if perfil.ativo else 'desativado'
        messages.success(request, f'Usuário "{perfil.user.username}" {acao}.')
        return redirect('admin_empresa_detalhe', pk=empresa.pk)
