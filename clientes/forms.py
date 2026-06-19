import re
from django import forms
from .models import Cliente


class ClienteForm(forms.ModelForm):
    def clean_cpf_cnpj(self):
        valor = self.cleaned_data.get('cpf_cnpj', '')
        # Remove tudo que não for letra ou número, mantém maiúsculo
        limpo = re.sub(r'[^a-zA-Z0-9]', '', valor).upper()

        if len(limpo) == 11:
            if not limpo.isdigit():
                raise forms.ValidationError('CPF deve conter apenas números.')
        elif len(limpo) == 14:
            # CNPJ alfanumérico: 12 primeiros podem ser letra/número,
            # os 2 últimos (dígitos verificadores) devem ser numéricos
            if not limpo[:12].isalnum() or not limpo[12:].isdigit():
                raise forms.ValidationError('CNPJ inválido. Os 2 últimos dígitos devem ser numéricos.')
        else:
            raise forms.ValidationError('Informe um CPF (11 dígitos) ou CNPJ (14 caracteres) válido.')

        return limpo  # salva sem formatação, só o valor limpo
    class Meta:
        model = Cliente
        fields = ['nome', 'cpf_cnpj', 'telefone', 'email', 'endereco', 'observacoes', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome completo',
            }),
            'cpf_cnpj': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '000.000.000-00 ou AA.AAA.AAA/AAAA-00',
                'id': 'id_cpf_cnpj',
                'maxlength': '18', 
            }),
            'telefone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '(00) 00000-0000',
                'id': 'id_telefone',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@exemplo.com',
            }),
            'endereco': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
            }),
            'observacoes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
            }),
            'ativo': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }