#!/usr/bin/env python
"""
seed.py — População de dados para testes do LocaGest
=====================================================

Uso:
    python seed.py              # cria tudo (categorias, produtos, clientes, locações)
    python seed.py --limpar     # apaga dados existentes antes de criar
    python seed.py --limpar --sem-locacoes  # só cria cadastros base

Execute dentro da pasta do projeto (onde está manage.py).
"""

import os
import sys
import django
import argparse
import random
from decimal import Decimal
from datetime import date, timedelta

# ── Bootstrap Django ──────────────────────────────────────────
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'locagest.settings')
django.setup()

# Imports dos models (após o setup)
from django.contrib.auth.models import User
from django.db import transaction
from clientes.models import Cliente
from produtos.models import Produto, CategoriaProduto
from locacoes.models import Locacao, ItemLocacao

# ─────────────────────────────────────────────────────────────
# DADOS FAKE
# ─────────────────────────────────────────────────────────────

CATEGORIAS = [
    ('Tendas e Coberturas',  'Tendas, lonas, coberturas e estruturas para eventos ao ar livre.'),
    ('Mobiliário',           'Mesas, cadeiras, bancos e mobiliário em geral para eventos.'),
    ('Iluminação',           'Refletores, spots, canhões de luz, cordões e decoração luminosa.'),
    ('Sonorização',          'Caixas de som, microfones, amplificadores e mixers.'),
    ('Decoração',            'Arranjos, painéis, tapetes, biombos e itens decorativos.'),
    ('Geradores',            'Geradores de energia de pequeno, médio e grande porte.'),
    ('Climatização',         'Ventiladores industriais, climatizadores e ar-condicionado portátil.'),
    ('Utensílios de Cozinha','Fogões, buffets, rechauds e utensílios para eventos gastronômicos.'),
]

