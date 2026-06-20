from django.contrib import sitemaps
from django.urls import reverse

class Sitemap(sitemaps.Sitemap):
    priority = 0.8
    changefreq = "never"

    def items(self):
        return [
            "pagina_vendas",
            "robots_txt",
            "accounts:login",
        ]

    def location(self, item):
        return reverse(item)