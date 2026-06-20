"""
LocaGest — Settings

Modo atual: SINGLE-TENANT / SHARED-SCHEMA (SQLite, MVP)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GUIA DE MIGRAÇÃO PARA django-tenants (quando quiser escalar)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. pip install django-tenants psycopg2-binary

2. Trocar DATABASE ENGINE para postgresql (ver bloco DATABASES abaixo)

3. Adicionar 'django_tenants' como PRIMEIRO app em INSTALLED_APPS

4. Separar INSTALLED_APPS em SHARED_APPS e TENANT_APPS:

   SHARED_APPS = [
       'django_tenants',     # obrigatório primeiro
       'core',               # contém TenantCompany, SubscriptionPlan, Assinatura
       'accounts',           # contém PerfilUsuario (shared entre schemas)
       'django.contrib.contenttypes',
       'django.contrib.auth',
       'django.contrib.admin',
       'django.contrib.sessions',
       'django.contrib.messages',
       'django.contrib.staticfiles',
   ]

   TENANT_APPS = [           # um schema isolado por empresa
       'clientes',
       'produtos',
       'locacoes',
       'agenda',
       'notificacoes',
   ]

   INSTALLED_APPS = list(SHARED_APPS) + [a for a in TENANT_APPS if a not in SHARED_APPS]

5. Configurar o model de Tenant:

   TENANT_MODEL          = 'core.TenantCompany'   # já existe
   TENANT_DOMAIN_MODEL   = 'core.Domain'           # criar model Domain em core/models.py

   O model Domain é simples:
       from django_tenants.models import DomainMixin
       class Domain(DomainMixin):
           pass

   E TenantCompany precisa herdar de TenantMixin:
       from django_tenants.models import TenantMixin
       class TenantCompany(TenantMixin, models.Model):
           ...

6. Trocar middleware:
   MIDDLEWARE = [
       'django_tenants.middleware.main.TenantMainMiddleware',  # substitui PlanoMiddleware
       ...
   ]
   Em core/middleware.py, substituir _resolver_empresa() por:
       from django_tenants.utils import get_tenant
       request.empresa = get_tenant(request)

7. Trocar DATABASE_ROUTERS:
   DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']

8. Executar:
   python manage.py migrate_schemas --shared
   python manage.py create_tenant   # para cada empresa

O resto do código (services, views, templates, mixins) permanece igual.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from pathlib import Path
import os
from decouple import config
from django.contrib.messages import constants

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config(
    'SECRET_KEY'
)

DEBUG = config('DEBUG')

ALLOWED_HOSTS = ['*']

# ── Apps ──────────────────────────────────────────────────────
# Quando migrar para django-tenants, separar em SHARED_APPS e
# TENANT_APPS conforme o guia acima.
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_tenants',
    'django.contrib.sitemaps',
    # Projeto
    'accounts',   # shared (perfis de usuário)
    'core',       # shared (planos, assinaturas, empresas)
    'clientes',   # tenant
    'produtos',   # tenant
    'locacoes',   # tenant
    'agenda',     # tenant
    'notificacoes', # tenant
    'relatorios',
]

SHARED_APPS = [
       'django_tenants',     
       'accounts',           
       'core',               
       'clientes',
       'produtos',
       'locacoes',
        'agenda',
        'notificacoes',
        'relatorios',
       'django.contrib.contenttypes',
       'django.contrib.auth',
       'django.contrib.admin',
       'django.contrib.sessions',
       'django.contrib.messages',
       'django.contrib.staticfiles',
   ]

TENANT_APPS = [           # um schema isolado por empresa
       'clientes',
       'produtos',
       'locacoes',
       'agenda',
       'notificacoes',
   ]

INSTALLED_APPS = list(SHARED_APPS) + [a for a in TENANT_APPS if a not in SHARED_APPS]

# ── Middleware ─────────────────────────────────────────────────
# Para django-tenants: substituir PlanoMiddleware por
#   'django_tenants.middleware.main.TenantMainMiddleware'
# e manter os demais.
# ── Middleware ─────────────────────────────────────────────────

    # Com django-tenants: TenantMainMiddleware DEVE ser o primeiro
    # Ele resolve o schema pelo subdomínio antes de qualquer outra coisa
MIDDLEWARE = [
        'django_tenants.middleware.main.TenantMainMiddleware',
        'django.middleware.security.SecurityMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'core.middleware.PlanoMiddleware', 
        'core.middleware.AssinaturaGuardMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
        'django.middleware.clickjacking.XFrameOptionsMiddleware',
    ]

ROOT_URLCONF = 'locagest.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'notificacoes.context_processors.notificacoes_nao_lidas',
                'core.context_processors.plano_context',
                'core.context_processors.user_perfil_context',
            ],
                    'libraries':{
            'filters':'templates.filters'
        }
        },
    },
]

WSGI_APPLICATION = 'locagest.wsgi.application'

# ── Banco de dados ─────────────────────────────────────────────
# MVP: SQLite.
# Para produção / django-tenants: PostgreSQL (obrigatório).
DATABASES = {
    'default': {
        #'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.sqlite3'),
        #'NAME':   os.environ.get('DB_NAME',   str(BASE_DIR / 'db.sqlite3')),
        # PostgreSQL / django-tenants:
         'ENGINE':   config('ENGINE_POST'),
         'NAME':     config('DB_NAME_POST'),
         'USER':     config('DB_USER_POST'),
         'PASSWORD': config('DB_PASSWORD_POST'),
         'HOST':     config('DB_HOST_POST'),
         'PORT':     config('DB_PORT_POST'),
    }
}

DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']

TENANT_MODEL          = 'core.TenantCompany'  
TENANT_DOMAIN_MODEL   = 'core.Domain'           

# ── Auth ───────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL             = '/accounts/login/'
LOGIN_REDIRECT_URL    = '/'
LOGOUT_REDIRECT_URL   = '/accounts/login/'

# ── Localização ────────────────────────────────────────────────
LANGUAGE_CODE = 'pt-br'
TIME_ZONE     = 'America/Sao_Paulo'
USE_I18N      = True
USE_TZ        = True

# ── Arquivos ───────────────────────────────────────────────────
STATIC_URL       = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT      = BASE_DIR / 'staticfiles'

MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Email ──────────────────────────────────────────────────────
# Produção: trocar para smtp ou serviço transacional (SendGrid, SES, etc.)
EMAIL_BACKEND      = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend'
)
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@locagest.com.br')