PRODUTOS_POR_CATEGORIA = {
    'Tendas e Coberturas': [
        ('Tenda 5x5m', 'TEND-001', 6, 150.00,  'Tenda sanfonada 5x5m, fácil montagem, ideal para eventos pequenos.'),
        ('Tenda 10x10m','TEND-002', 4, 280.00, 'Tenda com estrutura metálica reforçada, suporta até 50 pessoas.'),
        ('Tenda 10x20m','TEND-003', 2, 480.00, 'Tenda de grande porte para festas e eventos corporativos.'),
        ('Lona 6x4m',   'TEND-004', 8,  60.00, 'Lona impermeável para cobertura de palcos e áreas abertas.'),
    ],
    'Mobiliário': [
        ('Cadeira Plástica Branca', 'MOB-001', 200,  2.50, 'Cadeira plástica empilhável, cor branca.'),
        ('Cadeira Tiffany Dourada', 'MOB-002',  80,  8.00, 'Cadeira Tiffany com acabamento dourado, ideal para festas.'),
        ('Mesa Redonda 1,5m',       'MOB-003',  30, 25.00, 'Mesa redonda para 8 pessoas, com tampo plástico resistente.'),
        ('Mesa Retangular 2m',      'MOB-004',  40, 20.00, 'Mesa retangular dobrável, fácil transporte.'),
        ('Banco de Madeira 2m',     'MOB-005',  25, 15.00, 'Banco rústico de madeira para festas temáticas.'),
        ('Aparador Buffet',         'MOB-006',  15, 35.00, 'Aparador para buffet, estrutura metálica com tampo de vidro.'),
    ],
    'Iluminação': [
        ('Refletor PAR 64',        'ILU-001', 20,  30.00, 'Refletor PAR 64 com lâmpada de 1000W.'),
        ('Moving Head Beam',       'ILU-002',  8, 120.00, 'Moving head com feixe de luz robótico, efeitos variados.'),
        ('Cordão de LED 10m',      'ILU-003', 50,  12.00, 'Cordão de luz LED colorido, bivolt, 10 metros.'),
        ('Canhão de Luz UV',       'ILU-004', 10,  45.00, 'Canhão ultravioleta para efeitos em festas noturnas.'),
        ('Painel de LED RGB 1x2m', 'ILU-005',  6, 180.00, 'Painel de LED RGB programável para fundos fotográficos.'),
    ],
    'Sonorização': [
        ('Caixa de Som 15" Ativa', 'SOM-001', 12, 120.00, 'Caixa de som ativa 15 polegadas, 800W RMS.'),
        ('Subwoofer 18"',          'SOM-002',  6, 150.00, 'Subwoofer passivo 18 polegadas para graves profundos.'),
        ('Microfone sem Fio',      'SOM-003', 10,  50.00, 'Microfone UHF sem fio com receptor, alcance 80m.'),
        ('Mixer 16 Canais',        'SOM-004',  4, 200.00, 'Mesa de som analógica 16 canais com efeitos embutidos.'),
        ('Amplificador 2000W',     'SOM-005',  6, 130.00, 'Amplificador de potência 2000W RMS.'),
    ],
    'Decoração': [
        ('Painel de Flores 2x2m',  'DEC-001',  8, 150.00, 'Painel de flores artificiais para fotos e decoração.'),
        ('Tapete Vermelho 10m',    'DEC-002',  5,  80.00, 'Tapete vermelho estilo tapete olímpico, 10m x 1,5m.'),
        ('Biombo Ripado 1,8m',     'DEC-003', 12,  60.00, 'Biombo divisor de ambiente, ripas de madeira branca.'),
        ('Arco de Balões',         'DEC-004',  6,  90.00, 'Estrutura para arco de balões, altura ajustável até 3m.'),
        ('Candelabro 7 Braços',    'DEC-005', 20,  40.00, 'Candelabro dourado 7 braços para mesas de casamento.'),
    ],
    'Geradores': [
        ('Gerador 5KVA',  'GER-001', 4, 350.00, 'Gerador a diesel 5KVA silencioso, ideal para pequenos eventos.'),
        ('Gerador 15KVA', 'GER-002', 2, 650.00, 'Gerador trifásico 15KVA para médio porte.'),
        ('Gerador 30KVA', 'GER-003', 1, 980.00, 'Gerador de grande porte para eventos com alta demanda.'),
    ],
    'Climatização': [
        ('Ventilador Industrial 60cm', 'CLI-001', 15,  80.00, 'Ventilador industrial 60cm, 3 velocidades, bivolt.'),
        ('Climatizador 45L',           'CLI-002',  8, 130.00, 'Climatizador de ar por evaporação, reservatório 45L.'),
        ('Ar-condicionado Portátil',   'CLI-003',  4, 250.00, 'Split portátil 12.000 BTUs, fácil instalação.'),
    ],
    'Utensílios de Cozinha': [
        ('Fogão Industrial 4B', 'COZ-001',  6, 120.00, 'Fogão industrial 4 bocas a gás, estrutura inox.'),
        ('Rechaud Elétrico',    'COZ-002', 20,  25.00, 'Rechaud elétrico para manter alimentos quentes.'),
        ('Buffet Térmico 5 GN', 'COZ-003',  4, 200.00, 'Balcão de buffet térmico 5 cubas GN 1/1.'),
        ('Cuba Inox 50L',       'COZ-004', 10,  30.00, 'Cuba inox 50 litros para preparo e armazenamento.'),
    ],
}

