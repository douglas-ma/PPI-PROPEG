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
            'membro', 'funcao', 'carga_horaria_semanal', 'carga_horaria_total'
        ]
        widgets = {
            'membro': forms.Select(attrs={'required': False}),
            'funcao': forms.Select(attrs={'required': False}),
            'carga_horaria_semanal': forms.NumberInput(attrs={'required': False}),
            'carga_horaria_total': forms.NumberInput(attrs={'required': False}),
        }
    
    def __init__(self, *args, **kwargs):
        coordenador_atual = kwargs.pop('coordenador', None)
        self.is_draft = kwargs.pop('is_draft', False)

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
        
        if self.is_draft:
            for field in self.fields.values():
                field.required = False

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
    cnpq_area = forms.ChoiceField(
        choices=Usuario.CNPQ_AREA_CHOICES,
        required=False,
        label='Grande Área CNPq',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    participa_pos_graduacao = forms.TypedChoiceField(
        choices=(('False', 'Não'), ('True', 'Sim')),
        widget=forms.RadioSelect,
        label="Vinculado a Programa de Pós-Graduação?",
        coerce=lambda x: x == 'True',
        initial=False,
        required=False,
    )
    programa_pos_vinculo = forms.ChoiceField(
        choices=Usuario.PROGRAMA_POS_CHOICES,
        required=False,
        label='Programa de Pós-Graduação',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = Usuario
        fields = [
            'first_name', 'last_name', 'email', 'telefone',
            'rg', 'data_nascimento', 'siape',
            'lattes', 'cnpq_area',
            'titulacao', 'regime_trabalho',
            'centro_lotacao',
            'participa_pos_graduacao', 'programa_pos_vinculo',
        ]
        widgets = {
            'data_nascimento': forms.DateInput(attrs={'type': 'date'}),
            'lattes': forms.URLInput(attrs={'placeholder': 'https://lattes.cnpq.br/...'}),
        }
        labels = {
            'first_name':      'Nome',
            'last_name':       'Sobrenome',
            'titulacao':       'Titulação Máxima',
            'regime_trabalho': 'Regime de Trabalho (Ex: 20h, 40h, DE)',
            'rg':              'RG',
            'data_nascimento': 'Data de Nascimento',
            'siape':           'SIAPE',
            'lattes':          'Link Currículo Lattes',
            'centro_lotacao':  'Centro de Lotação',
        }


class GestorProfileForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = [
            'first_name', 'last_name', 'email', 'telefone',
            'rg', 'data_nascimento',
        ]
        widgets = {
            'data_nascimento': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'first_name':      'Nome',
            'last_name':       'Sobrenome',
            'rg':              'RG',
            'data_nascimento': 'Data de Nascimento',
        }


class AlunoProfileForm(forms.ModelForm):
    participa_pos_graduacao = forms.TypedChoiceField(
        choices=(('False', 'Não'), ('True', 'Sim')),
        widget=forms.RadioSelect,
        label="Vinculado a Programa de Pós-Graduação?",
        coerce=lambda x: x == 'True',
        initial=False,
        required=False,
    )
    programa_pos_vinculo = forms.ChoiceField(
        choices=Usuario.PROGRAMA_POS_CHOICES,
        required=False,
        label='Programa de Pós-Graduação',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = Usuario
        fields = [
            'first_name', 'last_name', 'email', 'telefone',
            'rg', 'data_nascimento', 'matricula', 'curso',
            'participa_pos_graduacao', 'programa_pos_vinculo',
        ]
        widgets = {
            'data_nascimento': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'first_name':      'Nome',
            'last_name':       'Sobrenome',
            'curso':           'Curso de Graduação',
            'rg':              'RG',
            'data_nascimento': 'Data de Nascimento',
            'matricula':       'Nº de Matrícula',
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
        ('final',   'Relatório Final'),
    )

    tipo_relatorio = forms.ChoiceField(
        choices=TIPO_CHOICES,
        label="Tipo de Relatório",
        widget=forms.RadioSelect,
        required=True,
    )

    # ── Campos comuns ──────────────────────────────────────────────────────
    periodo_inicio = forms.DateField(
        label="Início do Período Relatado",
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True,
    )
    periodo_fim = forms.DateField(
        label="Fim do Período Relatado",
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True,
    )
    objetivo_geral = forms.CharField(
        label="Objetivo Geral do Projeto",
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        help_text="Pré-preenchido a partir do projeto. Atualize se necessário.",
    )
    objetivos_especificos = forms.CharField(
        label="Objetivos Específicos",
        widget=forms.Textarea(attrs={'rows': 4}),
        required=False,
        help_text="Pré-preenchido a partir do projeto. Atualize se necessário.",
    )
    atividades_realizadas = forms.CharField(
        label="Atividades Realizadas no Período",
        widget=forms.Textarea(attrs={'rows': 6}),
        required=True,
        help_text="Descreva as principais ações executadas durante o período.",
    )
    resultados_alcancados = forms.CharField(
        label="Resultados Alcançados",
        widget=forms.Textarea(attrs={'rows': 6}),
        required=True,
        help_text="Detalhe os resultados e produtos gerados até o momento.",
    )
    dificuldades = forms.CharField(
        label="Dificuldades Encontradas",
        widget=forms.Textarea(attrs={'rows': 4}),
        required=False,
        help_text="Descreva obstáculos enfrentados durante a execução, se houver.",
    )

    # ── Exclusivo Parcial ──────────────────────────────────────────────────
    proximas_etapas = forms.CharField(
        label="Próximas Etapas Planejadas",
        widget=forms.Textarea(attrs={'rows': 4}),
        required=False,
        help_text="Descreva o que será realizado nos próximos meses do projeto.",
    )

    # ── Exclusivo Final ────────────────────────────────────────────────────
    metodologia_utilizada = forms.CharField(
        label="Metodologia Utilizada",
        widget=forms.Textarea(attrs={'rows': 5}),
        required=False,
        help_text="Descreva a metodologia efetivamente utilizada na execução do projeto.",
    )
    impactos_observados = forms.CharField(
        label="Impactos e Contribuições Observadas",
        widget=forms.Textarea(attrs={'rows': 5}),
        required=False,
        help_text="Descreva os impactos científicos, sociais ou institucionais gerados.",
    )
    produtos_gerados = forms.CharField(
        label="Produtos Gerados",
        widget=forms.Textarea(attrs={'rows': 4}),
        required=False,
        help_text="Liste publicações, eventos, softwares, patentes, relatórios ou outros produtos.",
    )
    consideracoes_finais = forms.CharField(
        label="Considerações Finais",
        widget=forms.Textarea(attrs={'rows': 5}),
        required=False,
        help_text="Síntese geral do projeto, avaliação dos objetivos atingidos e aprendizados.",
    )

    # ── Evidências (ambos os tipos) ────────────────────────────────────────
    evidencias = MultipleFileField(
        label="Arquivos de Evidências",
        required=False,
        help_text="Anexe documentos, imagens ou PDFs como evidências. Selecione múltiplos arquivos de uma vez.",
    )


class EditalForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        self.is_draft = kwargs.pop('is_draft', False)
        super().__init__(*args, **kwargs)
        if self.is_draft:
            for field in self.fields.values():
                field.required = False
        # documento_principal nunca é obrigatório no form — gerenciado pela view
        self.fields['documento_principal'].required = False

    class Meta:
        model = Edital
        fields = [
            'tipo', 'numero', 'ano', 'titulo', 'descricao',
            'data_inicio_submissoes', 'data_fim_submissoes',
            'documento_principal'
            # 'status' removido — gerenciado pelos botões publicar/rascunho/toggle
        ]
        widgets = {
            'data_inicio_submissoes': forms.DateInput(attrs={'type': 'date'}),
            'data_fim_submissoes': forms.DateInput(attrs={'type': 'date'}),
            'descricao': forms.Textarea(attrs={'rows': 4}),
        }
        labels = {
            'titulo': 'Título Descritivo do Edital',
        }

AnexoEditalFormSet = inlineformset_factory(
    Edital,
    AnexoEdital,
    fields=('descricao', 'arquivo'),
    extra=0,          # começa sem slots vazios — JS adiciona dinamicamente
    can_delete=True,
    labels={
        'descricao': 'Descrição do Anexo',
        'arquivo': 'Arquivo do Anexo',
    }
)

# ─────────────────────────────────────────────────────────────────────────────
# Formulários do novo fluxo de criação por etapas (substitui o Wizard)
# ─────────────────────────────────────────────────────────────────────────────

_BOOL_CHOICES = ((True, 'Sim'), (False, 'Não'))


class ProjetoEtapa1Form(forms.ModelForm):
    """Etapa 1 – Tipo de financiamento e Informações Gerais."""

    possui_financiamento = forms.TypedChoiceField(
        choices=(
            (False, 'Não – o projeto não possui financiamento externo'),
            (True,  'Sim – o projeto possui financiamento externo'),
        ),
        widget=forms.RadioSelect,
        label="O projeto possui financiamento externo?",
        coerce=lambda x: x == 'True',
        initial=False,
    )
    agencia_financiadora_nome = forms.CharField(
        label="Agência Financiadora",
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Ex: CAPES, CNPq, FAPAC…'}),
    )
    programa_pos_nome = forms.CharField(
        label="Programa de Pós-Graduação",
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Nome do programa'}),
    )
    tipo_etica_nome = forms.CharField(
        label="Tipo de Comitê de Ética",
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Ex: CEP, CEUA'}),
    )
    grupos_pesquisa_str = forms.CharField(
        label="Grupos de Pesquisa",
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Separe os nomes por vírgula'}),
        help_text="Separe os nomes dos grupos por vírgula.",
    )
    eh_docente = forms.TypedChoiceField(
        choices=_BOOL_CHOICES, widget=forms.RadioSelect,
        label="É docente?", coerce=lambda x: x == 'True', initial=False,
    )
    eh_pesquisador = forms.TypedChoiceField(
        choices=_BOOL_CHOICES, widget=forms.RadioSelect,
        label="É pesquisador?", coerce=lambda x: x == 'True', initial=False,
    )
    eh_pesquisador_visitante = forms.TypedChoiceField(
        choices=_BOOL_CHOICES, widget=forms.RadioSelect,
        label="É pesquisador visitante?", coerce=lambda x: x == 'True', initial=False,
    )
    participa_pos_graduacao = forms.TypedChoiceField(
        choices=_BOOL_CHOICES, widget=forms.RadioSelect,
        label="Participa de Programa de Pós-Graduação?", coerce=lambda x: x == 'True', initial=False,
    )
    etica_obrigatoria = forms.TypedChoiceField(
        choices=_BOOL_CHOICES, widget=forms.RadioSelect,
        label="Envolve aspectos éticos?", coerce=lambda x: x == 'True', initial=False,
    )
    comprovante_etica = forms.FileField(
        label="Comprovante de Aprovação do Comitê de Ética",
        required=False,
        help_text="Anexe o documento de aprovação do comitê (PDF).",
    )
    anexos_gerais = MultipleFileField(
        label="Anexos Adicionais",
        required=False,
        help_text="Selecione vários arquivos de uma vez (PDF, PNG, JPG).",
    )

    class Meta:
        model = Projeto
        fields = [
            'titulo', 'data_inicio', 'data_fim', 'edital',
            'centro_lotacao', 'curso', 'valor_fomento',
            'eh_docente', 'eh_pesquisador', 'eh_pesquisador_visitante',
            'participa_pos_graduacao', 'etica_obrigatoria', 'imagem_capa',
        ]
        widgets = {
            'data_inicio': forms.DateInput(attrs={'type': 'date'}),
            'data_fim':    forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        self.is_draft = kwargs.pop('is_draft', False)
        super().__init__(*args, **kwargs)

        # Queryset de editais calculado em runtime (evita bug de data fixa)
        self.fields['edital'].queryset = Edital.objects.filter(
            status='aberto',
            data_inicio_submissoes__lte=date.today(),
            data_fim_submissoes__gte=date.today(),
        )
        self.fields['edital'].empty_label = "Nenhum / Projeto sem vínculo com edital"
        self.fields['edital'].required = False

        # Pré-preenche campos de texto a partir das FKs do objeto salvo
        if self.instance and self.instance.pk:
            if self.instance.agencia_financiadora:
                self.fields['agencia_financiadora_nome'].initial = self.instance.agencia_financiadora.nome
                self.fields['possui_financiamento'].initial = True
            if self.instance.programa_pos:
                self.fields['programa_pos_nome'].initial = self.instance.programa_pos.nome
            if self.instance.tipo_etica:
                self.fields['tipo_etica_nome'].initial = self.instance.tipo_etica.nome
            grupos = self.instance.grupos_pesquisa.all()
            if grupos.exists():
                self.fields['grupos_pesquisa_str'].initial = ', '.join(g.nome for g in grupos)

        # No modo rascunho, nenhum campo é obrigatório
        if self.is_draft:
            for field in self.fields.values():
                field.required = False

    def clean(self):
        cleaned_data = super().clean()
        data_inicio = cleaned_data.get('data_inicio')
        data_fim    = cleaned_data.get('data_fim')
        if data_inicio and data_fim and data_fim < data_inicio:
            self.add_error('data_fim', "A data de fim não pode ser anterior à data de início.")
        return cleaned_data

    def save(self, commit=True):
        projeto = super().save(commit=False)

        # Agência Financiadora
        nome_agencia = self.cleaned_data.get('agencia_financiadora_nome', '').strip()
        if nome_agencia:
            agencia, _ = AgenciaFinanciadora.objects.get_or_create(nome=nome_agencia)
            projeto.agencia_financiadora = agencia
        else:
            projeto.agencia_financiadora = None

        # Programa de Pós-Graduação
        centro = self.cleaned_data.get('centro_lotacao')
        nome_programa = self.cleaned_data.get('programa_pos_nome', '').strip()
        if nome_programa and centro:
            programa, _ = ProgramaPos.objects.get_or_create(
                nome=nome_programa, defaults={'centro_lotacao': centro}
            )
            projeto.programa_pos = programa
        else:
            projeto.programa_pos = None

        # Tipo Ético
        nome_etica = self.cleaned_data.get('tipo_etica_nome', '').strip()
        if nome_etica:
            etica, _ = TipoEtico.objects.get_or_create(nome=nome_etica)
            projeto.tipo_etica = etica
        else:
            projeto.tipo_etica = None

        if commit:
            projeto.save()
            # Grupos de Pesquisa (M2M – precisa do PK já salvo)
            grupos_str = self.cleaned_data.get('grupos_pesquisa_str', '')
            lista_grupos = []
            if grupos_str:
                for nome in [n.strip() for n in grupos_str.split(',') if n.strip()]:
                    grupo, _ = GrupoPesquisa.objects.get_or_create(nome=nome)
                    lista_grupos.append(grupo)
            projeto.grupos_pesquisa.set(lista_grupos)

        return projeto


class ProjetoEtapa2Form(forms.ModelForm):
    """Etapa 2 – Detalhes textuais do projeto."""

    class Meta:
        model = Projeto
        fields = [
            'resumo', 'palavras_chave', 'introducao',
            'objetivo_geral', 'objetivos_especificos',
            'metodologia', 'resultados',
            'parcerias', 'referencias',
        ]
        widgets = {
            'resumo':               forms.Textarea(attrs={'rows': 4, 'maxlength': 1500}),
            'palavras_chave':       forms.TextInput(attrs={'placeholder': 'Separe por vírgulas'}),
            'introducao':           forms.Textarea(attrs={'rows': 6}),
            'objetivo_geral':       forms.Textarea(attrs={'rows': 4}),
            'objetivos_especificos':forms.Textarea(attrs={'rows': 6}),
            'metodologia':          forms.Textarea(attrs={'rows': 6}),
            'resultados':           forms.Textarea(attrs={'rows': 6}),
            'parcerias':            forms.Textarea(attrs={'rows': 3}),
            'referencias':          forms.Textarea(attrs={'rows': 4}),
        }
        labels = {
            'objetivo_geral':        'Objetivo Geral',
            'objetivos_especificos': 'Objetivos Específicos',
        }

    def __init__(self, *args, **kwargs):
        self.is_draft = kwargs.pop('is_draft', False)
        super().__init__(*args, **kwargs)
        if self.is_draft:
            for field in self.fields.values():
                field.required = False


class ProjetoEtapa2FinanciadoForm(forms.ModelForm):
    """
    Etapa 2 simplificada para projetos com financiamento externo.
    Exige apenas resumo, palavras-chave e dois uploads obrigatórios:
    o documento do projeto aprovado e o comprovante emitido pela agência.
    """
    documento_projeto = forms.FileField(
        label="Documento do Projeto Aprovado",
        required=True,
        help_text="Anexe o projeto completo aprovado pela agência financiadora (PDF).",
        widget=forms.FileInput(attrs={'accept': '.pdf'}),
    )
    comprovante_agencia = forms.FileField(
        label="Comprovante de Aprovação da Agência",
        required=True,
        help_text="Anexe o documento emitido pela agência confirmando a aprovação do financiamento (PDF).",
        widget=forms.FileInput(attrs={'accept': '.pdf'}),
    )

    class Meta:
        model = Projeto
        fields = ['resumo', 'palavras_chave']
        widgets = {
            'resumo':       forms.Textarea(attrs={'rows': 5, 'maxlength': 1500}),
            'palavras_chave': forms.TextInput(attrs={'placeholder': 'Separe por vírgulas'}),
        }

    def __init__(self, *args, **kwargs):
        self.is_draft = kwargs.pop('is_draft', False)
        super().__init__(*args, **kwargs)
        if self.is_draft:
            for field in self.fields.values():
                field.required = False


class ProjetoEtapa4Form(forms.ModelForm):
    """Etapa 4 – Vínculo com ODS."""

    ods = forms.ModelMultipleChoiceField(
        queryset=ODS.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label="Objetivos de Desenvolvimento Sustentável",
        required=False,
    )

    class Meta:
        model = Projeto
        fields = ['ods']

    def __init__(self, *args, **kwargs):
        self.is_draft = kwargs.pop('is_draft', False)
        super().__init__(*args, **kwargs)
        if self.is_draft:
            self.fields['ods'].required = False