from django import forms
from django.forms import inlineformset_factory
from .models import Locacao, ItemLocacao
from produtos.models import Produto


class LocacaoForm(forms.ModelForm):
    class Meta:
        model = Locacao
        fields = ['cliente', 'data_inicio', 'data_fim_prevista', 'observacoes']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select select2'}),
            'data_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_fim_prevista': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        cleaned = super().clean()
        data_inicio = cleaned.get('data_inicio')
        data_fim = cleaned.get('data_fim_prevista')
        if data_inicio and data_fim:
            if data_fim < data_inicio:
                raise forms.ValidationError("A data fim não pode ser anterior à data de início.")
        return cleaned


class ItemLocacaoForm(forms.ModelForm):
    class Meta:
        model = ItemLocacao
        fields = ['produto', 'quantidade', 'valor_unitario']
        widgets = {
            'produto': forms.Select(attrs={'class': 'form-select produto-select'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'valor_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


ItemLocacaoFormSet = inlineformset_factory(
    Locacao,
    ItemLocacao,
    form=ItemLocacaoForm,
    extra=0,
    min_num=0,
    validate_min=True,
    can_delete=True,
)