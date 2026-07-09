"""
relatorios/services.py
======================
Toda a lógica de consulta dos relatórios fica aqui.
As views apenas chamam esses métodos e passam o resultado ao template.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import (
    Sum, Count, Avg, F, Q,
    DecimalField, IntegerField,
    ExpressionWrapper, FloatField,
)
from django.db.models.functions import TruncMonth, TruncDate
from django.utils import timezone

from locacoes.models import Locacao, ItemLocacao
from produtos.models import Produto, CategoriaProduto
from clientes.models import Cliente


class RelatorioAtrasoService:
    """Locações que passaram da data de devolução e ainda estão abertas."""

    @staticmethod
    def dados(ordenar='dias_atraso'):
        hoje = timezone.localdate()

        qs = (
            Locacao.objects
            .filter(status__in=['ativa', 'atrasada'], data_fim_prevista__lt=hoje)
            .select_related('cliente')
            .prefetch_related('itens__produto')
            .order_by('data_fim_prevista')
        )

        resultado = []
        for loc in qs:
            dias = (hoje - loc.data_fim_prevista).days
            resultado.append({
                'locacao':        loc,
                'dias_atraso':    dias,
                'valor_total':    loc.valor_total,
                'produtos':       [f"{i.quantidade}× {i.produto.nome}" for i in loc.itens.all()],
            })

        if ordenar == 'valor':
            resultado.sort(key=lambda x: x['valor_total'], reverse=True)
        else:
            resultado.sort(key=lambda x: x['dias_atraso'], reverse=True)

        total_valor = sum(r['valor_total'] for r in resultado)
        return {
            'locacoes':    resultado,
            'total':       len(resultado),
            'total_valor': total_valor,
        }


class RelatorioFaturamentoService:
    """Faturamento agrupado por mês dentro de um intervalo."""

    @staticmethod
    def dados(meses: int = 12):
        hoje      = timezone.localdate()
        inicio    = hoje.replace(day=1) - timedelta(days=30 * (meses - 1))

        # Receita por mês (locações finalizadas ou ativas)
        por_mes = (
            Locacao.objects
            .filter(
                status__in=['finalizada', 'ativa', 'atrasada'],
                data_inicio__gte=inicio,
            )
            .annotate(mes=TruncMonth('data_inicio'))
            .values('mes')
            .annotate(
                total=Sum('valor_total'),
                quantidade=Count('id'),
            )
            .order_by('mes')
        )

        meses_lista = []
        for row in por_mes:
            meses_lista.append({
                'mes':        row['mes'],
                'mes_label':  row['mes'].strftime('%b/%Y'),
                'total':      row['total'] or Decimal('0'),
                'quantidade': row['quantidade'],
            })

        total_geral     = sum(m['total'] for m in meses_lista)
        total_locacoes  = sum(m['quantidade'] for m in meses_lista)
        media_mensal    = (total_geral / len(meses_lista)) if meses_lista else Decimal('0')

        # Ticket médio por locação
        ticket_medio = (
            Locacao.objects
            .filter(status__in=['finalizada', 'ativa', 'atrasada'], data_inicio__gte=inicio)
            .aggregate(media=Avg('valor_total'))['media'] or Decimal('0')
        )

        # Para o gráfico: valores normalizados (0-100) para barras CSS
        max_val = max((m['total'] for m in meses_lista), default=Decimal('1'))
        for m in meses_lista:
            m['pct'] = int(m['total'] / max_val * 100) if max_val else 0

        return {
            'meses':          meses_lista,
            'total_geral':    total_geral,
            'total_locacoes': total_locacoes,
            'media_mensal':   round(media_mensal, 2),
            'ticket_medio':   round(ticket_medio, 2),
            'periodo_meses':  meses,
        }


class RelatorioProdutosService:
    """Ranking de produtos por volume de locações e receita gerada."""

    @staticmethod
    def dados(limite: int = 20):
        ranking = (
            ItemLocacao.objects
            .filter(locacao__status__in=['finalizada', 'ativa', 'atrasada', 'pendente'])
            .values('produto__id', 'produto__nome', 'produto__codigo_interno',
                    'produto__categoria__nome', 'produto__valor_diario',
                    'produto__quantidade_total')
            .annotate(
                total_locacoes=Count('locacao', distinct=True),
                total_qtd_locada=Sum('quantidade'),
                receita_total=Sum('valor_total'),
            )
            .order_by('-total_qtd_locada')[:limite]
        )

        resultado = list(ranking)

        # Calcula % de ocupação acumulada para cada produto
        max_qtd = max((r['total_qtd_locada'] for r in resultado), default=1)
        for r in resultado:
            r['pct_uso'] = int(r['total_qtd_locada'] / max_qtd * 100) if max_qtd else 0

        total_receita = sum(r['receita_total'] or 0 for r in resultado)

        # Produtos sem nenhuma locação
        ids_locados = [r['produto__id'] for r in resultado]
        sem_locacao = (
            Produto.objects
            .filter(status='ativo')
            .exclude(id__in=ids_locados)
            .count()
        )

        return {
            'produtos':      resultado,
            'total_receita': total_receita,
            'sem_locacao':   sem_locacao,
            'limite':        limite,
        }


class RelatorioOcupacaoService:
    """Taxa de ocupação atual do estoque por produto e categoria."""

    @staticmethod
    def dados():
        hoje = timezone.localdate()

        # Quantidade em locação HOJE por produto
        em_uso = (
            ItemLocacao.objects
            .filter(
                locacao__status__in=['ativa', 'atrasada'],
               # locacao__data_inicio__lte=hoje,
               # locacao__data_fim_prevista__gte=hoje,
            )
            .values('produto__id')
            .annotate(qtd_em_uso=Sum('quantidade'))
        )
        uso_map = {r['produto__id']: r['qtd_em_uso'] for r in em_uso}

        produtos = (
            Produto.objects
            .filter(status='ativo')
            .select_related('categoria')
            .order_by('categoria__nome', 'nome')
        )

        resultado = []
        for p in produtos:
            em_uso_qtd = uso_map.get(p.id, 0)
            pct        = int(em_uso_qtd / p.quantidade_total * 100) if p.quantidade_total else 0
            resultado.append({
                'produto':       p,
                'em_uso':        em_uso_qtd,
                'disponivel':    p.quantidade_disponivel,
                'total':         p.quantidade_total,
                'pct_ocupacao':  pct,
                'status_cor':    'danger' if pct >= 90 else 'warning' if pct >= 60 else 'success',
            })

        # Agrupado por categoria
        from itertools import groupby
        from operator import itemgetter

        resultado.sort(key=lambda x: x['produto'].categoria.nome if x['produto'].categoria else 'Sem Categoria')

        por_categoria = []
        for cat_nome, itens in groupby(resultado, key=lambda x: x['produto'].categoria.nome if x['produto'].categoria else 'Sem Categoria'):
            itens_list = list(itens)
            total_em_uso = sum(i['em_uso'] for i in itens_list)
            total_estoque = sum(i['total'] for i in itens_list)
            por_categoria.append({
                'categoria': cat_nome,
                'itens':     itens_list,
                'pct_geral': int(total_em_uso / total_estoque * 100) if total_estoque else 0,
            })

        total_em_uso   = sum(r['em_uso'] for r in resultado)
        total_estoque  = sum(r['total'] for r in resultado)
        pct_geral      = int(total_em_uso / total_estoque * 100) if total_estoque else 0

        return {
            'por_categoria': por_categoria,
            'total_em_uso':  total_em_uso,
            'total_estoque': total_estoque,
            'pct_geral':     pct_geral,
            'data_ref':      hoje,
        }

from django.db.models import Max

class RelatorioClientesService:
    """Ranking de clientes por volume de locações e valor gerado."""

    @staticmethod
    def dados(limite: int = 20):
        ranking = (
            Locacao.objects
            .filter(status__in=['finalizada', 'ativa', 'atrasada'])
            .values('cliente__id', 'cliente__nome', 'cliente__cpf_cnpj',
                    'cliente__telefone', 'cliente__email')
            .annotate(
                total_locacoes=Count('id'),
                valor_total=Sum('valor_total'),
                ultima_locacao=Max('data_inicio'),
            )
            .order_by('-valor_total')[:limite]
        )

        resultado   = list(ranking)
        total_geral = sum(r['valor_total'] or 0 for r in resultado)

        # % do faturamento total
        for r in resultado:
            r['pct_faturamento'] = (
                round(float(r['valor_total']) / float(total_geral) * 100, 1)
                if total_geral else 0
            )

        # Clientes sem nenhuma locação finalizada
        ids_ativos = [r['cliente__id'] for r in resultado]
        sem_locacao = Cliente.objects.filter(ativo=True).exclude(id__in=ids_ativos).count()

        return {
            'clientes':     resultado,
            'total_geral':  total_geral,
            'sem_locacao':  sem_locacao,
            'limite':       limite,
        }


class RelatorioStatusService:
    """Visão geral das locações por status em um período."""

    @staticmethod
    def dados(dias: int = 30):
        hoje  = timezone.localdate()
        desde = hoje - timedelta(days=dias)

        # Contagem e valor por status
        por_status = (
            Locacao.objects
            .filter(Q(data_inicio__gte=desde) | Q(status__in=['ativa', 'atrasada', 'pendente']))
            .values('status')
            .annotate(
                quantidade=Count('id'),
                valor=Sum('valor_total'),
            )
            .order_by('status')
        )

        STATUS_META = {
            'ativa':      {'label': 'Ativa',      'cor': 'success', 'icone': 'bi-check-circle-fill'},
            'pendente':   {'label': 'Pendente',   'cor': 'warning', 'icone': 'bi-clock-fill'},
            'atrasada':   {'label': 'Atrasada',   'cor': 'danger',  'icone': 'bi-exclamation-triangle-fill'},
            'finalizada': {'label': 'Finalizada', 'cor': 'secondary','icone': 'bi-check2-all'},
            'cancelada':  {'label': 'Cancelada',  'cor': 'dark',    'icone': 'bi-x-circle-fill'},
        }

        resultado   = []
        total_qtd   = 0
        total_valor = Decimal('0')

        for row in por_status:
            meta = STATUS_META.get(row['status'], {'label': row['status'], 'cor': 'secondary', 'icone': 'bi-circle'})
            valor = row['valor'] or Decimal('0')
            resultado.append({
                'status':     row['status'],
                'label':      meta['label'],
                'cor':        meta['cor'],
                'icone':      meta['icone'],
                'quantidade': row['quantidade'],
                'valor':      valor,
            })
            total_qtd   += row['quantidade']
            total_valor += valor

        # % por quantidade
        for r in resultado:
            r['pct'] = int(r['quantidade'] / total_qtd * 100) if total_qtd else 0

        # Locações criadas por dia nos últimos 30 dias (para mini sparkline)
        por_dia = (
            Locacao.objects
            .filter(criado_em__date__gte=desde)
            .annotate(dia=TruncDate('criado_em'))
            .values('dia')
            .annotate(qtd=Count('id'))
            .order_by('dia')
        )

        return {
            'por_status':   resultado,
            'total_qtd':    total_qtd,
            'total_valor':  total_valor,
            'por_dia':      list(por_dia),
            'periodo_dias': dias,
        }