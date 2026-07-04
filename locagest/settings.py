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
import logging
from django.contrib.messages import constants

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config(
    'SECRET_KEY'
)

DEBUG = config('DEBUG')

# settings.py - Configuração para produção
if not DEBUG:
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'json': {
                'class': 'pythonjsonlogger.jsonlogger.JsonFormatter',
                'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
            },
            'verbose': {
                'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
                'style': '{',
            },
        },
        'handlers': {
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join('/home/Alugese/log/django.log'),
                'maxBytes': 1024 * 1024 * 100,  # 100 MB
                'backupCount': 30,
                'formatter': 'verbose',
                'level': 'INFO',
            },
            'error_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join('/home/Alugese/log/errors.log'),
                'maxBytes': 1024 * 1024 * 100,
                'backupCount': 30,
                'formatter': 'verbose',
                'level': 'ERROR',
            },
            'stripe_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join('/home/Alugese/log/stripe.log'),
                'maxBytes': 1024 * 1024 * 100,
                'backupCount': 30,
                'formatter': 'verbose',
                'level': 'INFO',
            },
            'webhook_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join('/home/Alugese/log/webhook.log'),
                'maxBytes': 1024 * 1024 * 100,
                'backupCount': 30,
                'formatter': 'verbose',
                'level': 'INFO',
            },
        },
        'loggers': {
            'core.stripe_service': {
                'handlers': ['stripe_file', 'error_file'],
                'level': 'INFO',
                'propagate': False,
            },
            'core.stripe_views': {
                'handlers': ['stripe_file', 'error_file'],
                'level': 'INFO',
                'propagate': False,
            },
            'core.webhook': {
                'handlers': ['webhook_file', 'error_file'],
                'level': 'INFO',
                'propagate': False,
            },
        },
    }

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
    'django.contrib.sites',
    'django.contrib.sitemaps',
    # AllAuth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    # Projeto
    'accounts',   
    'core',      
    'clientes',   
    'produtos',   
    'locacoes',   
    'agenda',     
    'notificacoes',
    'relatorios',
]

SHARED_APPS = [
       'django_tenants',     
       'django.contrib.sites',
       'django.contrib.sitemaps',
           # AllAuth
       'allauth',
       'allauth.account',
       'allauth.socialaccount',
       'allauth.socialaccount.providers.google',
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
        'core.tenant_oauth_middleware.TenantOAuthMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
        'django.middleware.clickjacking.XFrameOptionsMiddleware',
        'core.middleware.PlanoMiddleware', 
        'core.middleware.AssinaturaGuardMiddleware',
        # AllAuth
        'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'locagest.urls'
PUBLIC_SCHEMA_URLCONF = 'locagest.urls_public'

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
TENANT_BASE_DOMAIN = 'localhost'
TENANT_DEV_PORT    = '8000'
TENANT_MODEL          = 'core.TenantCompany'  
TENANT_DOMAIN_MODEL   = 'core.Domain'           
PUBLIC_SCHEMA_NAME = 'public'

# ── allauth: adapters customizados ────────────────────────────
# Habilitam o redirecionamento para o subdomínio do tenant
# após autenticação Google.
SOCIALACCOUNT_ADAPTER = 'accounts.google_adapter.TenantSocialAccountAdapter'
ACCOUNT_ADAPTER       = 'accounts.google_adapter.TenantAccountAdapter'


# ── Auth ───────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL             = '/accounts/login/'
LOGOUT_URL            = '/accounts/logout'
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
#DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@locagest.com.br')
DEFAULT_FROM_EMAIL=config('EMAIL_HOST_USER')
EMAIL_HOST_USER= config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD= config('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS=True
EMAIL_PORT =587
EMAIL_HOST='smtp.office365.com'

SITE_ID = 1


# Configurações de Autenticação
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# AllAuth Settings
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 7
ACCOUNT_LOGIN_ATTEMPTS_LIMIT = 5
ACCOUNT_LOGIN_ATTEMPTS_TIMEOUT = 300
SOCIALACCOUNT_LOGIN_ON_GET = True

# Google OAuth2
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id':config('GOOGLE_CLIENT_ID'),
            'secret': config('GOOGLE_CLIENT_SECRET'),
            'key': ''
        },
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'VERIFIED_EMAIL': True,
        'EMAIL_AUTHENTICATION': True,
        #'OAUTH_PKCE_ENABLED': True,  # Ativar PKCE para mais segurança
    }
}

PUBLIC_DOMAIN='localhost:8000'

# Forçar URL de callback fixa
SOCIAL_AUTH_GOOGLE_OAUTH2_REDIRECT_URI = f'https://{PUBLIC_DOMAIN}/auth/google/login/callback/'

# Para desenvolvimento
if DEBUG:
    SOCIAL_AUTH_GOOGLE_OAUTH2_REDIRECT_URI = f'http://{PUBLIC_DOMAIN}/auth/google/login/callback/'


MESSAGE_TAGS = {
    constants.DEBUG: 'alert-primary',
    constants.ERROR: 'alert-danger',
    constants.SUCCESS: 'alert-success',
    constants.INFO: 'alert-info',
    constants.WARNING: 'alert-warning',
}

WHATSAPP_API_VERSION  = 'v20.0'
WHATSAPP_VERIFY_TOKEN = config('WHATSAPP_VERIFY_TOKEN')