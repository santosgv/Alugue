"""
Camada de serviço para Locações.
Centraliza as regras de negócio, especialmente validação de disponibilidade.
"""
from datetime import date
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from .models import Locacao, ItemLocacao
from produtos.models import Produto


class DisponibilidadeError(Exception):
    """Exceção levantada quando há conflito de disponibilidade."""
    pass


class LocacaoService:
    """Serviço principal de gerenciamento de locações."""

    @staticmethod
    def verificar_disponibilidade(produto: Produto, quantidade: int,
                                   data_inicio: date, data_fim: date,
                                   excluir_locacao_id: int = None) -> dict:
        """
        Verifica se há quantidade disponível para um produto no período.
        
        Retorna dict com:
            - disponivel (bool)
            - quantidade_maxima (int): máxima disponível no período
            - conflitos (list): locações conflitantes
        """
        # Busca locações ativas que se sobrepõem ao período solicitado
        query = ItemLocacao.objects.filter(
            produto=produto,
            locacao__status__in=[Locacao.STATUS_ATIVA, Locacao.STATUS_PENDENTE],
            locacao__data_inicio__lte=data_fim,
            locacao__data_fim_prevista__gte=data_inicio,
        )

        if excluir_locacao_id:
            query = query.exclude(locacao_id=excluir_locacao_id)

        # Calcula o maior uso simultâneo no período (dia a dia)
        max_uso = 0
        conflitos = []
        current_date = data_inicio
        from datetime import timedelta

        while current_date <= data_fim:
            uso_dia = query.filter(
                locacao__data_inicio__lte=current_date,
                locacao__data_fim_prevista__gte=current_date,
            ).aggregate(total=Sum('quantidade'))['total'] or 0

            if uso_dia > max_uso:
                max_uso = uso_dia
            current_date += timedelta(days=1)

        quantidade_disponivel = produto.quantidade_total - max_uso

        if quantidade > quantidade_disponivel:
            conflitos_qs = query.select_related('locacao', 'locacao__cliente').distinct()
            conflitos = [
                {
                    'locacao_id': item.locacao.id,
                    'cliente': item.locacao.cliente.nome,
                    'quantidade': item.quantidade,
                    'data_inicio': item.locacao.data_inicio,
                    'data_fim': item.locacao.data_fim_prevista,
                }
                for item in conflitos_qs
            ]

        return {
            'disponivel': quantidade <= quantidade_disponivel,
            'quantidade_maxima': max(0, quantidade_disponivel),
            'quantidade_solicitada': quantidade,
            'quantidade_total': produto.quantidade_total,
            'conflitos': conflitos,
        }

    @staticmethod
    def verificar_disponibilidade_multiplos(itens_data: list,
                                             data_inicio: date, data_fim: date,
                                             excluir_locacao_id: int = None) -> list:
        """
        Verifica disponibilidade para múltiplos itens de uma vez.
        
        itens_data: [{'produto': Produto, 'quantidade': int}, ...]
        Retorna lista de erros (vazia se tudo ok).
        """
        erros = []
        for item in itens_data:
            resultado = LocacaoService.verificar_disponibilidade(
                produto=item['produto'],
                quantidade=item['quantidade'],
                data_inicio=data_inicio,
                data_fim=data_fim,
                excluir_locacao_id=excluir_locacao_id,
            )
            if not resultado['disponivel']:
                erros.append(
                    f"Produto '{item['produto'].nome}': solicitado {item['quantidade']}, "
                    f"disponível {resultado['quantidade_maxima']} no período."
                )
        return erros

    @classmethod
    @transaction.atomic
    def criar_locacao(cls, cliente, data_inicio: date, data_fim: date,
                      itens_data: list, usuario=None, observacoes: str = '') -> Locacao:
        """
        Cria uma locação completa com validação de disponibilidade.
        
        itens_data: [{'produto_id': int, 'quantidade': int, 'valor_unitario': Decimal}, ...]
        Levanta DisponibilidadeError se não houver disponibilidade.
        """
        # Monta lista para validação
        itens_validacao = []
        for item_data in itens_data:
            produto = Produto.objects.get(pk=item_data['produto_id'])
            itens_validacao.append({
                'produto': produto,
                'quantidade': item_data['quantidade'],
            })

        # Valida disponibilidade de todos os itens
        erros = cls.verificar_disponibilidade_multiplos(itens_validacao, data_inicio, data_fim)
        if erros:
            raise DisponibilidadeError('\n'.join(erros))

        # Cria a locação
        locacao = Locacao.objects.create(
            cliente=cliente,
            data_inicio=data_inicio,
            data_fim_prevista=data_fim,
            status=Locacao.STATUS_ATIVA,
            observacoes=observacoes,
            criado_por=usuario,
        )

        # Cria os itens e desconta disponibilidade
        for item_data in itens_data:
            produto = Produto.objects.select_for_update().get(pk=item_data['produto_id'])
            ItemLocacao.objects.create(
                locacao=locacao,
                produto=produto,
                quantidade=item_data['quantidade'],
                valor_unitario=item_data['valor_unitario'],
            )
            produto.quantidade_disponivel -= item_data['quantidade']
            produto.save(update_fields=['quantidade_disponivel'])

        locacao.calcular_valor_total()
        return locacao

    @classmethod
    @transaction.atomic
    def finalizar_locacao(cls, locacao: Locacao) -> Locacao:
        """Finaliza uma locação e devolve os produtos ao estoque."""
        if locacao.status not in [Locacao.STATUS_ATIVA, Locacao.STATUS_ATRASADA]:
            raise ValueError(f"Não é possível finalizar locação com status '{locacao.get_status_display()}'.")

        for item in locacao.itens.select_related('produto'):
            produto = Produto.objects.select_for_update().get(pk=item.produto_id)
            produto.quantidade_disponivel += item.quantidade
            produto.save(update_fields=['quantidade_disponivel'])

        locacao.status = Locacao.STATUS_FINALIZADA
        locacao.data_fim_real = timezone.localdate()
        locacao.save(update_fields=['status', 'data_fim_real'])
        return locacao

    @classmethod
    @transaction.atomic
    def cancelar_locacao(cls, locacao: Locacao) -> Locacao:
        """Cancela uma locação e devolve os produtos ao estoque."""
        if locacao.status == Locacao.STATUS_FINALIZADA:
            raise ValueError("Não é possível cancelar uma locação já finalizada.")
        if locacao.status == Locacao.STATUS_CANCELADA:
            raise ValueError("Locação já está cancelada.")

        # Devolve estoque apenas se estava ativa/pendente
        if locacao.status in [Locacao.STATUS_ATIVA, Locacao.STATUS_PENDENTE, Locacao.STATUS_ATRASADA]:
            for item in locacao.itens.select_related('produto'):
                produto = Produto.objects.select_for_update().get(pk=item.produto_id)
                produto.quantidade_disponivel += item.quantidade
                produto.save(update_fields=['quantidade_disponivel'])

        locacao.status = Locacao.STATUS_CANCELADA
        locacao.save(update_fields=['status'])
        return locacao

    @classmethod
    @transaction.atomic
    def atualizar_locacao(cls, locacao: Locacao, data_inicio: date, data_fim: date,
                          itens_data: list, observacoes: str = '') -> Locacao:
        """
        Atualiza locação existente com revalidação de disponibilidade.
        Devolve estoque dos itens antigos e recalcula com os novos.
        """
        # Devolve estoque dos itens atuais
        for item in locacao.itens.select_related('produto'):
            produto = Produto.objects.select_for_update().get(pk=item.produto_id)
            produto.quantidade_disponivel += item.quantidade
            produto.save(update_fields=['quantidade_disponivel'])

        # Remove itens antigos
        locacao.itens.all().delete()

        # Valida nova disponibilidade (excluindo a própria locação)
        itens_validacao = []
        for item_data in itens_data:
            produto = Produto.objects.get(pk=item_data['produto_id'])
            itens_validacao.append({'produto': produto, 'quantidade': item_data['quantidade']})

        erros = cls.verificar_disponibilidade_multiplos(
            itens_validacao, data_inicio, data_fim, excluir_locacao_id=locacao.id
        )
        if erros:
            # Rollback vai acontecer automaticamente pela transaction.atomic
            raise DisponibilidadeError('\n'.join(erros))

        # Atualiza locação
        locacao.data_inicio = data_inicio
        locacao.data_fim_prevista = data_fim
        locacao.observacoes = observacoes
        locacao.save(update_fields=['data_inicio', 'data_fim_prevista', 'observacoes'])

        # Recria itens
        for item_data in itens_data:
            produto = Produto.objects.select_for_update().get(pk=item_data['produto_id'])
            ItemLocacao.objects.create(
                locacao=locacao,
                produto=produto,
                quantidade=item_data['quantidade'],
                valor_unitario=item_data['valor_unitario'],
            )
            produto.quantidade_disponivel -= item_data['quantidade']
            produto.save(update_fields=['quantidade_disponivel'])

        locacao.calcular_valor_total()
        return locacao


