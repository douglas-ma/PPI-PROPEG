from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.forms import inlineformset_factory
from django.forms.models import BaseInlineFormSet
from django_select2.forms import Select2Widget, Select2MultipleWidget
from django.db.models import Q
from validate_docbr import CPF
from .models import *
from datetime import date
import os

from .document_extraction import DocumentoProjetoError, extrair_texto_pdf_digital


FORMATOS_DOCUMENTO = ('pdf', 'png', 'jpg', 'jpeg')
MIMES_DOCUMENTO = {
    'application/pdf',
    'image/png',
    'image/jpeg',
    'image/jpg',
}


def validar_pdf_ou_imagem(arquivo):
    """Aceita somente PDFs e imagens PNG/JPG, validando extensão e MIME."""
    extensao = os.path.splitext(arquivo.name)[1].lower().lstrip('.')
    content_type = getattr(arquivo, 'content_type', '')
    if extensao not in FORMATOS_DOCUMENTO or (content_type and content_type not in MIMES_DOCUMENTO):
        raise ValidationError('Envie um arquivo PDF ou uma imagem nos formatos PNG, JPG ou JPEG.')

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
        label="Centro Acadêmico",
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
    busca_membro = forms.CharField(required=False)

    class Meta:
        model = EquipeProjeto
        fields = [
            'origem_membro', 'membro', 'nome_membro_manual', 'cpf_manual',
            'funcao', 'carga_horaria_semanal', 'carga_horaria_total',
        ]
        widgets = {
            'membro': forms.Select(attrs={'required': False}),
            'nome_membro_manual': forms.TextInput(attrs={'required': False}),
            'cpf_manual': forms.TextInput(attrs={'required': False, 'inputmode': 'numeric'}),
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
        ).select_related('curso').order_by('first_name', 'last_name')
        
        if coordenador_atual:
            query_membros = query_membros.exclude(pk=coordenador_atual.pk)
        
        self.fields['membro'].queryset = query_membros
        if self.instance.pk and self.instance.membro_id:
            self.fields['busca_membro'].initial = self.instance.nome_exibicao
        for field in self.fields.values():
            field.required = False

    def clean_cpf_manual(self):
        cpf = ''.join(filter(str.isdigit, self.cleaned_data.get('cpf_manual', '')))
        if not cpf:
            return ''
        if len(cpf) != 11 or not CPF().validate(cpf):
            raise ValidationError('Informe um CPF válido.')
        if Usuario.objects.filter(cpf__in=(cpf, CPF().mask(cpf))).exists():
            raise ValidationError(
                'Este CPF já pertence a um usuário do sistema. Utilize a busca de usuários cadastrados.'
            )
        return cpf

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('DELETE'):
            return cleaned_data

        origem = cleaned_data.get('origem_membro') or EquipeProjeto.ORIGEM_SISTEMA
        membro = cleaned_data.get('membro')
        nome_manual = (cleaned_data.get('nome_membro_manual') or '').strip()
        cpf_manual = cleaned_data.get('cpf_manual') or ''
        busca_membro = (cleaned_data.get('busca_membro') or '').strip()
        carga_semanal = cleaned_data.get('carga_horaria_semanal')
        carga_total = cleaned_data.get('carga_horaria_total')

        possui_identificacao = bool(membro or nome_manual or cpf_manual or busca_membro)
        possui_carga = carga_semanal is not None or carga_total is not None
        linha_iniciada = possui_identificacao or possui_carga or origem == EquipeProjeto.ORIGEM_MANUAL

        if not linha_iniciada and not self.instance.pk:
            return cleaned_data

        if origem == EquipeProjeto.ORIGEM_SISTEMA:
            cleaned_data['nome_membro_manual'] = ''
            cleaned_data['cpf_manual'] = ''
            if not membro and (busca_membro or not self.is_draft):
                self.add_error('membro', 'Pesquise e selecione um usuário do sistema.')
        else:
            cleaned_data['membro'] = None
            cleaned_data['busca_membro'] = ''
            if not nome_manual and not self.is_draft:
                self.add_error('nome_membro_manual', 'Informe o nome do membro.')
            if not cpf_manual and not self.is_draft and 'cpf_manual' not in self.errors:
                self.add_error('cpf_manual', 'Informe o CPF do membro.')

        if linha_iniciada and not self.is_draft:
            if not cleaned_data.get('funcao'):
                self.add_error('funcao', 'Selecione a função do membro.')
            if carga_semanal is None:
                self.add_error('carga_horaria_semanal', 'Informe a carga horária semanal.')
            if carga_total is None:
                self.add_error('carga_horaria_total', 'Informe a carga horária total.')

        return cleaned_data


class BaseEquipeProjetoFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        cpfs = {}
        for form in self.forms:
            if not hasattr(form, 'cleaned_data') or form.cleaned_data.get('DELETE'):
                continue
            membro = form.cleaned_data.get('membro')
            cpf = membro.cpf if membro else form.cleaned_data.get('cpf_manual', '')
            cpf = ''.join(filter(str.isdigit, cpf or ''))
            if not cpf:
                continue
            if cpf in cpfs:
                campo = 'membro' if membro else 'cpf_manual'
                form.add_error(campo, 'Este CPF já foi adicionado à equipe.')
            else:
                cpfs[cpf] = form

EquipeProjetoFormSet = inlineformset_factory(
    Projeto,
    EquipeProjeto,
    form=EquipeProjetoForm,
    formset=BaseEquipeProjetoFormSet,
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
            'regime_trabalho': 'Regime de Trabalho',
            'rg':              'RG',
            'data_nascimento': 'Data de Nascimento',
            'siape':           'SIAPE',
            'lattes':          'Link Currículo Lattes',
            'centro_lotacao':  'Centro Acadêmico',
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
        widgets = {
            'arquivo': forms.FileInput(attrs={'accept': '.pdf,.png,.jpg,.jpeg'}),
        }
        labels = {
            'arquivo': 'Selecione o arquivo do comprovante',
            'descricao': 'Descrição (opcional)',
        }

    def clean_arquivo(self):
        arquivo = self.cleaned_data['arquivo']
        validar_pdf_ou_imagem(arquivo)
        return arquivo


class AprovacaoCentroForm(forms.Form):
    responsavel_nome = forms.CharField(
        label='Nome do responsável pelo Centro Acadêmico',
        max_length=255,
        widget=forms.TextInput(attrs={'autocomplete': 'name'}),
    )
    responsavel_cargo = forms.CharField(
        label='Cargo ou função',
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': 'Ex.: Diretor(a) do Centro Acadêmico'}),
    )
    resultado_deliberacao = forms.ChoiceField(
        label='Resultado da deliberação',
        choices=[('', 'Selecione o resultado')] + list(SolicitacaoAprovacaoCentro.RESULTADO_CHOICES),
        widget=forms.RadioSelect,
    )
    ata_assembleia = forms.FileField(
        label='Ata da assembleia com a deliberação',
        validators=[FileExtensionValidator(FORMATOS_DOCUMENTO), validar_pdf_ou_imagem],
        widget=forms.FileInput(attrs={'accept': '.pdf,.png,.jpg,.jpeg', 'class': 'form-control'}),
        help_text='Formatos aceitos: PDF, PNG, JPG e JPEG.',
    )
    confirma_deliberacao = forms.BooleanField(
        label=(
            'Confirmo que o resultado informado corresponde à deliberação '
            'registrada na ata anexada.'
        ),
        required=True,
    )


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

    def clean(self):
        cleaned_data = super().clean()
        arquivo = cleaned_data.get('arquivo')
        tipo_anexo = cleaned_data.get('tipo_anexo')
        if arquivo and tipo_anexo in ('comprovante_fomento', 'ata_conselho'):
            try:
                validar_pdf_ou_imagem(arquivo)
            except ValidationError as erro:
                self.add_error('arquivo', erro)
        return cleaned_data

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
    """Etapa 1 – Tipo de projeto e informações gerais."""

    tipo_projeto = forms.ChoiceField(
        choices=[('', 'Selecione o tipo do projeto')] + list(Projeto.TIPO_PROJETO_CHOICES),
        label='Tipo de Projeto',
        required=True,
    )
    coordenador_projeto = forms.ModelChoiceField(
        queryset=Usuario.objects.none(),
        label='Coordenador responsável',
        required=False,
    )
    origem_coordenador = forms.ChoiceField(
        choices=(
            ('sistema', 'Coordenador cadastrado no sistema'),
            ('manual', 'Coordenador não cadastrado no sistema'),
        ),
        label='Origem do cadastro do coordenador',
        widget=forms.RadioSelect,
        required=False,
    )
    coordenador_externo_nome = forms.CharField(
        label='Nome completo do coordenador',
        max_length=255,
        required=False,
    )
    coordenador_externo_cpf = forms.CharField(
        label='CPF do coordenador (opcional)',
        max_length=14,
        required=False,
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'placeholder': '000.000.000-00'}),
    )
    coordenador_externo_email = forms.EmailField(
        label='E-mail do coordenador (opcional)',
        required=False,
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
    situacao_etica = forms.ChoiceField(
        choices=[('', 'Selecione a situação do comprovante')] + list(Projeto.SITUACAO_ETICA_CHOICES),
        label='Situação do comprovante ético',
        required=False,
    )
    comprovante_etica = forms.FileField(
        label="Comprovante do Comitê de Ética",
        required=False,
        validators=[FileExtensionValidator(FORMATOS_DOCUMENTO), validar_pdf_ou_imagem],
        widget=forms.FileInput(attrs={'accept': '.pdf,.png,.jpg,.jpeg'}),
        help_text="Anexe a aprovação ou o comprovante de submissão, conforme a opção indicada. Formatos: PDF, PNG, JPG ou JPEG.",
    )
    anexos_gerais = MultipleFileField(
        label="Anexos Adicionais",
        required=False,
        help_text="Selecione vários arquivos de uma vez (PDF, PNG, JPG).",
    )
    comprovante_fomento = forms.FileField(
        label='Comprovante de Aprovação do Fomento',
        required=False,
        validators=[FileExtensionValidator(FORMATOS_DOCUMENTO), validar_pdf_ou_imagem],
        widget=forms.FileInput(attrs={'accept': '.pdf,.png,.jpg,.jpeg'}),
        help_text='Formatos aceitos: PDF, PNG, JPG e JPEG.',
    )
    class Meta:
        model = Projeto
        fields = [
            'tipo_projeto', 'titulo', 'data_inicio', 'data_fim', 'edital',
            'centro_lotacao', 'curso', 'valor_fomento',
            'eh_docente', 'eh_pesquisador', 'eh_pesquisador_visitante',
            'participa_pos_graduacao', 'etica_obrigatoria', 'situacao_etica',
        ]
        widgets = {
            'data_inicio': forms.DateInput(attrs={'type': 'date'}),
            'data_fim':    forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        self.is_draft = kwargs.pop('is_draft', False)
        self.allow_closed_edital = kwargs.pop('allow_closed_edital', False)
        self.modo_gestor = kwargs.pop('modo_gestor', False)
        super().__init__(*args, **kwargs)

        if self.modo_gestor:
            self.fields['coordenador_projeto'].queryset = Usuario.objects.filter(
                perfil='coordenador', is_active=True,
            ).order_by('first_name', 'last_name', 'username')
            self.fields['origem_coordenador'].initial = 'sistema'
            if self.instance and self.instance.pk:
                if self.instance.coordenador_id:
                    self.fields['origem_coordenador'].initial = 'sistema'
                    self.fields['coordenador_projeto'].initial = self.instance.coordenador
                elif self.instance.coordenador_externo_nome:
                    self.fields['origem_coordenador'].initial = 'manual'
        else:
            for campo in (
                'origem_coordenador', 'coordenador_projeto',
                'coordenador_externo_nome', 'coordenador_externo_cpf',
                'coordenador_externo_email',
            ):
                self.fields.pop(campo)

        # Queryset de editais calculado em runtime (evita bug de data fixa)
        if self.allow_closed_edital:
            self.fields['edital'].queryset = Edital.objects.all().order_by('-ano', '-numero')
        else:
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

    def clean_coordenador_externo_cpf(self):
        cpf = ''.join(filter(str.isdigit, self.cleaned_data.get('coordenador_externo_cpf', '')))
        if not cpf:
            return ''
        if len(cpf) != 11 or not CPF().validate(cpf):
            raise ValidationError('Informe um CPF válido.')
        return CPF().mask(cpf)

    def clean(self):
        cleaned_data = super().clean()
        data_inicio = cleaned_data.get('data_inicio')
        data_fim    = cleaned_data.get('data_fim')
        if data_inicio and data_fim and data_fim < data_inicio:
            self.add_error('data_fim', "A data de fim não pode ser anterior à data de início.")

        if self.is_draft:
            return cleaned_data

        if self.modo_gestor:
            origem = cleaned_data.get('origem_coordenador')
            if origem == 'sistema':
                if not cleaned_data.get('coordenador_projeto'):
                    self.add_error('coordenador_projeto', 'Selecione o coordenador cadastrado.')
            elif origem == 'manual':
                if not cleaned_data.get('coordenador_externo_nome', '').strip():
                    self.add_error('coordenador_externo_nome', 'Informe o nome completo do coordenador.')
            else:
                self.add_error('origem_coordenador', 'Informe como o coordenador será registrado.')

        tipo_projeto = cleaned_data.get('tipo_projeto')
        if tipo_projeto == Projeto.TIPO_PROJETO_AGENCIA_FOMENTO:
            if not cleaned_data.get('agencia_financiadora_nome', '').strip():
                self.add_error('agencia_financiadora_nome', 'Informe a agência de fomento responsável pela aprovação.')
            tem_comprovante = bool(
                self.instance.pk and
                self.instance.anexos.filter(tipo_anexo='comprovante_fomento').exists()
            )
            if not cleaned_data.get('comprovante_fomento') and not tem_comprovante:
                self.add_error('comprovante_fomento', 'Anexe o comprovante de aprovação do fomento.')

        elif tipo_projeto == Projeto.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO:
            centro = cleaned_data.get('centro_lotacao')
            if centro and not centro.email:
                self.add_error(
                    'centro_lotacao',
                    'O Centro Acadêmico selecionado não possui e-mail cadastrado para receber a solicitação de deliberação.',
                )

        elif tipo_projeto == Projeto.TIPO_PROJETO_UFAC_COM_FINANCIAMENTO:
            if not cleaned_data.get('edital'):
                self.add_error('edital', 'Selecione um edital aberto para este tipo de projeto.')

        if cleaned_data.get('etica_obrigatoria'):
            situacao = cleaned_data.get('situacao_etica')
            if not cleaned_data.get('tipo_etica_nome', '').strip():
                self.add_error('tipo_etica_nome', 'Informe o comitê de ética responsável.')
            if not situacao:
                self.add_error('situacao_etica', 'Informe se o documento comprova aprovação ou apenas submissão.')
            tipo_existente = 'comite_etica' if situacao == 'aprovado' else 'submissao_comite_etica'
            tem_documento = bool(
                situacao and self.instance.pk
                and self.instance.anexos.filter(tipo_anexo=tipo_existente).exists()
            )
            if situacao and not cleaned_data.get('comprovante_etica') and not tem_documento:
                self.add_error('comprovante_etica', 'Anexe o comprovante correspondente à situação informada.')

        return cleaned_data

    def save(self, commit=True):
        projeto = super().save(commit=False)

        if self.modo_gestor:
            if self.cleaned_data.get('origem_coordenador') == 'manual':
                projeto.coordenador = None
                projeto.coordenador_externo_nome = self.cleaned_data.get('coordenador_externo_nome', '').strip()
                projeto.coordenador_externo_cpf = self.cleaned_data.get('coordenador_externo_cpf', '')
                projeto.coordenador_externo_email = self.cleaned_data.get('coordenador_externo_email', '').strip()
            elif self.cleaned_data.get('coordenador_projeto'):
                projeto.coordenador = self.cleaned_data['coordenador_projeto']
                projeto.coordenador_externo_nome = ''
                projeto.coordenador_externo_cpf = ''
                projeto.coordenador_externo_email = ''

        # Agência Financiadora
        tipo_projeto = self.cleaned_data.get('tipo_projeto')
        nome_agencia = self.cleaned_data.get('agencia_financiadora_nome', '').strip()
        if tipo_projeto == Projeto.TIPO_PROJETO_AGENCIA_FOMENTO and nome_agencia:
            agencia, _ = AgenciaFinanciadora.objects.get_or_create(nome=nome_agencia)
            projeto.agencia_financiadora = agencia
        else:
            projeto.agencia_financiadora = None
            projeto.valor_fomento = None

        if tipo_projeto != Projeto.TIPO_PROJETO_UFAC_COM_FINANCIAMENTO:
            projeto.edital = None

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
        if self.cleaned_data.get('etica_obrigatoria') and nome_etica:
            etica, _ = TipoEtico.objects.get_or_create(nome=nome_etica)
            projeto.tipo_etica = etica
        else:
            projeto.tipo_etica = None
            projeto.situacao_etica = ''
            projeto.etica_submetida_em = None
            projeto.prazo_aprovacao_etica = None

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


class GestorProjetoNovoForm(forms.Form):
    coordenador = forms.ModelChoiceField(
        queryset=Usuario.objects.none(),
        label='Coordenador responsável',
        help_text='Selecione o coordenador ao qual o projeto histórico ficará vinculado.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['coordenador'].queryset = Usuario.objects.filter(
            perfil='coordenador', is_active=True,
        ).order_by('first_name', 'last_name', 'username')


class GestorFinalizarCadastroProjetoForm(forms.Form):
    STATUS_IMPORTACAO = [
        ('submetido', 'Submetido'),
        ('aprovado', 'Aprovado'),
        ('reprovado', 'Reprovado'),
        ('em_andamento', 'Em andamento'),
        ('aguardando_encerramento', 'Aguardando finalização'),
        ('finalizado', 'Finalizado com êxito'),
        ('encerrado', 'Encerrado sem conclusão'),
    ]
    status = forms.ChoiceField(choices=STATUS_IMPORTACAO, label='Situação atual do projeto')
    motivo_encerramento = forms.CharField(
        required=False,
        label='Motivo do encerramento sem conclusão',
        widget=forms.Textarea(attrs={'rows': 3, 'maxlength': 2000}),
    )

    def clean(self):
        dados = super().clean()
        if dados.get('status') == 'encerrado' and not dados.get('motivo_encerramento', '').strip():
            self.add_error('motivo_encerramento', 'Informe o motivo do encerramento sem conclusão.')
        return dados


class ComprovanteEticaAprovacaoForm(forms.Form):
    comprovante = forms.FileField(
        label='Comprovante de aprovação do Comitê de Ética',
        validators=[FileExtensionValidator(FORMATOS_DOCUMENTO), validar_pdf_ou_imagem],
        widget=forms.FileInput(attrs={'accept': '.pdf,.png,.jpg,.jpeg', 'class': 'form-control'}),
        help_text='Formatos aceitos: PDF, PNG, JPG e JPEG.',
    )


class EncerramentoSemConclusaoForm(forms.Form):
    motivo = forms.CharField(
        label='Motivo do encerramento sem conclusão',
        widget=forms.Textarea(attrs={'rows': 5, 'maxlength': 2000}),
        max_length=2000,
    )


class ProjetoEtapa2Form(forms.ModelForm):
    """Etapa 2 – Detalhes textuais do projeto."""

    documento_projeto = forms.FileField(
        label='Documento Digital do Projeto (opcional)',
        required=False,
        validators=[FileExtensionValidator(['pdf'])],
        help_text=(
            'Envie somente PDF nativamente digital, com texto selecionável. '
            'Documentos digitalizados ou fotografados não podem ser processados.'
        ),
        widget=forms.FileInput(attrs={'accept': '.pdf'}),
    )

    class Meta:
        model = Projeto
        fields = [
            'resumo', 'palavras_chave', 'introducao',
            'objetivo_geral', 'objetivos_especificos',
            'metodologia', 'resultados',
            'parcerias', 'referencias',
        ]
        widgets = {
            'resumo':               forms.Textarea(attrs={'rows': 4, 'maxlength': 4000}),
            'palavras_chave':       forms.Textarea(attrs={'rows': 2, 'maxlength': 4000, 'placeholder': 'Separe por vírgulas'}),
            'introducao':           forms.Textarea(attrs={'rows': 6, 'maxlength': 4000}),
            'objetivo_geral':       forms.Textarea(attrs={'rows': 4, 'maxlength': 4000}),
            'objetivos_especificos':forms.Textarea(attrs={'rows': 6, 'maxlength': 4000}),
            'metodologia':          forms.Textarea(attrs={'rows': 6, 'maxlength': 4000}),
            'resultados':           forms.Textarea(attrs={'rows': 6, 'maxlength': 4000}),
            'parcerias':            forms.Textarea(attrs={'rows': 3, 'maxlength': 4000}),
            'referencias':          forms.Textarea(attrs={'rows': 4, 'maxlength': 4000}),
        }
        labels = {
            'introducao':             'Introdução e Justificativa',
            'objetivo_geral':        'Objetivo Geral',
            'objetivos_especificos': 'Objetivos Específicos',
            'resultados':             'Resultados Esperados',
        }

    def __init__(self, *args, **kwargs):
        self.is_draft = kwargs.pop('is_draft', False)
        super().__init__(*args, **kwargs)
        for nome in self.Meta.fields:
            self.fields[nome].max_length = 4000
            self.fields[nome].widget.attrs['maxlength'] = 4000
        if self.is_draft:
            for field in self.fields.values():
                field.required = False

    def clean_documento_projeto(self):
        arquivo = self.cleaned_data.get('documento_projeto')
        if not arquivo:
            self.texto_documento_extraido = ''
            return arquivo

        if arquivo.size > 20 * 1024 * 1024:
            raise ValidationError('O documento deve ter no máximo 20 MB.')
        content_type = getattr(arquivo, 'content_type', '')
        if content_type and content_type != 'application/pdf':
            raise ValidationError('Envie o documento no formato PDF.')

        try:
            self.texto_documento_extraido = extrair_texto_pdf_digital(arquivo)
        except DocumentoProjetoError as erro:
            raise ValidationError(str(erro)) from erro
        return arquivo


class ProjetoEtapa2AgenciaFomentoForm(ProjetoEtapa2Form):
    """
    Mantém o fluxo curto da agência, mas permite preencher todos os campos
    acadêmicos e anexar opcionalmente um documento digital do projeto.
    """

    def clean(self):
        cleaned_data = super().clean()
        if self.is_draft:
            return cleaned_data

        if not cleaned_data.get('resumo'):
            self.add_error('resumo', 'Informe o resumo do projeto.')
        if not cleaned_data.get('palavras_chave'):
            self.add_error('palavras_chave', 'Informe as palavras-chave do projeto.')
        return cleaned_data


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
