from decimal import Decimal,InvalidOperation

from django import forms
from .models import Produto, CategoriaProduto


class CategoriaProdutoForm(forms.ModelForm):
    class Meta:
        model = CategoriaProduto
        fields = ['nome', 'descricao']

        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome da categoria'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Descrição da categoria'
            }),
        }



class ProdutoForm(forms.ModelForm):

    # Declara como CharField para receber a string formatada da máscara
    # sem que o DecimalField do Django tente validar antes
    valor_diario = forms.CharField(
        label='Valor Diário (R$)',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_valor_diario',
            'placeholder': '0,00',
        })
    )

    def clean_valor_diario(self):
        valor = self.cleaned_data.get('valor_diario', '')
        # Remove pontos de milhar e troca vírgula por ponto
        valor_limpo = str(valor).replace('.', '').replace(',', '.')
        try:
            resultado = Decimal(valor_limpo)
        except (InvalidOperation, ValueError):
            raise forms.ValidationError('Informe um valor válido. Ex: 150,00')

        if resultado <= 0:
            raise forms.ValidationError('O valor diário deve ser maior que zero.')

        return resultado

    class Meta:
        model = Produto
        fields = ['nome', 'categoria', 'codigo_interno', 'quantidade_total',
                  'quantidade_disponivel', 'valor_diario', 'descricao', 'foto', 'status']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'codigo_interno': forms.TextInput(attrs={'class': 'form-control'}),
            'quantidade_total': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'quantidade_disponivel': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'foto': forms.FileInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned = super().clean()
        qtd_total = cleaned.get('quantidade_total')
        qtd_disp = cleaned.get('quantidade_disponivel')
        if qtd_total is not None and qtd_disp is not None:
            if qtd_disp > qtd_total:
                self.add_error('quantidade_disponivel',
                               'Quantidade disponível não pode ser maior que a quantidade total.')
        return cleaned