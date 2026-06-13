from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, View
from django.shortcuts import redirect
from django.http import JsonResponse
from .models import Notificacao


class NotificacaoListView(LoginRequiredMixin, ListView):
    model = Notificacao
    template_name = 'notificacoes/lista.html'
    context_object_name = 'notificacoes'
    paginate_by = 30

    def get_queryset(self):
        return Notificacao.objects.filter(
            usuario=self.request.user
        ).select_related('locacao_ref__cliente')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['nao_lidas'] = self.get_queryset().filter(lida=False).count()
        return ctx


class MarcarLidaView(LoginRequiredMixin, View):
    def post(self, request, pk):
        notif = Notificacao.objects.filter(pk=pk, usuario=request.user).first()
        if notif:
            notif.marcar_como_lida()
        return redirect('notificacoes:lista')


class MarcarTodasLidasView(LoginRequiredMixin, View):
    def post(self, request):
        from django.utils import timezone
        Notificacao.objects.filter(usuario=request.user, lida=False).update(
            lida=True, data_leitura=timezone.now()
        )
        return redirect('notificacoes:lista')