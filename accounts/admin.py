from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from .models import PerfilUsuario


class PerfilUsuarioInline(admin.StackedInline):
    model  = PerfilUsuario
    extra  = 0
    fields = ('empresa', 'role', 'ativo')


class UserAdmin(BaseUserAdmin):
    inlines = (PerfilUsuarioInline,)
    list_display = ('username', 'email', 'first_name', 'last_name',
                     'role_badge', 'is_active', 'is_staff')

    def empresa_badge(self, obj):
        try:
            empresa = obj.perfil.empresa
            if empresa:
                return format_html('<span style="color:#16a34a;font-weight:600;">{}</span>', empresa.nome)
        except Exception:
            pass
        return format_html('<span style="color:#94a3b8;">—</span>')
    empresa_badge.short_description = 'Empresa'

    def role_badge(self, obj):
        try:
            return obj.perfil.get_role_display()
        except Exception:
            return '—'
    role_badge.short_description = 'Perfil'


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display  = ('user', 'empresa', 'role', 'ativo', 'criado_em')
    list_filter   = ('role', 'ativo', 'empresa')
    search_fields = ('user__username', 'user__email', 'empresa__nome')
    raw_id_fields = ('user',)