CLIENTES = [
    # (nome, cpf_cnpj, telefone, email, cidade)
    ('Amanda Ferreira Souza',       '123.456.789-01', '(11) 99201-4532', 'amanda.ferreira@gmail.com',     'São Paulo, SP'),
    ('Bruno Carvalho Lima',         '234.567.890-12', '(11) 98312-5643', 'bruno.carvalho@hotmail.com',    'São Paulo, SP'),
    ('Carla Mendes Oliveira',       '345.678.901-23', '(21) 97423-6754', 'carla.mendes@gmail.com',        'Rio de Janeiro, RJ'),
    ('Diego Rocha Almeida',         '456.789.012-34', '(31) 96534-7865', 'diego.rocha@empresa.com.br',    'Belo Horizonte, MG'),
    ('Elaine Vieira Costa',         '567.890.123-45', '(41) 95645-8976', 'elaine.vieira@gmail.com',       'Curitiba, PR'),
    ('Fábio Nascimento Santos',     '678.901.234-56', '(51) 94756-9087', 'fabio.nascimento@outlook.com',  'Porto Alegre, RS'),
    ('Gabriela Torres Martins',     '789.012.345-67', '(61) 93867-0198', 'gabriela.torres@gmail.com',     'Brasília, DF'),
    ('Henrique Barbosa Pereira',    '890.123.456-78', '(71) 92978-1209', 'henrique.barbosa@gmail.com',    'Salvador, BA'),
    ('Isabela Gomes Ribeiro',       '901.234.567-89', '(81) 91089-2310', 'isabela.gomes@yahoo.com.br',    'Recife, PE'),
    ('João Pedro Araújo Dias',      '012.345.678-90', '(85) 90190-3421', 'joaopedro.araujo@gmail.com',    'Fortaleza, CE'),
    ('Karen Souza Fernandes',       '111.222.333-44', '(11) 99201-4532', 'karen.souza@empresa.com.br',    'São Paulo, SP'),
    ('Lucas Morais Correia',        '222.333.444-55', '(11) 98312-5643', 'lucas.morais@gmail.com',        'Campinas, SP'),
    ('Mariana Castro Lopes',        '333.444.555-66', '(19) 97423-6754', 'mariana.castro@hotmail.com',    'Ribeirão Preto, SP'),
    ('Nicolas Freitas Monteiro',    '444.555.666-77', '(27) 96534-7865', 'nicolas.freitas@gmail.com',     'Vitória, ES'),
    ('Patrícia Nunes Rodrigues',    '555.666.777-88', '(62) 95645-8976', 'patricia.nunes@outlook.com',    'Goiânia, GO'),
    # Empresas (CNPJ)
    ('Buffet Sabor & Arte Ltda',    '12.345.678/0001-90', '(11) 3456-7890', 'contato@saborarte.com.br',   'São Paulo, SP'),
    ('Espaço Eventos Premium ME',   '23.456.789/0001-01', '(11) 2345-6789', 'eventos@espacopremium.com.br','São Paulo, SP'),
    ('Cerimonial Bella Noite',      '34.567.890/0001-12', '(21) 3456-7890', 'bella@bellanioite.com.br',   'Rio de Janeiro, RJ'),
    ('Casa de Festas Alegria',      '45.678.901/0001-23', '(31) 4567-8901', 'festas@alegria.com.br',      'Belo Horizonte, MG'),
    ('WeddingPro Assessoria',       '56.789.012/0001-34', '(11) 5678-9012', 'assessoria@weddingpro.com.br','Guarulhos, SP'),
]

OBSERVACOES_LOCACAO = [
    'Cliente solicitou entrega às 8h. Confirmar endereço 1 dia antes.',
    'Montar na véspera do evento. Chave disponível a partir das 14h.',
    'Evento na cobertura do prédio — verificar acesso para elevador de carga.',
    'Cliente já possui gerador próprio, não incluir na locação.',
    'Necessário NF para reembolso corporativo.',
    'Retirada no local pelo próprio cliente.',
    '',  # sem observação
    '',
    '',
]


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def cor(texto, codigo):
    return f'\033[{codigo}m{texto}\033[0m'

def ok(msg):    print(f'  {cor("✔", "32")} {msg}')
def info(msg):  print(f'  {cor("→", "36")} {msg}')
def erro(msg):  print(f'  {cor("✘", "31")} {msg}')
def titulo(msg):print(f'\n{cor(msg, "1;34")}')


def data_relativa(dias: int) -> date:
    """Retorna hoje + dias (negativo = passado)."""
    return date.today() + timedelta(days=dias)


# ─────────────────────────────────────────────────────────────
# FUNÇÕES DE SEED
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def limpar():
    titulo('Limpando dados existentes...')
    ItemLocacao.objects.all().delete();  ok('ItemLocacao removidos')
    Locacao.objects.all().delete();      ok('Locações removidas')
    Produto.objects.all().delete();      ok('Produtos removidos')
    CategoriaProduto.objects.all().delete(); ok('Categorias removidas')
    Cliente.objects.all().delete();      ok('Clientes removidos')


@transaction.atomic
def criar_categorias() -> dict:
    titulo('Criando Categorias...')
    cats = {}
    for nome, descricao in CATEGORIAS:
        cat, created = CategoriaProduto.objects.get_or_create(
            nome=nome, defaults={'descricao': descricao}
        )
        cats[nome] = cat
        ok(f'{"Criada" if created else "Existente"}: {nome}')
    return cats


