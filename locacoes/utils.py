from io import BytesIO

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import get_template

from xhtml2pdf import pisa

from .models import Locacao


def gerar_pdf_locacao(request, pk):

    locacao = get_object_or_404(
        Locacao.objects.select_related(
            "cliente",
            "criado_por"
        ).prefetch_related(
            "itens__produto"
        ),
        pk=pk
    )

    template = get_template(
        "locacoes/pdf_locacao.html"
    )

    html = template.render({
        "locacao": locacao
    })

    resultado = BytesIO()

    pisa_status = pisa.CreatePDF(
        html,
        dest=resultado,
        encoding="utf-8"
    )

    if pisa_status.err:
        return HttpResponse(
            "Erro ao gerar PDF",
            status=500
        )

    response = HttpResponse(
        resultado.getvalue(),
        content_type="application/pdf"
    )

    response["Content-Disposition"] = (
        f'attachment; filename="locacao_{locacao.pk}.pdf"'
    )

    return response