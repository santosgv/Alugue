from django import forms
from .models import TenantCompany, Assinatura, SubscriptionPlan


class TenantCompanyForm(forms.ModelForm):
    class Meta:
        model  = TenantCompany
        fields = ['nome', 'cnpj', 'email', 'telefone']
        widgets = {
            'nome':     forms.TextInput(attrs={'class': 'form-control'}),
            'cnpj':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00.000.000/0001-00'}),
            'email':    forms.EmailInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control'}),
        }


class MudarPlanoForm(forms.Form):
    plano = forms.ModelChoiceField(
        queryset=SubscriptionPlan.objects.filter(ativo=True),
        widget=forms.HiddenInput(),
    )
    ciclo = forms.ChoiceField(
        choices=Assinatura.CICLO_CHOICES,
        widget=forms.HiddenInput(),
    )


class CancelarAssinaturaForm(forms.Form):
    motivo = forms.CharField(
        label='Motivo do cancelamento',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                     'placeholder': 'Conte-nos o motivo para podermos melhorar...'}),
        required=False,
    )
    confirmacao = forms.CharField(
        label='Digite CANCELAR para confirmar',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'CANCELAR'}),
    )

    def clean_confirmacao(self):
        val = self.cleaned_data.get('confirmacao', '')
        if val.strip().upper() != 'CANCELAR':
            raise forms.ValidationError('Digite exatamente "CANCELAR" para confirmar.')
        return val