@transaction.atomic
def criar_produtos(categorias: dict, admin: User) -> list:
    titulo('Criando Produtos...')
    produtos = []
    for cat_nome, itens in PRODUTOS_POR_CATEGORIA.items():
        cat = categorias.get(cat_nome)
        for nome, codigo, qtd, valor, descricao in itens:
            # Pula se já existe
            if Produto.objects.filter(codigo_interno=codigo).exists():
                info(f'Já existe: {codigo} — {nome}')
                produtos.append(Produto.objects.get(codigo_interno=codigo))
                continue
            p = Produto.objects.create(
                nome=nome,
                categoria=cat,
                codigo_interno=codigo,
                quantidade_total=qtd,
                quantidade_disponivel=qtd,  # começa tudo disponível
                valor_diario=Decimal(str(valor)),
                descricao=descricao,
                status='ativo',
                criado_por=admin,
            )
            produtos.append(p)
            ok(f'{codigo} — {nome} (qtd:{qtd}, R${valor}/dia)')
    return produtos


@transaction.atomic
def criar_clientes(admin: User) -> list:
    titulo('Criando Clientes...')
    clientes = []
    for nome, cpf_cnpj, telefone, email, cidade in CLIENTES:
        if Cliente.objects.filter(cpf_cnpj=cpf_cnpj).exists():
            info(f'Já existe: {nome}')
            clientes.append(Cliente.objects.get(cpf_cnpj=cpf_cnpj))
            continue
        c = Cliente.objects.create(
            nome=nome,
            cpf_cnpj=cpf_cnpj,
            telefone=telefone,
            email=email,
            endereco=f'Rua das Flores, {random.randint(10, 999)} — {cidade}',
            observacoes=random.choice(['Cliente VIP', 'Parceiro recorrente', '']),
            ativo=True,
            criado_por=admin,
        )
        clientes.append(c)
        ok(f'{nome} ({cpf_cnpj})')
    return clientes


