from django import forms
from django.contrib.auth.forms import UserCreationForm
from projetos_institucionais.models import Usuario, Endereco
from validate_docbr import CPF
import re

class PerfilUsuarioForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'email', 'telefone', 'titulacao', 'centro_lotacao', 'curso']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'
        
        self.fields['titulacao'].empty_label = "Selecione sua titulação"
        self.fields['centro_lotacao'].empty_label = "Selecione seu centro de lotação"

        self.fields['first_name'].label = "Primeiro Nome"
        self.fields['last_name'].label = "Sobrenome"
        self.fields['email'].label = "E-mail"
        self.fields['telefone'].label = "Telefone"
        self.fields['titulacao'].label = "Titulação"
        self.fields['centro_lotacao'].label = "Centro de Lotação"


class EnderecoForm(forms.ModelForm):
    class Meta:
        model = Endereco
        fields = ['rua', 'numero', 'complemento', 'bairro', 'cidade', 'estado', 'cep']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'


class RegistroUsuarioForm(forms.ModelForm):
    perfil = forms.ChoiceField(
        label="Registrar-se como",
        choices=[('', 'Selecione uma opção')] + list(Usuario.PERFIL_CHOICES),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Digite sua senha'}),
    )
    password2 = forms.CharField(
        label="Confirme sua Senha",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirme sua senha'}),
    )

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ['cpf', 'first_name', 'last_name', 'email', 'perfil']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = self.fields['perfil'].choices

        self.fields['first_name'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Digite seu nome'})
        self.fields['last_name'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Digite seu sobrenome'})
        self.fields['cpf'].widget.attrs.update({'class': 'form-control', 'placeholder': '000.000.000-00'})
        self.fields['email'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Digite seu email'})
        self.fields['perfil'].choices = [choice for choice in choices if choice[0] != 'gestor']

    # Verificador para ver se as senhas são iguais
    def clean_password2(self):
        cd = self.cleaned_data
        if cd['password'] != cd['password2']:
            raise forms.ValidationError('As senhas não conferem.')
        return cd['password2']
    
    def clean_cpf(self):
        cpf = self.cleaned_data.get('cpf')
        if cpf:
            cpf_numeros = re.sub(r'[^0-9]', '', cpf)
            cpf_validator = CPF()
            if not cpf_validator.validate(cpf_numeros):
                raise forms.ValidationError("CPF inválido. Por favor, verifique o número digitado.")
            return cpf_numeros
        return cpf

    def save(self, commit=True):
        user = super().save(commit=False)

        cpf_limpo = self.cleaned_data['cpf']
        user.username = cpf_limpo
        user.cpf = cpf_limpo

        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class UsuarioEditForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = [
            'first_name', 'last_name', 'email', 'cpf', 'perfil', 'status'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].disabled = True
        self.fields['last_name'].disabled = True
        self.fields['cpf'].disabled = True
        self.fields['email'].disabled = True
