"""
Camada de serviço para Planos e Assinaturas.
Centraliza todas as regras de negócio relacionadas a limites e billing.
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.utils import timezone

from produtos.models import CategoriaProduto

from .models import SubscriptionPlan, TenantCompany, Assinatura, UsoAssinatura


# ─────────────────────────────────────────────────────────────
# EXCEÇÕES DE DOMÍNIO
# ─────────────────────────────────────────────────────────────

class LimitePlanoExcedido(Exception):
    """Levantada quando uma operação viola o limite do plano contratado."""
    pass


class AssinaturaInvalida(Exception):
    """Levantada quando não há assinatura ativa ou ela está expirada."""
    pass


# ─────────────────────────────────────────────────────────────
# SERVIÇO DE LIMITES
# ─────────────────────────────────────────────────────────────

class LimiteService:
    """
    Valida se o plano permite criar novos registros.
    Agnóstico ao tenant: recebe o plano e as contagens atuais.
    """

    @staticmethod
    def verificar_limite_clientes(plano: SubscriptionPlan, total_atual: int) -> None:
        if plano.clientes_ilimitados:
            return
        if total_atual >= plano.limite_clientes:
            raise LimitePlanoExcedido(
                f"Seu plano {plano.nome} permite até {plano.limite_clientes} clientes. "
                f"Faça upgrade para cadastrar mais."
            )

    @staticmethod
    def verificar_limite_produtos(plano: SubscriptionPlan, total_atual: int) -> None:
        if plano.produtos_ilimitados:
            return
        if total_atual >= plano.limite_produtos:
            raise LimitePlanoExcedido(
                f"Seu plano {plano.nome} permite até {plano.limite_produtos} produtos. "
                f"Faça upgrade para cadastrar mais."
            )
        
    @staticmethod
    def verificar_limite_categorias(plano: SubscriptionPlan, total_atual: int) -> None:
        if plano.categorias_ilimitados:
            return
        if total_atual >= plano.limite_categorias:
            raise LimitePlanoExcedido(
                f"Seu plano {plano.nome} permite até {plano.limite_categorias} Categorias. "
                f"Faça upgrade para cadastrar mais."
            )

    @staticmethod
    def verificar_limite_locacoes(plano: SubscriptionPlan, total_atual: int) -> None:
        if plano.locacoes_ilimitadas:
            return
        if total_atual >= plano.limite_locacoes:
            raise LimitePlanoExcedido(
                f"Seu plano {plano.nome} permite até {plano.limite_locacoes} locações ativas. "
                f"Finalize locações ou faça upgrade."
            )
        
    @staticmethod
    def verificar_limite_usuarios(plano: SubscriptionPlan, total_atual: int) -> None:
        if plano.usuarios_ilimitados:
            return
        if total_atual >= plano.limite_usuarios:
            raise LimitePlanoExcedido(
                f"Seu plano {plano.nome} permite até {plano.limite_usuarios} usuário(s). "
                f"Faça upgrade para adicionar mais."
            )

    @staticmethod
    def verificar_recurso(plano: SubscriptionPlan, chave: str, nome_exibicao: str) -> None:
        if not plano.tem_recurso(chave):
            raise LimitePlanoExcedido(
                f"O recurso '{nome_exibicao}' não está disponível no plano {plano.nome}. "
                f"Faça upgrade para acessar."
            )

    @staticmethod
    def uso_atual(plano: SubscriptionPlan, total_clientes: int,
                  total_produtos: int,total_categorias: int, 
                  total_locacoes: int = 0,total_usuarios: int = 0) -> dict:
        """
        Retorna dict com uso e percentuais para exibição no dashboard.
        """
        def pct(atual, limite):
            if limite == 0:
                return 0
            return min(100, round(atual / limite * 100))

        def status(p):
            if p >= 100:
                return 'danger'
            if p >= 80:
                return 'warning'
            return 'success'

        clientes_pct = pct(total_clientes, plano.limite_clientes)
        produtos_pct = pct(total_produtos, plano.limite_produtos)
        categorias_pct = pct(total_categorias, plano.limite_categorias)
        locacoes_pct = pct(total_locacoes, plano.limite_locacoes)
        usuarios_pct = pct(total_usuarios, plano.limite_usuarios)

        return {
            'clientes': {
                'atual': total_clientes,
                'limite': plano.limite_clientes,
                'ilimitado': plano.clientes_ilimitados,
                'pct': clientes_pct,
                'status': status(clientes_pct),
            },
            'produtos': {
                'atual': total_produtos,
                'limite': plano.limite_produtos,
                'ilimitado': plano.produtos_ilimitados,
                'pct': produtos_pct,
                'status': status(produtos_pct),
            },
            'categorias': {
                'atual': total_categorias,
                'limite': plano.limite_categorias,
                'ilimitado': plano.categorias_ilimitados,
                'pct': categorias_pct,
                'status': status(categorias_pct),
            },
            'locacoes': {
                'atual': total_locacoes,
                'limite': plano.limite_locacoes,
                'ilimitado': plano.locacoes_ilimitadas,
                'pct': locacoes_pct,
                'status': status(locacoes_pct),
            },
            'usuarios': {
                'atual': total_usuarios,
                'limite': plano.limite_usuarios,
                'ilimitado': plano.usuarios_ilimitados,
                'pct': usuarios_pct,
                'status': status(usuarios_pct),
            },
        }


# ─────────────────────────────────────────────────────────────
# SERVIÇO DE ASSINATURA
# ─────────────────────────────────────────────────────────────

class AssinaturaService:
    """Gerencia o ciclo de vida das assinaturas."""

    TRIAL_DIAS = 14

    @classmethod
    @transaction.atomic
    def criar_trial(cls, empresa: TenantCompany, plano: SubscriptionPlan,
                    usuario=None) -> Assinatura:
        """Inicia período de trial para uma empresa."""
        hoje = timezone.localdate()
        assinatura = Assinatura.objects.create(
            empresa=empresa,
            plano=plano,
            status=Assinatura.STATUS_TRIAL,
            ciclo=Assinatura.CICLO_MENSAL,
            data_inicio=hoje,
            data_fim=hoje + datetime.timedelta(days=cls.TRIAL_DIAS),
            valor_cobrado=Decimal('0.00'),
            criado_por=usuario,
        )
        return assinatura

    @classmethod
    @transaction.atomic
    def ativar(cls, assinatura: Assinatura, ciclo: str,
               data_inicio: Optional[datetime.date] = None,
               usuario=None) -> Assinatura:
        """Ativa ou renova uma assinatura."""
        hoje = data_inicio or timezone.localdate()

        if ciclo == Assinatura.CICLO_ANUAL:
            data_fim = hoje + datetime.timedelta(days=365)
            data_renovacao = data_fim
            valor = assinatura.plano.preco_anual
        else:
            data_fim = hoje + datetime.timedelta(days=30)
            data_renovacao = data_fim
            valor = assinatura.plano.preco_mensal

        assinatura.status         = Assinatura.STATUS_ATIVA
        assinatura.ciclo          = ciclo
        assinatura.data_inicio    = hoje
        assinatura.data_fim       = data_fim
        assinatura.data_renovacao = data_renovacao
        assinatura.valor_cobrado  = valor
        assinatura.cancelada_em   = None
        assinatura.motivo_cancel  = ''
        assinatura.save()
        return assinatura

    @classmethod
    @transaction.atomic
    def mudar_plano(cls, empresa: TenantCompany, novo_plano: SubscriptionPlan,
                    ciclo: str, usuario=None) -> Assinatura:
        """
        Muda o plano de uma empresa. Se há assinatura ativa, cria uma nova
        (a anterior é cancelada). Se não, cria do zero.
        """
        sub_atual = empresa.assinaturas.filter(
            status__in=[Assinatura.STATUS_ATIVA, Assinatura.STATUS_TRIAL]
        ).first()

        if sub_atual:
            sub_atual.status = Assinatura.STATUS_CANCELADA
            sub_atual.cancelada_em = timezone.now()
            sub_atual.motivo_cancel = f'Mudança de plano para {novo_plano.nome}'
            sub_atual.save(update_fields=['status', 'cancelada_em', 'motivo_cancel'])

        nova = Assinatura(
            empresa=empresa,
            plano=novo_plano,
            data_inicio=timezone.localdate(),
            criado_por=usuario,
        )
        nova = cls.ativar(nova, ciclo, usuario=usuario)
        return nova

    @classmethod
    @transaction.atomic
    def cancelar(cls, assinatura: Assinatura, motivo: str = '', usuario=None) -> Assinatura:
        if assinatura.status == Assinatura.STATUS_CANCELADA:
            raise AssinaturaInvalida("Assinatura já está cancelada.")
        assinatura.status = Assinatura.STATUS_CANCELADA
        assinatura.cancelada_em = timezone.now()
        assinatura.motivo_cancel = motivo
        assinatura.save(update_fields=['status', 'cancelada_em', 'motivo_cancel'])
        return assinatura

    @classmethod
    def verificar_expiradas(cls) -> int:
        """
        Marca como expiradas as assinaturas com data_fim < hoje.
        Chamar via management command / cron.
        """
        hoje = timezone.localdate()
        count = Assinatura.objects.filter(
        #    status__in=[Assinatura.STATUS_ATIVA, Assinatura.STATUS_TRIAL],
            data_fim__lt=hoje,
        ).update(status=Assinatura.STATUS_EXPIRADA)
        return count

    @staticmethod
    def plano_ativo_da_empresa(empresa: TenantCompany) -> Optional[SubscriptionPlan]:
        sub = empresa.assinaturas.filter(
        #    status__in=[Assinatura.STATUS_ATIVA, Assinatura.STATUS_TRIAL]
        ).select_related('plano').first()
        return sub.plano if sub else empresa.plano

    @staticmethod
    def assinatura_ativa(empresa: TenantCompany) -> Optional[Assinatura]:
        return empresa.assinaturas.filter(
           # status__in=[Assinatura.STATUS_ATIVA, Assinatura.STATUS_TRIAL]
        ).select_related('plano').first()


# ─────────────────────────────────────────────────────────────
# SERVIÇO DE USO
# ─────────────────────────────────────────────────────────────

class UsoService:
    """Captura snapshots de uso para histórico e billing futuro."""

    @staticmethod
    def registrar_snapshot(empresa: TenantCompany) -> UsoAssinatura:
        """
        Registra ou atualiza o snapshot de uso de hoje.
        Chamar via cron diário.
        """
        from clientes.models import Cliente
        from produtos.models import Produto
        from locacoes.models import Locacao

        hoje = timezone.localdate()
        uso, _ = UsoAssinatura.objects.update_or_create(
            empresa=empresa,
            data=hoje,
            defaults={
                'total_clientes': Cliente.objects.filter(ativo=True).count(),
                'total_produtos': Produto.objects.filter(status='ativo').count(),
                'total_categorias': CategoriaProduto.objects.count(),
                'total_locacoes': Locacao.objects.filter(
                    status__in=['ativa', 'pendente', 'atrasada']
                ).count(),
            }
        )
        return uso

    @staticmethod
    def historico(empresa: TenantCompany, dias: int = 30) -> list:
        desde = timezone.localdate() - datetime.timedelta(days=dias)
        return list(
            UsoAssinatura.objects.filter(empresa=empresa, data__gte=desde).order_by('data')
        )
