from django import forms
from django.forms import inlineformset_factory
from .models import *

class Etapa1_TipoFinanciamentoForm(forms.Form):
    title = "Tipo de Financiamento"
    FINANCIAMENTO_CHOICES = (
        (False, 'Não, o projeto não possui financiamento externo'),
        (True, 'Sim, o projeto possui financiamento externo'),
    )
    possui_financiamento = forms.ChoiceField(
        choices=FINANCIAMENTO_CHOICES,
        widget=forms.RadioSelect,
        label="O projeto possui financiamento externo?"
    )

class Etapa2_InfoGeraisForm(forms.ModelForm):    
    title = "Informações Gerais"
    class Meta:
        model = Projeto
        fields = [
            'titulo', 'data_inicio', 'data_fim', 'agencia_financiadora', 'valor_fomento', 'centro_lotacao', 'curso', 'eh_docente', 'eh_pesquisador', 'eh_pesquisador_visitante', 'participa_pos_graduacao', 'programa_pos', 'grupos_pesquisa', 'etica_obrigatoria', 'tipo_etica',
        ]
        widgets = {
            'data_inicio': forms.DateInput(attrs={'type': 'date'}),
            'data_fim': forms.DateInput(attrs={'type': 'date'}),
            'eh_docente': forms.RadioSelect(choices=[(True, 'Sim'), (False, 'Não')]),
            'eh_pesquisador': forms.RadioSelect(choices=[(True, 'Sim'), (False, 'Não')]),
            'eh_pesquisador_visitante': forms.RadioSelect(choices=[(True, 'Sim'), (False, 'Não')]),
            'participa_pos_graduacao': forms.RadioSelect(choices=[(True, 'Sim'), (False, 'Não')]),
            'etica_obrigatoria': forms.RadioSelect(choices=[(True, 'Sim'), (False, 'Não')]),
            'grupos_pesquisa': forms.CheckboxSelectMultiple,
        }
        labels = {
            'etica_obrigatoria': "Envolve aspectos éticos?",
            'grupos_pesquisa': "Participa de Grupo de Pesquisa? Se sim, quais?",
            'eh_docente': "É docente?",
            'eh_pesquisador': "É pesquisador?",
            'eh_pesquisador_visitante': "É pesquisador visitante?",
        }
    
    def clean(self):
        cleaned_data = super().clean()
        data_inicio = cleaned_data.get("data_inicio")
        data_fim = cleaned_data.get("data_fim")
        if data_inicio and data_fim and data_fim < data_inicio:
            raise forms.ValidationError("A data de fim não pode ser anterior à data de início.")
        return cleaned_data
    
class Etapa3_DetalhesProjetoForm(forms.ModelForm):
    title = "Detalhes do Projeto"
    class Meta:
        model = Projeto
        fields = [
            'resumo', 'palavras_chave', 'introducao', 'objetivos', 'metodologia', 'resultados', 'parcerias', 'referencias',
        ]
        widgets = {
            'resumo': forms.Textarea(attrs={'rows': 4, 'maxlength': 1500}),
            'palavras_chave': forms.TextInput(attrs={'placeholder': 'Separe por vírgulas'}),
            'introducao': forms.Textarea(attrs={'rows': 6}),
            'objetivos': forms.Textarea(attrs={'rows': 6}),
            'metodologia': forms.Textarea(attrs={'rows': 6}),
            'resultados': forms.Textarea(attrs={'rows': 6}),
            'parcerias': forms.Textarea(attrs={'rows': 3}),
            'referencias': forms.Textarea(attrs={'rows': 4}),
        }

# Etapa 4
class EquipeProjetoForm(forms.ModelForm):
    title = "Equipe do Projeto"
    class Meta:
        model = EquipeProjeto
        fields = [
            'membro', 'carga_horaria_semanal', 'carga_horaria_total'
        ]
        widgets = {
            'membro': forms.Select(attrs={'required': False}),
            'carga_horaria_semanal': forms.NumberInput(attrs={'required': False}),
            'carga_horaria_total': forms.NumberInput(attrs={'required': False}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['membro'].queryset = Usuario.objects.filter(perfil='aluno').order_by('first_name')
        self.fields['membro'].required = False
        self.fields['carga_horaria_semanal'].required = False
        self.fields['carga_horaria_total'].required = False

EquipeProjetoFormSet = inlineformset_factory(
    Projeto,
    EquipeProjeto,
    form=EquipeProjetoForm,
    extra=1,
    can_delete=True,
    min_num=0,
)


class Etapa5_ODSForm(forms.ModelForm):
    title = "Vínculo com ODS"

    ods = forms.ModelMultipleChoiceField(
        queryset=ODS.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label="Selecione um ou mais Objetivos de Desenvolvimento Sustentável (ODS)",
        required=False
    )

    class Meta:
        model = Projeto
        fields = ['ods']


class Etapa6_RevisaoForm(forms.Form):
    title = "Revisão e Submissão"
    pass


class AnexoComprovanteForm(forms.ModelForm):
    class Meta:
        model = Anexo
        fields = ['arquivo', 'descricao']
        labels = {
            'arquivo': 'Selecione o arquivo do comprovante',
            'descricao': 'Descrição (opcional)',
        }

class UsuarioAlunoEditForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'telefone']

class EnderecoForm(forms.ModelForm):
    class Meta:
        model = Endereco
        exclude = ['id']