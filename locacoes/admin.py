from django.contrib import admin
from .models import ItemLocacao, Locacao
# Register your models here.

admin.site.register(Locacao)
admin.site.register(ItemLocacao)