class DisponibilidadeService:
    """Serviço para consultas de disponibilidade e dashboard."""

    @staticmethod
    def produtos_disponiveis_hoje():
        """Produtos com quantidade_disponivel > 0 hoje."""
        return Produto.objects.filter(
            status=Produto.STATUS_ATIVO,
            quantidade_disponivel__gt=0
        ).order_by('nome')

    @staticmethod
    def produtos_reservados_hoje():
        """Produtos com locações ativas hoje."""
        hoje = timezone.localdate()
        from django.db.models import F
        return Produto.objects.filter(
            status=Produto.STATUS_ATIVO,
            itens_locacao__locacao__status__in=[Locacao.STATUS_ATIVA, Locacao.STATUS_PENDENTE],
            itens_locacao__locacao__data_inicio__lte=hoje,
            itens_locacao__locacao__data_fim_prevista__gte=hoje,
        ).distinct()

    @staticmethod
    def produtos_proximos_devolucao(dias: int = 3):
        """Produtos com devolução prevista nos próximos N dias."""
        from datetime import timedelta
        hoje = timezone.localdate()
        limite = hoje + timedelta(days=dias)
        return Locacao.objects.filter(
            status__in=[Locacao.STATUS_ATIVA, Locacao.STATUS_ATRASADA],
            data_fim_prevista__gte=hoje,
            data_fim_prevista__lte=limite,
        ).select_related('cliente').prefetch_related('itens__produto').order_by('data_fim_prevista')

    @staticmethod
    def locacoes_atrasadas():
        """Locações com data_fim_prevista passada e ainda ativas."""
        hoje = timezone.localdate()
        return Locacao.objects.filter(
            status=Locacao.STATUS_ATIVA,
            data_fim_prevista__lt=hoje,
        ).select_related('cliente').prefetch_related('itens__produto').order_by('data_fim_prevista')

    @staticmethod
    def atualizar_status_atrasadas():
        """Atualiza status de locações vencidas para 'atrasada'. Chamar via cron/management command."""
        hoje = timezone.localdate()
        count = Locacao.objects.filter(
            status=Locacao.STATUS_ATIVA,
            data_fim_prevista__lt=hoje,
        ).update(status=Locacao.STATUS_ATRASADA)
        return count