@transaction.atomic
def criar_locacoes(clientes: list, produtos: list, admin: User):
    titulo('Criando Locações...')

    # Filtra apenas produtos com estoque suficiente
    prods_disponiveis = [p for p in produtos if p.quantidade_total >= 2]

    hoje = date.today()

    # Cenários de locação com datas e status variados
    cenarios = [
        # (label, inicio_delta, fim_delta, status, num_itens)

        # ── FINALIZADAS (passado) ──────────────────────────────
        ('Finalizada há 2 meses',   -70, -60, 'finalizada', 2),
        ('Finalizada há 45 dias',   -55, -48, 'finalizada', 1),
        ('Finalizada há 30 dias',   -38, -31, 'finalizada', 3),
        ('Finalizada há 20 dias',   -25, -21, 'finalizada', 2),
        ('Finalizada há 15 dias',   -20, -16, 'finalizada', 1),
        ('Finalizada há 10 dias',   -14, -11, 'finalizada', 2),
        ('Finalizada há 7 dias',    -10,  -8, 'finalizada', 1),
        ('Finalizada há 3 dias',     -5,  -4, 'finalizada', 2),

        # ── CANCELADAS ─────────────────────────────────────────
        ('Cancelada antiga',        -40, -35, 'cancelada', 1),
        ('Cancelada recente',        -8,  -5, 'cancelada', 2),

        # ── ATRASADAS (deveria ter devolvido, não devolveu) ────
        ('Atrasada 5 dias',         -12,  -5, 'atrasada', 2),
        ('Atrasada 3 dias',          -8,  -3, 'atrasada', 1),
        ('Atrasada 1 dia',           -5,  -1, 'atrasada', 2),

        # ── ATIVAS (em andamento) ──────────────────────────────
        ('Ativa — devolução amanhã',   -3,    1, 'ativa', 1),
        ('Ativa — devolução em 2 dias', -2,   2, 'ativa', 2),
        ('Ativa — devolução em 3 dias', -4,   3, 'ativa', 1),
        ('Ativa — devolução em 5 dias', -2,   5, 'ativa', 3),
        ('Ativa — devolução em 7 dias', -1,   7, 'ativa', 2),
        ('Ativa — devolução em 10 dias', 0,  10, 'ativa', 1),
        ('Ativa — longa duração',       -5,  20, 'ativa', 2),

        # ── PENDENTES (agendadas p/ futuro) ───────────────────
        ('Pendente — começa amanhã',     1,   4, 'pendente', 1),
        ('Pendente — começa em 3 dias',  3,   7, 'pendente', 2),
        ('Pendente — começa em 7 dias',  7,  12, 'pendente', 1),
        ('Pendente — começa em 15 dias', 15, 20, 'pendente', 3),
        ('Pendente — começa em 30 dias', 30, 35, 'pendente', 2),
    ]

    criadas = 0
    random.shuffle(clientes)  # distribui clientes aleatoriamente

    for i, (label, ini_d, fim_d, status, num_itens) in enumerate(cenarios):
        cliente   = clientes[i % len(clientes)]
        inicio    = data_relativa(ini_d)
        fim       = data_relativa(fim_d)
        obs       = random.choice(OBSERVACOES_LOCACAO)

        # Seleciona produtos aleatórios que tenham estoque
        pool = random.sample(prods_disponiveis, min(num_itens, len(prods_disponiveis)))

        # Cria a locação (sem mexer no estoque — é seed de testes)
        locacao = Locacao(
            cliente=cliente,
            data_inicio=inicio,
            data_fim_prevista=fim,
            status=status,
            observacoes=obs,
            criado_por=admin,
        )
        if status == 'finalizada':
            locacao.data_fim_real = fim
        locacao.save()

        valor_total = Decimal('0')
        dias = max(1, (fim - inicio).days + 1)

        for produto in pool:
            qtd          = random.randint(1, min(3, produto.quantidade_total))
            valor_unit   = produto.valor_diario
            valor_item   = qtd * valor_unit * dias

            ItemLocacao.objects.create(
                locacao=locacao,
                produto=produto,
                quantidade=qtd,
                valor_unitario=valor_unit,
                valor_total=valor_item,
            )
            valor_total += valor_item

        locacao.valor_total = valor_total
        locacao.save(update_fields=['valor_total'])

        criadas += 1
        ok(f'#{locacao.pk:03d} [{status:10s}] {cliente.nome[:25]:25s} | {inicio} → {fim} | R$ {valor_total:,.2f} | {label}')

    return criadas


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Seed de dados para o LocaGest')
    parser.add_argument('--limpar',        action='store_true', help='Apaga dados existentes antes de criar')
    parser.add_argument('--sem-locacoes',  action='store_true', help='Cria apenas categorias, produtos e clientes')
    args = parser.parse_args()

    print(f'\n{"─"*55}')
    print(f'  🌱  LocaGest — Seed de Dados para Testes')
    print(f'{"─"*55}')

    # Superuser para associar os registros
    admin = User.objects.filter(is_superuser=True).first()
    if not admin:
        erro('Nenhum superuser encontrado. Execute: python manage.py createsuperuser')
        sys.exit(1)
    info(f'Usando usuário: {admin.username}')

    if args.limpar:
        limpar()

    categorias = criar_categorias()
    produtos   = criar_produtos(categorias, admin)
    clientes   = criar_clientes(admin)

    total_loc = 0
    #if not args.sem_locacoes:
    #    total_loc = criar_locacoes(clientes, produtos, admin)

    # ── Resumo ────────────────────────────────────────────────
    print(f'\n{"─"*55}')
    print(f'  {cor("✔ Seed concluído!", "1;32")}')
    print(f'{"─"*55}')
    print(f'  Categorias : {CategoriaProduto.objects.count()}')
    print(f'  Produtos   : {Produto.objects.count()}')
    print(f'  Clientes   : {Cliente.objects.count()}')
    print(f'  Locações   : {Locacao.objects.count()}')
    print(f'    ├ Ativas    : {Locacao.objects.filter(status="ativa").count()}')
    print(f'    ├ Pendentes : {Locacao.objects.filter(status="pendente").count()}')
    print(f'    ├ Atrasadas : {Locacao.objects.filter(status="atrasada").count()}')
    print(f'    ├ Finalizadas: {Locacao.objects.filter(status="finalizada").count()}')
    print(f'    └ Canceladas: {Locacao.objects.filter(status="cancelada").count()}')
    print(f'{"─"*55}\n')


if __name__ == '__main__':
    main()