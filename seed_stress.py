#!/usr/bin/env python
"""
seed_stress.py — Geração de volume massivo para teste de stress do LocaGest
=============================================================================

Diferente do seed.py (dados de demonstração realistas), este script gera
um VOLUME GRANDE de Categorias, Produtos e Clientes para avaliar performance
de listagens, filtros, paginação e queries em geral.

NÃO gera Locações — inserir locação direto no banco sem passar pelo
LocacaoService pula a validação de disponibilidade de estoque, o que
deixaria os dados inconsistentes (produto com quantidade_disponivel
incoerente com o que está "locado"). Use a interface ou o LocacaoService
para gerar locações de teste se precisar.

Uso:
    python seed_stress.py                          # usa os defaults abaixo
    python seed_stress.py --clientes 50000
    python seed_stress.py --produtos 20000 --categorias 200
    python seed_stress.py --limpar                 # apaga antes de gerar


Execute dentro da pasta do projeto (onde está manage.py).
"""

import os
import sys
import django
import argparse
import random
import time
import uuid
from decimal import Decimal

# ── Bootstrap Django ──────────────────────────────────────────
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'locagest.settings')
django.setup()

from django.contrib.auth.models import User
from django.db import transaction, connection
from clientes.models import Cliente
from produtos.models import Produto, CategoriaProduto


# ─────────────────────────────────────────────────────────────
# CONFIGURAÇÃO DE LOTES (bulk_create em chunks evita explodir memória)
# ─────────────────────────────────────────────────────────────
BATCH_SIZE = 2000


# ─────────────────────────────────────────────────────────────
# DADOS BASE PARA VARIAÇÃO ALEATÓRIA
# ─────────────────────────────────────────────────────────────

PREFIXOS_CATEGORIA = [
    'Tendas', 'Mobiliário', 'Iluminação', 'Sonorização', 'Decoração',
    'Geradores', 'Climatização', 'Utensílios', 'Estruturas', 'Pisos',
    'Toldos', 'Coberturas', 'Palcos', 'Painéis', 'Letreiros',
    'Brinquedos', 'Infláveis', 'Jogos', 'Equipamentos Esportivos',
    'Equipamentos de Cozinha', 'Louças', 'Talheres', 'Toalhas',
    'Cadeiras Especiais', 'Mesas Especiais', 'Tapetes', 'Cortinas',
    'Treliças', 'Lonas', 'Andaimes', 'Ferramentas', 'Veículos',
]

SUFIXOS_CATEGORIA = [
    'para Eventos', 'Premium', 'Standard', 'Profissional', 'Básico',
    'Corporativo', 'Residencial', 'Industrial', 'Importado', 'Nacional',
    '', '', '',  # vazios para variar tamanho do nome
]

NOMES_PRODUTO_BASE = [
    'Tenda', 'Mesa', 'Cadeira', 'Refletor', 'Caixa de Som', 'Microfone',
    'Gerador', 'Ventilador', 'Climatizador', 'Painel', 'Cordão de LED',
    'Toalha', 'Talher', 'Prato', 'Copo', 'Taça', 'Banco', 'Sofá',
    'Puff', 'Balcão', 'Aparador', 'Biombo', 'Arco', 'Candelabro',
    'Tapete', 'Cortina', 'Treliça', 'Lona', 'Andaime', 'Palco',
    'Letreiro', 'Inflável', 'Pula-pula', 'Cama Elástica', 'Piscina de Bolinha',
    'Carrinho de Pipoca', 'Algodão Doce', 'Chocolateira', 'Fritadeira',
    'Forno', 'Fogão', 'Geladeira', 'Freezer', 'Bebedouro', 'Buffet',
]

MODELOS_PRODUTO = [
    'Standard', 'Premium', 'Plus', 'Pro', 'Master', 'Compact', 'XL',
    'Mini', 'Deluxe', 'Classic', 'Modern', 'Vintage', 'Industrial',
    '', '', '',
]

CORES_PRODUTO = [
    'Branco', 'Preto', 'Dourado', 'Prateado', 'Vermelho', 'Azul',
    'Verde', 'Madeira', 'Bege', '', '', '',
]

