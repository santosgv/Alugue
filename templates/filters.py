from django import template
import re
from decimal import Decimal, InvalidOperation


register = template.Library()

@register.filter
def remove_formatacao_telefone(value):
    if not value:
        return ""
    return value.replace("(", "").replace(")", "").replace("-", "").replace(" ", "")

@register.filter
def money(value):
    """
    Formata qualquer valor monetário corretamente.

    Exemplos:
    100 -> 100,00
    100.00 -> 100,00
    '100.00' -> 100,00
    '100,00' -> 100,00
    Decimal('1500.90') -> 1.500,90
    """

    if value in [None, "", "N/D"]:
        return "0,00"

    try:
        if isinstance(value, str):

            # Se já veio no padrão brasileiro
            if "," in value:
                value = value.replace(".", "").replace(",", ".")

            # Se veio no padrão python/sql (100.00)
            else:
                value = value.strip()

        valor = Decimal(str(value))

        return (
            f"{valor:,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    except (InvalidOperation, ValueError, TypeError):
        return "0,00"
    
@register.filter
def cpf_cnpj(value):
    """
    Formata CPF ou CNPJ.
    """
    if not value:
        return ""

    numero = re.sub(r"\D", "", str(value))

    if len(numero) == 11:
        return f"{numero[:3]}.{numero[3:6]}.{numero[6:9]}-{numero[9:]}"

    if len(numero) == 14:
        return (
            f"{numero[:2]}.{numero[2:5]}.{numero[5:8]}/"
            f"{numero[8:12]}-{numero[12:]}"
        )

    return value

@register.filter
def telefone(value):
    """
    Formata telefone fixo ou celular.
    """
    if not value:
        return ""

    numero = re.sub(r"\D", "", str(value))

    # Celular: (31) 99999-9999
    if len(numero) == 11:
        return (
            f"({numero[:2]}) "
            f"{numero[2:7]}-{numero[7:]}"
        )

    # Fixo: (31) 3333-3333
    if len(numero) == 10:
        return (
            f"({numero[:2]}) "
            f"{numero[2:6]}-{numero[6:]}"
        )

    return value

@register.filter
def split(value, separator):
    return value.split(separator)


@register.simple_tag(takes_context=True)
def if_role(context, role, on_true='', on_false=''):
    """
    Mostra conteúdo baseado no role do usuário
    
    Uso: 
    {% if_role 'admin' %}
        Conteúdo para admin
    {% else %}
        Conteúdo para outros
    {% end_if_role %}
    """
    user_perfil = context.get('user_perfil')
    if user_perfil and user_perfil.role == role:
        return on_true
    return on_false

@register.filter
def has_role(user_perfil, role):
    """Filtro para verificar role"""
    return user_perfil and user_perfil.role == role

@register.simple_tag(takes_context=True)
def show_for_roles(context, roles, on_true='', on_false=''):
    """Mostra conteúdo para múltiplos roles"""
    user_perfil = context.get('user_perfil')
    if user_perfil and user_perfil.role in roles:
        return on_true
    return on_false

@register.filter
def can_edit(user_perfil):
    """Verifica se pode editar (não readonly)"""
    return user_perfil and user_perfil.role != user_perfil.ROLE_READONLY

@register.filter
def can_manage_settings(user_perfil):
    """Verifica se pode gerenciar configurações (admin apenas)"""
    return user_perfil and user_perfil.is_admin_empresa

@register.inclusion_tag('core/partials/menu_button.html', takes_context=True)
def render_button(context, permission_required, button_text, button_url):
    """
    Renderiza botão condicional baseado em permissão
    
    Uso: {% render_button 'can_edit' 'Editar' '/editar/1/' %}
    """
    user_perfil = context.get('user_perfil')
    has_permission = False
    
    if permission_required == 'can_edit':
        has_permission = user_perfil and user_perfil.can_edit
    elif permission_required == 'admin_only':
        has_permission = user_perfil and user_perfil.is_admin_empresa
    
    return {
        'has_permission': has_permission,
        'button_text': button_text,
        'button_url': button_url,
    }