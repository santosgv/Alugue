# blog/models.py
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from django.utils.text import slugify
from taggit.managers import TaggableManager
import markdown

class Category(models.Model):
    """Categoria dos posts"""
    nome = models.CharField('Nome', max_length=100, unique=True)
    slug = models.SlugField('Slug', max_length=100, unique=True, blank=True)
    descricao = models.TextField('Descrição', blank=True)
    icone = models.CharField('Ícone Font Awesome', max_length=50, blank=True, 
                            help_text='Ex: fa-calendar-alt')
    cor = models.CharField('Cor', max_length=20, default='primary',
                          choices=[
                              ('primary', 'Azul'),
                              ('success', 'Verde'),
                              ('danger', 'Vermelho'),
                              ('warning', 'Amarelo'),
                              ('info', 'Ciano'),
                              ('purple', 'Roxo'),
                              ('pink', 'Rosa'),
                              ('orange', 'Laranja'),
                          ])
    ordem = models.IntegerField('Ordem', default=0)
    ativo = models.BooleanField('Ativo', default=True)
    created_at = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = ['ordem', 'nome']

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nome)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('blog:categoria_detail', kwargs={'slug': self.slug})


class Post(models.Model):
    """Post do blog"""
    STATUS_CHOICES = [
        ('draft', 'Rascunho'),
        ('published', 'Publicado'),
        ('archived', 'Arquivado'),
    ]
    
    titulo = models.CharField('Título', max_length=200)
    slug = models.SlugField('Slug', max_length=200, unique=True, blank=True)
    subtitulo = models.CharField('Subtítulo', max_length=300, blank=True)
    
    conteudo = models.TextField('Conteúdo')
    resumo = models.TextField('Resumo', max_length=500, 
                             help_text='Breve resumo do post para listagem')
    
    imagem_destaque = models.ImageField('Imagem de Destaque', 
                                       upload_to='blog/posts/%Y/%m/',
                                       blank=True, null=True)
    
    categoria = models.ForeignKey(Category, on_delete=models.PROTECT, 
                                 related_name='posts')
    tags = TaggableManager('Tags', blank=True)
    
    autor = models.ForeignKey(User, on_delete=models.PROTECT, 
                             related_name='blog_posts')
    
    status = models.CharField('Status', max_length=20, 
                             choices=STATUS_CHOICES, default='draft')
    
    views = models.PositiveIntegerField('Visualizações', default=0)
    destaque = models.BooleanField('Post em Destaque', default=False)
    
    published_at = models.DateTimeField('Data de Publicação', 
                                       null=True, blank=True)
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Post'
        verbose_name_plural = 'Posts'
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['slug', 'status']),
            models.Index(fields=['-published_at']),
        ]

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.titulo)
            # Garante slug único
            original_slug = self.slug
            counter = 1
            while Post.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()
        
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('blog:post_detail', kwargs={'slug': self.slug})

    def get_conteudo_html(self):
        """Retorna o conteúdo em HTML (Markdown)"""
        return markdown.markdown(
            self.conteudo,
            extensions=['extra', 'codehilite', 'toc', 'smarty']
        )

    def get_tempo_leitura(self):
        """Estima o tempo de leitura"""
        palavras = len(self.conteudo.split())
        minutos = max(1, round(palavras / 200))
        return minutos

    def incrementar_views(self):
        """Incrementa o contador de visualizações"""
        self.views += 1
        self.save(update_fields=['views'])

    @property
    def is_published(self):
        return self.status == 'published' and self.published_at

    @classmethod
    def get_published(cls):
        return cls.objects.filter(status='published', published_at__lte=timezone.now())

    @classmethod
    def get_destaques(cls):
        return cls.get_published().filter(destaque=True)[:5]

    @classmethod
    def get_recentes(cls, limit=5):
        return cls.get_published().order_by('-published_at')[:limit]

    @classmethod
    def get_populares(cls, limit=5):
        return cls.get_published().order_by('-views')[:limit]


class PostImagem(models.Model):
    """Imagens adicionais do post (galeria)"""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='imagens')
    imagem = models.ImageField('Imagem', upload_to='blog/posts/gallery/%Y/%m/')
    legenda = models.CharField('Legenda', max_length=200, blank=True)
    ordem = models.IntegerField('Ordem', default=0)

    class Meta:
        verbose_name = 'Imagem do Post'
        verbose_name_plural = 'Imagens do Post'
        ordering = ['ordem']

    def __str__(self):
        return f"Imagem {self.ordem} - {self.post.titulo}"


class Comentario(models.Model):
    """Comentários dos posts (opcional)"""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comentarios')
    nome = models.CharField('Nome', max_length=100)
    email = models.EmailField('E-mail')
    conteudo = models.TextField('Comentário')
    publicado = models.BooleanField('Publicado', default=False)
    created_at = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Comentário'
        verbose_name_plural = 'Comentários'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.nome} - {self.post.titulo[:30]}"