NOMES_PRIMEIRO = [
    'Ana', 'Bruno', 'Carla', 'Diego', 'Elaine', 'Fábio', 'Gabriela',
    'Henrique', 'Isabela', 'João', 'Karen', 'Lucas', 'Mariana', 'Nicolas',
    'Patrícia', 'Rafael', 'Sabrina', 'Thiago', 'Vanessa', 'William',
    'Aline', 'Bernardo', 'Camila', 'Daniel', 'Eduarda', 'Felipe',
    'Giovanna', 'Hugo', 'Ingrid', 'José', 'Kátia', 'Leonardo', 'Mônica',
    'Natália', 'Otávio', 'Paula', 'Quésia', 'Ricardo', 'Sandra', 'Tatiane',
]

NOMES_SOBRENOME = [
    'Silva', 'Souza', 'Oliveira', 'Santos', 'Costa', 'Ferreira', 'Almeida',
    'Pereira', 'Lima', 'Carvalho', 'Gomes', 'Ribeiro', 'Martins', 'Rocha',
    'Araújo', 'Fernandes', 'Barbosa', 'Vieira', 'Monteiro', 'Cardoso',
    'Teixeira', 'Moreira', 'Correia', 'Castro', 'Nascimento', 'Freitas',
    'Nunes', 'Mendes', 'Torres', 'Dias',
]

EMPRESAS_SUFIXO = [
    'Eventos', 'Festas', 'Buffet', 'Locações', 'Cerimonial', 'Decorações',
    'Produções', 'Assessoria', 'Espaço', 'Casa de Festas',
]

CIDADES_UF = [
    'São Paulo, SP', 'Rio de Janeiro, RJ', 'Belo Horizonte, MG',
    'Curitiba, PR', 'Porto Alegre, RS', 'Brasília, DF', 'Salvador, BA',
    'Recife, PE', 'Fortaleza, CE', 'Goiânia, GO', 'Campinas, SP',
    'Guarulhos, SP', 'Santos, SP', 'Niterói, RJ', 'Vitória, ES',
    'Florianópolis, SC', 'Joinville, SC', 'Londrina, PR', 'Maringá, PR',
    'Uberlândia, MG',
]

DDD_POR_REGIAO = ['11', '21', '31', '41', '51', '61', '71', '81', '85', '62']


# ─────────────────────────────────────────────────────────────
# HELPERS DE OUTPUT
# ─────────────────────────────────────────────────────────────

def cor(texto, codigo):
    return f'\033[{codigo}m{texto}\033[0m'

def ok(msg):     print(f'  {cor("✔", "32")} {msg}')
def info(msg):   print(f'  {cor("→", "36")} {msg}')
def erro(msg):   print(f'  {cor("✘", "31")} {msg}')
def titulo(msg): print(f'\n{cor(msg, "1;34")}')
def tempo(msg, segundos):
    print(f'  {cor("⏱", "33")} {msg}: {segundos:.2f}s')


def gerar_cpf_fake(seq: int) -> str:
    """Gera um CPF com formato válido (não passa validação real, só formato único)."""
    base = str(seq).zfill(9)
    return f'{base[:3]}.{base[3:6]}.{base[6:9]}-{seq % 100:02d}'


def gerar_cnpj_fake(seq: int) -> str:
    base = str(seq).zfill(8)
    return f'{base[:2]}.{base[2:5]}.{base[5:8]}/0001-{seq % 100:02d}'


def gerar_codigo_produto(seq: int) -> str:
    """Código interno único e curto."""
    return f'PRD-{seq:06d}'


# ─────────────────────────────────────────────────────────────
# LIMPEZA
# ─────────────────────────────────────────────────────────────

def limpar():
    titulo('Limpando dados existentes...')
    t0 = time.time()

    # Locações dependem de produtos/clientes — remove primeiro se existir
    from locacoes.models import Locacao, ItemLocacao
    n = ItemLocacao.objects.all().delete()[0]
    ok(f'ItemLocacao removidos: {n}')
    n = Locacao.objects.all().delete()[0]
    ok(f'Locação removidos: {n}')

    n = Produto.objects.all().delete()[0]
    ok(f'Produto removidos: {n}')
    n = CategoriaProduto.objects.all().delete()[0]
    ok(f'CategoriaProduto removidos: {n}')
    n = Cliente.objects.all().delete()[0]
    ok(f'Cliente removidos: {n}')

    tempo('Tempo de limpeza', time.time() - t0)


# ─────────────────────────────────────────────────────────────
# GERAÇÃO: CATEGORIAS
# ─────────────────────────────────────────────────────────────

def criar_categorias(total: int) -> list:
    titulo(f'Gerando {total:,} Categorias...'.replace(',', '.'))
    t0 = time.time()

    existentes = set(CategoriaProduto.objects.values_list('nome', flat=True))
    objs = []
    nomes_usados = set(existentes)

    for i in range(total):
        # Combina prefixo + sufixo + índice para garantir nome único
        prefixo = random.choice(PREFIXOS_CATEGORIA)
        sufixo  = random.choice(SUFIXOS_CATEGORIA)
        nome = f'{prefixo} {sufixo}'.strip()

        # Garante unicidade (campo tem unique=True no model)
        if nome in nomes_usados:
            nome = f'{nome} #{i}'
        nomes_usados.add(nome)

        objs.append(CategoriaProduto(
            nome=nome,
            descricao=f'Categoria gerada para teste de stress — lote {i // BATCH_SIZE + 1}.',
        ))

        if len(objs) >= BATCH_SIZE:
            CategoriaProduto.objects.bulk_create(objs, ignore_conflicts=True)
            info(f'{i + 1:,} categorias processadas...'.replace(',', '.'))
            objs = []

    if objs:
        CategoriaProduto.objects.bulk_create(objs, ignore_conflicts=True)

    tempo('Tempo de geração', time.time() - t0)
    categorias = list(CategoriaProduto.objects.all())
    ok(f'Total no banco: {len(categorias):,}'.replace(',', '.'))
    return categorias


# ─────────────────────────────────────────────────────────────
# GERAÇÃO: PRODUTOS
# ─────────────────────────────────────────────────────────────

def criar_produtos(total: int, categorias: list, admin: User) -> int:
    titulo(f'Gerando {total:,} Produtos...'.replace(',', '.'))
    t0 = time.time()

    # Pega o maior código existente para não colidir
    ultimo = (
        Produto.objects
        .filter(codigo_interno__startswith='PRD-')
        .order_by('-codigo_interno')
        .values_list('codigo_interno', flat=True)
        .first()
    )
    seq_inicial = int(ultimo.split('-')[1]) + 1 if ultimo else 1

    status_pool = ['ativo'] * 90 + ['inativo'] * 7 + ['manutencao'] * 3  # 90/7/3%

    objs = []
    criados = 0

    for i in range(total):
        seq = seq_inicial + i

        base   = random.choice(NOMES_PRODUTO_BASE)
        modelo = random.choice(MODELOS_PRODUTO)
        cor_p  = random.choice(CORES_PRODUTO)
        nome   = ' '.join(filter(None, [base, modelo, cor_p, str(random.randint(1, 99))]))

        qtd_total = random.choice([1, 2, 3, 5, 8, 10, 15, 20, 30, 50, 100, 200])
        qtd_disp  = random.randint(0, qtd_total)  # varia disponibilidade para stress real
        valor     = round(random.uniform(5, 2000), 2)

        objs.append(Produto(
            nome=nome[:200],
            categoria=random.choice(categorias) if categorias else None,
            codigo_interno=gerar_codigo_produto(seq),
            quantidade_total=qtd_total,
            quantidade_disponivel=qtd_disp,
            valor_diario=Decimal(str(valor)),
            descricao=f'Produto gerado automaticamente para teste de stress (seq {seq}).',
            status=random.choice(status_pool),
            criado_por=admin,
        ))

        if len(objs) >= BATCH_SIZE:
            Produto.objects.bulk_create(objs, ignore_conflicts=True)
            criados += len(objs)
            info(f'{criados:,} produtos inseridos...'.replace(',', '.'))
            objs = []

    if objs:
        Produto.objects.bulk_create(objs, ignore_conflicts=True)
        criados += len(objs)

    tempo('Tempo de geração', time.time() - t0)
    total_banco = Produto.objects.count()
    ok(f'Total no banco: {total_banco:,}'.replace(',', '.'))
    return total_banco


