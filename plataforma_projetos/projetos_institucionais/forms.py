from django import forms
from .models import Usuario, GrupoPesquisa, Titulacao, Projeto, ODS, Documento, Ata, Relatorio

class UsuarioForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = '__all__'


class GrupoPesquisaForm(forms.ModelForm):
    class Meta:
        model = GrupoPesquisa
        fields = '__all__'


class TitulacaoForm(forms.ModelForm):
    class Meta:
        model = Titulacao
        fields = '__all__'


class ProjetoForm(forms.ModelForm):
    class Meta:
        model = Projeto
        fields = '__all__'


class ODSForm(forms.ModelForm):
    class Meta:
        model = ODS
        fields = '__all__'


class DocumentoForm(forms.ModelForm):
    class Meta:
        model = Documento
        fields = '__all__'


class AtaForm(forms.ModelForm):
    class Meta:
        model = Ata
        fields = '__all__'


class RelatorioForm(forms.ModelForm):
    class Meta:
        model = Relatorio
        fields = '__all__'
