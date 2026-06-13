"""
core/recursos_config.py
=======================
Configuração centralizada de todos os recursos do sistema.

Como usar:
    - em_desenvolvimento=True  → badge "Em breve", ícone cinza, não clicável
    - em_desenvolvimento=False → renderiza conforme o plano (ativo/inativo)

Para lançar um recurso, mude em_desenvolvimento para False.
O template e a view se atualizam automaticamente, sem tocar no modelo.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class RecursoConfig:
    nome: str                            # chave usada no campo JSON recursos{}
    display_name: str                    # nome exibido na UI
    icone: str                           # classe Bootstrap Icons
    descricao: str                       # tooltip / texto auxiliar
    em_desenvolvimento: bool = False     # True = badge "Em breve"
    previsao_lancamento: Optional[str] = None  # ex: "Q3 2025"


# ── Registro central ──────────────────────────────────────────
# A ORDEM aqui define a ordem de exibição na feature list do plano.
RECURSOS_CONFIG: Dict[str, RecursoConfig] = {
    'relatorios': RecursoConfig(
        nome='relatorios',
        display_name='Relatórios Avançados',
        icone='bi-bar-chart-fill',
        descricao='Relatórios de faturamento, ocupação, produtos e clientes.',
        em_desenvolvimento=False,
        previsao_lancamento=None,
    ),
    'whatsapp': RecursoConfig(
        nome='whatsapp',
        display_name='Alertas WhatsApp',
        icone='bi-whatsapp',
        descricao='Notificações automáticas de vencimento e atraso via WhatsApp.',
        em_desenvolvimento=True,
        previsao_lancamento=None,
    ),
    'api_acesso': RecursoConfig(
        nome='api_acesso',
        display_name='Acesso à API',
        icone='bi-code-slash',
        descricao='API REST completa para integrar com outros sistemas.',
        em_desenvolvimento=True,
        previsao_lancamento=None,
    ),
    'suporte_prioritario': RecursoConfig(
        nome='suporte_prioritario',
        display_name='Suporte Prioritário',
        icone='bi-headset',
        descricao='Atendimento com SLA de 4h em horário comercial.',
        em_desenvolvimento=True,
        previsao_lancamento=None,
    ),
}


def is_em_desenvolvimento(recurso_nome: str) -> bool:
    config = RECURSOS_CONFIG.get(recurso_nome)
    return config.em_desenvolvimento if config else False


def get_recurso_config(recurso_nome: str) -> Optional[RecursoConfig]:
    return RECURSOS_CONFIG.get(recurso_nome)


def get_recursos_para_plano(plano) -> list[dict]:
    """
    Retorna lista de dicts prontos para o template, com o estado
    de cada recurso calculado para o plano recebido.

    Estado possíveis por recurso:
        'ativo'           → plano tem o recurso E está lançado
        'indisponivel'    → plano NÃO tem o recurso (mas está lançado)
        'em_desenvolvimento' → recurso ainda não lançado (independe do plano)

    Exemplo de retorno:
        [
          {'config': RecursoConfig(...), 'estado': 'ativo'},
          {'config': RecursoConfig(...), 'estado': 'indisponivel'},
          {'config': RecursoConfig(...), 'estado': 'em_desenvolvimento'},
        ]
    """
    resultado = []
    for recurso_nome, config in RECURSOS_CONFIG.items():
        if config.em_desenvolvimento:
            estado = 'em_desenvolvimento'
        elif plano.tem_recurso(recurso_nome):
            estado = 'ativo'
        else:
            estado = 'indisponivel'

        resultado.append({
            'config': config,
            'estado': estado,
        })
    return resultado
