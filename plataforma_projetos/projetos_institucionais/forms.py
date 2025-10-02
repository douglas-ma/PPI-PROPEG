from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django_select2.forms import Select2Widget, Select2MultipleWidget
from django.db.models import Q
from .models import *
from datetime import date
import os

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


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class Etapa2_InfoGeraisForm(forms.ModelForm):    
    title = "Informações Gerais"

    edital = forms.ModelChoiceField(
        queryset=Edital.objects.filter(
            status='aberto',
            data_inicio_submissoes__lte=date.today(),
            data_fim_submissoes__gte=date.today(),
        ),
        required=False,
        label="Vincular a um Edital (Opcional)",
        empty_label="Nenhum / Projeto sem vínculo com edital",
        help_text="Selecione um edital aberto para vincular seu projeto."
    )

    titulo = forms.CharField(label="Título do Projeto", max_length=255)
    data_inicio = forms.DateField(
        label="Data de Início",
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    data_fim = forms.DateField(
        label="Data de Fim",
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    agencia_financiadora = forms.CharField(
        label="Agência Financiadora", 
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Digite o nome da agência'})
    )
    valor_fomento = forms.DecimalField(
        label="Valor do Fomento",
        required=False,
        max_digits=10,
        decimal_places=2
    )
    centro_lotacao = forms.ModelChoiceField(
        label="Centro de Lotação",
        queryset=CentroLotacao.objects.all(),
        required=True
    )
    curso = forms.ModelChoiceField(
        label="Curso de Graduação",
        queryset=CursoGraduacao.objects.all(),
        required=False
    )
    BOOL_CHOICES = ((True, 'Sim'), (False, 'Não'))
    eh_docente = forms.TypedChoiceField(
        choices=BOOL_CHOICES, widget=forms.RadioSelect, label="É docente?*", initial=False, coerce=lambda x: x == 'True'
    )
    eh_pesquisador = forms.TypedChoiceField(
        choices=BOOL_CHOICES, widget=forms.RadioSelect, label="É pesquisador?*", initial=False, coerce=lambda x: x == 'True'
    )
    eh_pesquisador_visitante = forms.TypedChoiceField(
        choices=BOOL_CHOICES, widget=forms.RadioSelect, label="É pesquisador visitante?*", initial=False, coerce=lambda x: x == 'True'
    )
    participa_pos_graduacao = forms.TypedChoiceField(
        choices=BOOL_CHOICES, widget=forms.RadioSelect, label="Participa de Programa de Pós-Graduação?*", initial=False, coerce=lambda x: x == 'True'
    )
    programa_pos = forms.CharField(
        label="Programa de Pós-Graduação", 
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Digite o nome do programa'})
    )
    grupos_pesquisa = forms.CharField(
        label="Participa de Grupos de Pesquisa? Se sim, quais?", 
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Separe os nomes por vírgula'})
    )
    etica_obrigatoria = forms.TypedChoiceField(
        choices=BOOL_CHOICES, widget=forms.RadioSelect, label="Envolve aspectos éticos?*", initial=False, coerce=lambda x: x == 'True'
    )
    tipo_etica = forms.CharField(
        label="Tipo Ético", 
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Digite o tipo de comitê de ética'})
    )
    imagem_capa = forms.ImageField(
        label="Imagem de Capa do Projeto (Opcional)",
        required=False,
        help_text="Esta imagem será exibida nos cards do projeto. Use uma imagem representativa."
    )
    anexos_gerais = MultipleFileField(
        label="Anexos Adicionais",
        required=False,
        help_text="Anexe arquivos .pdf ou imagens (.jpg, .jpeg, .png). Segure 'Ctrl' (ou 'Cmd') para selecionar vários."
    )

    class Meta:
        model = Projeto
        fields = []
 
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
        coordenador_atual = kwargs.pop('coordenador', None)

        super().__init__(*args, **kwargs)

        query_membros = Usuario.objects.filter(
            Q(perfil='aluno') | Q(perfil='coordenador')
        ).order_by('first_name')
        
        if coordenador_atual:
            query_membros = query_membros.exclude(pk=coordenador_atual.pk)
        
        self.fields['membro'].queryset = query_membros
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


class CoordenadorProfileForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = [
            'first_name', 'last_name', 'email', 'telefone', 'titulacao', 'centro_lotacao', 'regime_trabalho'
        ]
        labels = {
            'first_name': 'Nome',
            'last_name': 'Sobrenome',
            'titulacao': 'Titulação Máxima',
            'centro_lotacao': 'Centro de Lotação',
            'regime_trabalho': 'Regime de Trabalho (Ex: 20h, 40h, DE)',
        }


class AlunoProfileForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = [
            'first_name', 'last_name', 'email', 'telefone', 'curso'
        ]
        labels = {
            'first_name': 'Nome',
            'last_name': 'Sobrenome',
            'curso': 'Curso de Graduação',
        }


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


class AnexoForm(forms.ModelForm):
    class Meta:
        model = Anexo
        fields = ['tipo_anexo', 'arquivo', 'descricao']
        labels = {
            'tipo_anexo': 'Tipo de Anexo',
            'arquivo': 'Selecione o arquivo',
            'descricao': 'Descrição (opcional)',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tipos_excluidos = ['comprovante_aprovacao', 'relatorio_submissao']
        self.fields['tipo_anexo'].choices = [
            (k, v) for k, v in self.fields['tipo_anexo'].choices if k not in tipos_excluidos
        ]

class RelatorioForm(forms.Form):
    TIPO_CHOICES = (
        ('parcial', 'Relatório Parcial'),
        ('final', 'Relatório Final'),
    )
    
    tipo_relatorio = forms.ChoiceField(
        choices=TIPO_CHOICES,
        label="Tipo de Relatório",
        widget=forms.RadioSelect,
        required=True
    )
    resumo_atividades = forms.CharField(
        label="Resumo das Atividades Realizadas no Período",
        widget=forms.Textarea(attrs={'rows': 6}),
        required=True,
        help_text="Descreva de forma sucinta as principais ações e o progresso do projeto."
    )
    resultados_alcancados = forms.CharField(
        label="Resultados Alcançados",
        widget=forms.Textarea(attrs={'rows': 6}),
        required=True,
        help_text="Detalhe os resultados e/ou produtos gerados até o momento."
    )
    dificuldades = forms.CharField(
        label="Dificuldades Encontradas (Opcional)",
        widget=forms.Textarea(attrs={'rows': 4}),
        required=False
    )
    proximos_passos = forms.CharField(
        label="Próximos Passos e Planejamento Futuro",
        widget=forms.Textarea(attrs={'rows': 4}),
        required=True,
        help_text="Para relatórios parciais, descreva as próximas etapas. Para relatórios finais, descreva os desdobramentos."
    )


class EditalForm(forms.ModelForm):
    class Meta:
        model = Edital
        fields = [
            'titulo', 'descricao', 'data_inicio_submissoes', 
            'data_fim_submissoes', 'status', 'documento_principal'
        ]
        widgets = {
            'data_inicio_submissoes': forms.DateInput(attrs={'type': 'date'}),
            'data_fim_submissoes': forms.DateInput(attrs={'type': 'date'}),
            'descricao': forms.Textarea(attrs={'rows': 4}),
        }
    
AnexoEditalFormSet = inlineformset_factory(
    Edital, 
    AnexoEdital,
    fields=('descricao', 'arquivo'),
    extra=1,
    can_delete=True,
    labels={
        'descricao': 'Descrição do Anexo',
        'arquivo': 'Arquivo do Anexo',
    }
)