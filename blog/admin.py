# blog/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Post, PostImagem, Comentario

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['nome', 'slug', 'icone', 'cor', 'ordem', 'ativo']
    prepopulated_fields = {'slug': ('nome',)}
    list_filter = ['ativo', 'cor']
    search_fields = ['nome', 'descricao']
    ordering = ['ordem']

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'categoria', 'autor', 'status', 
                   'published_at', 'views', 'destaque', 'visualizar_post']
    list_filter = ['status', 'categoria', 'destaque', 'created_at']
    search_fields = ['titulo', 'subtitulo', 'conteudo']
    prepopulated_fields = {'slug': ('titulo',)}
    readonly_fields = ['views', 'created_at', 'updated_at']
    date_hierarchy = 'published_at'
    #filter_horizontal = ['tags']
    
    fieldsets = (
        ('Conteúdo', {
            'fields': ('titulo', 'slug', 'subtitulo', 'categoria', 'tags', 
                      'conteudo', 'resumo')
        }),
        ('Mídia', {
            'fields': ('imagem_destaque',),
            'classes': ('collapse',)
        }),
        ('Publicação', {
            'fields': ('status', 'published_at', 'destaque')
        }),
        ('Métricas', {
            'fields': ('views', 'autor', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def visualizar_post(self, obj):
        if obj.is_published:
            return format_html('<a href="{}" target="_blank">🔗 Ver</a>', 
                             obj.get_absolute_url())
        return 'Não publicado'
    visualizar_post.short_description = 'Visualizar'

@admin.register(PostImagem)
class PostImagemAdmin(admin.ModelAdmin):
    list_display = ['post', 'legenda', 'ordem']
    list_filter = ['post']

@admin.register(Comentario)
class ComentarioAdmin(admin.ModelAdmin):
    list_display = ['nome', 'post', 'created_at', 'publicado']
    list_filter = ['publicado', 'created_at']
    search_fields = ['nome', 'email', 'conteudo']
    actions = ['aprovar_comentarios']

    def aprovar_comentarios(self, request, queryset):
        queryset.update(publicado=True)
    aprovar_comentarios.short_description = 'Aprovar comentários selecionados'