# ─────────────────────────────────────────────────────────────
# GERAÇÃO: CLIENTES
# ─────────────────────────────────────────────────────────────

def criar_clientes(total: int, admin: User) -> int:
    titulo(f'Gerando {total:,} Clientes...'.replace(',', '.'))
    t0 = time.time()

    # Sequência única baseada em uuid curto para evitar colisão de cpf_cnpj
    objs = []
    criados = 0

    # Proporção 80% PF / 20% PJ — realista para esse tipo de negócio
    for i in range(total):
        is_pj = random.random() < 0.20

        cidade = random.choice(CIDADES_UF)
        ddd    = random.choice(DDD_POR_REGIAO)
        tel    = f'({ddd}) 9{random.randint(1000,9999)}-{random.randint(1000,9999)}'

        if is_pj:
            nome_empresa = (
                f'{random.choice(NOMES_SOBRENOME)} '
                f'{random.choice(EMPRESAS_SUFIXO)} '
                f'{"ME" if random.random() < 0.5 else "Ltda"}'
            )
            doc   = gerar_cnpj_fake(i + 1)
            email = f'contato{i}@{nome_empresa.lower().split()[0]}.com.br'
            nome  = nome_empresa
        else:
            primeiro  = random.choice(NOMES_PRIMEIRO)
            sobrenome = random.choice(NOMES_SOBRENOME)
            sobrenome2 = random.choice(NOMES_SOBRENOME)
            nome  = f'{primeiro} {sobrenome} {sobrenome2}'
            doc   = gerar_cpf_fake(i + 1)
            email = f'{primeiro.lower()}.{sobrenome.lower()}{i}@email.com'

        objs.append(Cliente(
            nome=nome,
            cpf_cnpj=doc,
            telefone=tel,
            email=email,
            endereco=f'Rua {random.choice(NOMES_SOBRENOME)}, {random.randint(1, 9999)} — {cidade}',
            observacoes='' if random.random() < 0.7 else random.choice(
                ['Cliente VIP', 'Parceiro recorrente', 'Indicação']
            ),
            ativo=random.random() < 0.95,  # 5% inativos para variar filtros
            criado_por=admin,
        ))

        if len(objs) >= BATCH_SIZE:
            Cliente.objects.bulk_create(objs, ignore_conflicts=True)
            criados += len(objs)
            info(f'{criados:,} clientes inseridos...'.replace(',', '.'))
            objs = []

    if objs:
        Cliente.objects.bulk_create(objs, ignore_conflicts=True)
        criados += len(objs)

    tempo('Tempo de geração', time.time() - t0)
    total_banco = Cliente.objects.count()
    ok(f'Total no banco: {total_banco:,}'.replace(',', '.'))
    return total_banco


# ─────────────────────────────────────────────────────────────
# RELATÓRIO DE PERFORMANCE DE LEITURA
# ─────────────────────────────────────────────────────────────

def benchmark_leitura():
    """
    Executa queries típicas da aplicação e mede o tempo,
    simulando o que as telas reais fazem (listagem, busca, filtro).
    """
    titulo('Benchmark de leitura (queries típicas da aplicação)')

    testes = []

    # 1. Listagem simples paginada (como ClienteListView)
    t0 = time.time()
    list(Cliente.objects.filter(ativo=True).order_by('nome')[:20])
    testes.append(('Listagem de clientes (20 primeiros, ordenado)', time.time() - t0))

    # 2. Busca textual (como o campo de busca usa icontains)
    t0 = time.time()
    list(Cliente.objects.filter(nome__icontains='Silva')[:20])
    testes.append(('Busca de clientes por nome (icontains)', time.time() - t0))

    # 3. Listagem de produtos com select_related (como ProdutoListView)
    t0 = time.time()
    list(Produto.objects.select_related('categoria').filter(status='ativo').order_by('nome')[:20])
    testes.append(('Listagem de produtos c/ categoria (select_related)', time.time() - t0))

    # 4. Filtro por categoria
    t0 = time.time()
    cat = CategoriaProduto.objects.first()
    if cat:
        list(Produto.objects.filter(categoria=cat)[:20])
    testes.append(('Filtro de produtos por categoria', time.time() - t0))

    # 5. Produtos com baixo estoque (query mais pesada, usada no dashboard)
    t0 = time.time()
    list(Produto.objects.filter(status='ativo', quantidade_disponivel__gt=0).count())
    testes.append(('Contagem de produtos disponíveis (dashboard)', time.time() - t0))

    # 6. Contagem total (usada em paginação)
    t0 = time.time()
    Cliente.objects.filter(ativo=True).count()
    testes.append(('Contagem total de clientes ativos (paginação)', time.time() - t0))

    for nome, segundos in testes:
        cor_tempo = '32' if segundos < 0.1 else '33' if segundos < 0.5 else '31'
        print(f'  {cor(f"{segundos*1000:7.1f}ms", cor_tempo)}  {nome}')

    print()
    print(f'  {cor("Dica:", "1;36")} tempos acima de 500ms em queries simples')
    print(f'  geralmente indicam falta de índice ou necessidade de cache.')


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Gera volume massivo de dados para teste de stress do LocaGest.'
    )
    parser.add_argument('--categorias', type=int, default=300,
                        help='Quantidade de categorias a gerar (default: 300)')
    parser.add_argument('--produtos', type=int, default=50_000,
                        help='Quantidade de produtos a gerar (default: 50.000)')
    parser.add_argument('--clientes', type=int, default=100_000,
                        help='Quantidade de clientes a gerar (default: 100.000)')
    parser.add_argument('--limpar', action='store_true',
                        help='Apaga todos os dados antes de gerar')
    parser.add_argument('--sem-benchmark', action='store_true',
                        help='Pula o benchmark de leitura ao final')
    args = parser.parse_args()

    print(f'\n{"═"*65}')
    print(f'  🔥  LocaGest — Geração de Volume para Teste de Stress')
    print(f'{"═"*65}')
    print(f'  Categorias : {args.categorias:,}'.replace(',', '.'))
    print(f'  Produtos   : {args.produtos:,}'.replace(',', '.'))
    print(f'  Clientes   : {args.clientes:,}'.replace(',', '.'))
    print(f'{"═"*65}')

    admin = User.objects.filter(is_superuser=True).first()
    if not admin:
        erro('Nenhum superuser encontrado. Execute: python manage.py createsuperuser')
        sys.exit(1)
    info(f'Usando usuário: {admin.username}')
    info(f'Engine do banco: {connection.vendor}')

    if connection.vendor == 'sqlite':
        print()
        print(f'  {cor("⚠ AVISO:", "1;33")} você está usando SQLite. Para volumes muito')
        print(f'  grandes (>100k registros) considere PostgreSQL — SQLite não')
        print(f'  paraleliza escritas e pode ficar lento no bulk_create.')

    if args.limpar:
        limpar()

    t_inicio = time.time()

    categorias = criar_categorias(args.categorias)
    total_produtos = criar_produtos(args.produtos, categorias, admin)
    total_clientes = criar_clientes(args.clientes, admin)

    t_total = time.time() - t_inicio

    # ── Resumo final ────────────────────────────────────────────
    print(f'\n{"═"*65}')
    print(f'  {cor("✔ Geração concluída!", "1;32")}')
    print(f'{"═"*65}')
    print(f'  Categorias no banco : {CategoriaProduto.objects.count():,}'.replace(',', '.'))
    print(f'  Produtos no banco   : {total_produtos:,}'.replace(',', '.'))
    print(f'  Clientes no banco   : {total_clientes:,}'.replace(',', '.'))
    print(f'  Tempo total         : {t_total:.2f}s')
    print(f'{"═"*65}\n')

    if not args.sem_benchmark:
        benchmark_leitura()

    print(f'\n{cor("Próximos passos:", "1;36")}')
    print('  • Abra /clientes/ e /produtos/ no navegador e meça o tempo de carregamento.')
    print('  • Teste os filtros e a busca textual com volume real.')
    print('  • Para gerar locações de teste, use a interface ou o LocacaoService')
    print('    (inserir direto no banco pula a validação de disponibilidade).')
    print()


if __name__ == '__main__':
    main()