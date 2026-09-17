from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import hashlib
import secrets

def _raw_storage():
    """
    Storage lazy para FileFields — usa RawMediaCloudinaryStorage se CLOUDINARY_URL
    estiver configurada, caso contrário usa FileSystemStorage local.
    A inicialização é adiada para evitar erro de credenciais no carregamento do módulo.
    """
    import os
    from django.utils.functional import LazyObject

    class LazyRawStorage(LazyObject):
        def _setup(self):
            if os.environ.get('CLOUDINARY_URL') or os.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('settings_prod'):
                try:
                    from cloudinary_storage.storage import RawMediaCloudinaryStorage
                    self._wrapped = RawMediaCloudinaryStorage()
                    return
                except Exception:
                    pass
            from django.core.files.storage import FileSystemStorage
            self._wrapped = FileSystemStorage()

    return LazyRawStorage()
from validate_docbr import CPF

class UsuarioManager(BaseUserManager):
    """
    Manager customizado para o modelo Usuario, onde o email ou cpf é o identificador único
    para autenticação em vez do username.
    """
    def create_user(self, cpf, username, email, password, **extra_fields):
        if not cpf:
            raise ValueError('O CPF deve ser fornecido')
        cpf_validator = CPF()
        cpf_numeros = ''.join(filter(str.isdigit, cpf))
        if not cpf_validator.validate(cpf_numeros):
            raise ValueError('O CPF fornecido é inválido.')
        if not username:
            raise ValueError('O nome de usuário (username) é obrigatório')
        if not email:
            raise ValueError('O Email deve ser fornecido')
            
        email = self.normalize_email(email)
        user = self.model(cpf=cpf, username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, cpf, username, email, password, **extra_fields):

        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
            
        return self.create_user(cpf, username, email, password, **extra_fields)


# Classe de usuário
class Usuario(AbstractUser):
    PERFIL_CHOICES = (
        ('coordenador', 'Coordenador'),
        ('aluno', 'Aluno'),
        ('gestor', 'Gestor'),
    )

    STATUS_CHOICES = (
        ('pendente', 'Pendente'),
        ('ativo', 'Ativo'),
        ('inativo', 'Inativo'),
    )

    REGIME_TRABALHO_CHOICES = (
        ('20h', '20h'),
        ('40h', '40h'),
        ('DE', 'DE (Dedicação Exclusiva)'),
    )

    # 19 programas de pós-graduação stricto sensu da UFAC (fonte: propeg.ufac.br, mar/2026)
    PROGRAMA_POS_CHOICES = [
        ('', 'Selecione o programa'),
        ('PPGCA',      'Ciências Ambientais (PPGCA)'),
        ('PPGCC',      'Ciência da Computação (PPGCC)'),
        ('PPGCF',      'Ciência Florestal (PPGCF)'),
        ('PPGCSA',     'Ciência da Saúde na Amazônia Ocidental (PPGCSA)'),
        ('PPGCITA',    'Ciência, Inovação e Tecnologia para a Amazônia (PPGCITA)'),
        ('PPGDR',      'Desenvolvimento Regional (PPGDR)'),
        ('PPGECOL',    'Ecologia e Manejo de Recursos Naturais (PPGECOL)'),
        ('PPGEDU',     'Educação (PPGEDU)'),
        ('PPGEF',      'Ensino de Física — Mestrado Profissional (PPGEF)'),
        ('PPGECM',     'Ensino de Ciências e Matemática — Mestrado Profissional (PPGECM)'),
        ('PPEHL',      'Ensino de Humanidades e Linguagens (PPEHL)'),
        ('PPGGEO',     'Geografia (PPGGEO)'),
        ('PPGLL',      'Letras: Linguagem e Identidade (PPGLL)'),
        ('PROFMAT',    'Matemática em Rede Nacional — Mestrado Profissional (PROFMAT)'),
        ('PPGAPV',     'Agronomia: Produção Vegetal (PPGAPV)'),
        ('PPGAC',      'Artes Cênicas (PPGAC)'),
        ('PPGBIONORTE','Biodiversidade e Biotecnologia — Rede Bionorte (PPGBIONORTE)'),
        ('PPGSC',      'Saúde Coletiva (PPGSC)'),
        ('PPGSPA',     'Sanidade e Produção Animal (PPGSPA)'),
    ]

    CNPQ_AREA_CHOICES = [
        ('', 'Selecione uma área'),
        ('Ciências Exatas e da Terra', (
            ('exatas_matematica',  'Matemática'),
            ('exatas_computacao',  'Computação'),
            ('exatas_fisica',      'Física'),
            ('exatas_quimica',     'Química'),
            ('exatas_geociencias', 'Geociências'),
        )),
        ('Ciências Biológicas', (
            ('bio_geral',     'Biologia Geral'),
            ('bio_biofisica', 'Biofísica'),
            ('bio_botanica',  'Botânica'),
            ('bio_ecologia',  'Ecologia'),
            ('bio_genetica',  'Genética'),
        )),
        ('Engenharias', (
            ('eng_civil',    'Engenharia Civil'),
            ('eng_eletrica', 'Engenharia Elétrica'),
            ('eng_mecanica', 'Engenharia Mecânica'),
            ('eng_producao', 'Engenharia de Produção'),
        )),
        ('Ciências da Saúde', (
            ('saude_medicina', 'Medicina'),
            ('saude_nutricao', 'Nutrição'),
            ('saude_coletiva', 'Saúde Coletiva'),
        )),
        ('Ciências Agrárias', (
            ('agrar_agronomia', 'Agronomia'),
            ('agrar_florestal', 'Recursos Florestais'),
            ('agrar_zootecnia', 'Zootecnia'),
        )),
        ('Ciências Sociais Aplicadas', (
            ('sociais_direito',  'Direito'),
            ('sociais_admin',    'Administração'),
            ('sociais_economia', 'Economia'),
            ('sociais_info',     'Ciência da Informação'),
        )),
        ('Ciências Humanas', (
            ('humanas_filosofia',  'Filosofia'),
            ('humanas_sociologia', 'Sociologia'),
            ('humanas_historia',   'História'),
            ('humanas_psicologia', 'Psicologia'),
            ('humanas_educacao',   'Educação'),
        )),
        ('Linguística, Letras e Artes', (
            ('lla_linguistica', 'Linguística'),
            ('lla_letras',      'Letras'),
            ('lla_artes',       'Artes'),
        )),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pendente',
        verbose_name='Status',
    )

    USERNAME_FIELD = 'cpf'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name', 'email']

    cpf = models.CharField(max_length=14, unique=True, verbose_name="CPF")
    email = models.EmailField(unique=True)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    rg = models.CharField(max_length=20, blank=True, null=True, verbose_name="RG")
    data_nascimento = models.DateField(blank=True, null=True, verbose_name="Data de Nascimento")
    siape = models.CharField(max_length=10, blank=True, null=True, verbose_name="SIAPE")
    matricula = models.CharField(max_length=20, blank=True, null=True, verbose_name="Nº de Matrícula")
    lattes = models.URLField(max_length=200, blank=True, null=True, verbose_name="Link Currículo Lattes")
    cnpq_area = models.CharField(
        max_length=100,
        choices=CNPQ_AREA_CHOICES,
        blank=True,
        null=True,
        verbose_name="Grande Área CNPq",
    )
    cnpq = models.CharField(max_length=20, blank=True, null=True, verbose_name="Nº Currículo Lattes/CNPq")
    perfil = models.CharField(max_length=20, choices=PERFIL_CHOICES)
    regime_trabalho = models.CharField(
        max_length=3,
        choices=REGIME_TRABALHO_CHOICES,
        blank=True,
        null=True,
        verbose_name="Regime de Trabalho",
    )
    is_active = models.BooleanField(default=False, verbose_name="Ativo", help_text="Marque esta opção para ativar a conta do usuário.")

    # Vínculo com pós-graduação (coordenador e aluno)
    participa_pos_graduacao = models.BooleanField(
        default=False, blank=True, null=True,
        verbose_name="Vinculado a Programa de Pós-Graduação?",
    )
    programa_pos_vinculo = models.CharField(
        max_length=20,
        choices=PROGRAMA_POS_CHOICES,
        blank=True, null=True,
        verbose_name="Programa de Pós-Graduação",
    )

    curso = models.ForeignKey(
        'CursoGraduacao',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Curso de Graduação",
    )

    endereco = models.OneToOneField(
        'Endereco',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    titulacao = models.ForeignKey(
        'Titulacao',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Titulação"
    )
    centro_lotacao = models.ForeignKey(
        'CentroLotacao',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Centro Acadêmico"
    )

    objects = UsuarioManager()

    def __str__(self):
        return self.get_full_name() or self.username or self.cpf


# Entidades mais simples
class Endereco(models.Model):
    rua = models.CharField(max_length=255)
    numero = models.CharField(max_length=20)
    complemento = models.CharField(max_length=100, blank=True, null=True)
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2, verbose_name="UF")
    cep = models.CharField(max_length=9, verbose_name="CEP")

    def __str__(self):
        return f"{self.rua}, {self.numero} - {self.cidade}"
    
    class Meta:
        verbose_name = "Endereço"
        verbose_name_plural = "Endereços"


class Titulacao(models.Model):
    nome = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nome
    
    class Meta:
        verbose_name = "Titulação"
        verbose_name_plural = "Titulações"


class CentroLotacao(models.Model):
    nome = models.CharField(max_length=255, verbose_name="Nome")
    telefone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return self.nome
    
    class Meta:
        verbose_name = "Centro Acadêmico"
        verbose_name_plural = "Centros Acadêmicos"


class CursoGraduacao(models.Model):
    nome = models.CharField(max_length=255)
    centro_lotacao = models.ForeignKey(
        CentroLotacao,
        on_delete=models.PROTECT,
        verbose_name="Centro Acadêmico"
    )

    def __str__(self):
        return self.nome
    
    class Meta:
        verbose_name= "Curso de Graduação"
        verbose_name_plural = "Cursos de Graduação"


class ProgramaPos(models.Model):
    nome = models.CharField(max_length=255, verbose_name="Nome")
    centro_lotacao = models.ForeignKey(
        CentroLotacao,
        on_delete=models.PROTECT,
        verbose_name="Centro Acadêmico"
    )

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Programa de Pós-Graduação"
        verbose_name_plural = "Programas de Pós-Graduação"


class TipoEtico(models.Model):
    nome = models.CharField(max_length=255)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Tipo Ético"
        verbose_name_plural = "Tipos Éticos"


class ODS(models.Model):
    titulo = models.CharField(max_length=255, verbose_name="Título")
    imagem = models.ImageField(
        upload_to='ods_imagens/',
        blank=True,
        null=True,
        verbose_name="Imagem",
    )

    def __str__(self):
        return self.titulo
    
    class Meta:
        verbose_name = "ODS"
        verbose_name_plural = "ODS"
    

class GrupoPesquisa(models.Model):
    nome = models.CharField(max_length=255)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Grupo de Pesquisa"
        verbose_name_plural = "Grupos de Pesquisa"


class AgenciaFinanciadora(models.Model):
    nome = models.CharField(max_length=255)

    def __str__(self):
        return self.nome
        
    class Meta:
        verbose_name = "Agência Financiadora"
        verbose_name_plural = "Agências Financiadoras"


class Edital(models.Model):
    STATUS_CHOICES = (
        ('rascunho', 'Rascunho'),
        ('aberto', 'Aberto'),
        ('fechado', 'Fechado'),
    )

    tipo = models.CharField(max_length=50, default='PROPEG', verbose_name="Tipo/Origem", help_text="Ex: PROPEG, PROEX, etc.")
    numero = models.PositiveIntegerField(verbose_name="Número do Edital")
    ano = models.PositiveIntegerField(verbose_name="Ano do Edital")
    titulo = models.CharField(max_length=255, verbose_name="Título Descritivo do Edital")
    descricao = models.TextField(verbose_name="Descrição Resumida")
    data_inicio_submissoes = models.DateField(verbose_name="Início das Submissões")
    data_fim_submissoes = models.DateField(verbose_name="Fim das Submissões")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='rascunho')
    
    documento_principal = models.FileField(
        upload_to='editais/documentos/',
        storage=_raw_storage(),
        blank=True, null=True,
        max_length=500,
        verbose_name="Documento Principal do Edital (PDF)"
    )
    
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    data_criacao = models.DateTimeField(auto_now_add=True)

    @property
    def titulo_completo(self):
        return f"Edital {self.tipo} n°{self.numero}/{self.ano} - {self.titulo}"

    def __str__(self):
        return self.titulo_completo

    class Meta:
        verbose_name = "Edital"
        verbose_name_plural = "Editais"
        ordering = ['-ano', '-numero']
        unique_together = ('numero', 'ano', 'tipo')


class AnexoEdital(models.Model):
    edital = models.ForeignKey(Edital, on_delete=models.CASCADE, related_name='anexos')
    descricao = models.CharField(max_length=255, verbose_name="Descrição do Anexo")
    arquivo = models.FileField(upload_to='editais/anexos/', storage=_raw_storage(), max_length=500)
    data_upload = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Anexo '{self.descricao}' do edital '{self.edital.titulo}'"

    class Meta:
        verbose_name = "Anexo do Edital"
        verbose_name_plural = "Anexos do Edital"


class AdendoEdital(models.Model):
    edital    = models.ForeignKey(Edital, on_delete=models.CASCADE, related_name='adendos')
    titulo    = models.CharField(max_length=255, verbose_name="Título do Adendo")
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição")
    arquivo   = models.FileField(upload_to='editais/adendos/', blank=True, null=True,
                                  storage=_raw_storage(),
                                  max_length=500,
                                  verbose_name="Arquivo do Adendo (PDF, opcional)")
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Adendo: {self.titulo} — {self.edital.titulo_completo}"

    class Meta:
        verbose_name = "Adendo do Edital"
        verbose_name_plural = "Adendos do Edital"
        ordering = ['-data_criacao']


# Entidade Principal
class Projeto(models.Model):
    TIPO_PROJETO_AGENCIA_FOMENTO = 'agencia_fomento'
    TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO = 'ufac_sem_financiamento'
    TIPO_PROJETO_UFAC_COM_FINANCIAMENTO = 'ufac_com_financiamento'

    TIPO_PROJETO_CHOICES = [
        (TIPO_PROJETO_AGENCIA_FOMENTO, '1 - Projeto Aprovado (Agência de Fomento)'),
        (TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO, '2 - UFAC (Sem Financiamento/Fluxo Contínuo)'),
        (TIPO_PROJETO_UFAC_COM_FINANCIAMENTO, '3 - UFAC (Com Financiamento)'),
    ]

    STATUS_CHOICES = [
        ('rascunho', 'Rascunho'),
        ('submetido', 'Submetido'),
        ('aguardando_conselho', 'Aguardando deliberação do Centro Acadêmico'),
        ('aprovado', 'Aprovado'),
        ('reprovado', 'Reprovado'),
        ('em_andamento', 'Em andamento'),
        ('aguardando_encerramento', 'Aguardando Finalização'),
        ('finalizado', 'Finalizado'),
        ('encerrado', 'Encerrado sem conclusão'),
    ]

    SITUACAO_ETICA_CHOICES = [
        ('aprovado', 'Comprovante de aprovação'),
        ('submetido', 'Comprovante de submissão'),
    ]
    
    titulo = models.CharField(max_length=255, blank=True, null=True)
    descricao = models.TextField(verbose_name="Descrição", blank=True, null=True)
    resumo = models.TextField(max_length=4000, blank=True, null=True)
    introducao = models.TextField(max_length=4000, verbose_name="Introdução e Justificativa", blank=True, null=True)
    objetivo_geral = models.TextField(max_length=4000, blank=True, null=True, verbose_name="Objetivo Geral")
    objetivos_especificos = models.TextField(max_length=4000, blank=True, null=True, verbose_name="Objetivos Específicos")
    objetivos = models.TextField(blank=True, null=True)  # mantido para compatibilidade
    metodologia = models.TextField(max_length=4000, blank=True, null=True)
    resultados = models.TextField(max_length=4000, verbose_name="Resultados Esperados", blank=True, null=True)
    referencias = models.TextField(max_length=4000, blank=True, null=True)
    data_inicio = models.DateField(verbose_name="Data de Início", blank=True, null=True)
    data_fim = models.DateField(verbose_name="Data de Fim", blank=True, null=True)
    tipo_projeto = models.CharField(
        max_length=40,
        choices=TIPO_PROJETO_CHOICES,
        blank=True,
        default='',
        verbose_name="Tipo de Projeto",
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='rascunho')
    valor_fomento = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    etica_obrigatoria = models.BooleanField(default=False, verbose_name="Envolve Aspectos Éticos?", blank=True, null=True)
    situacao_etica = models.CharField(
        max_length=20,
        choices=SITUACAO_ETICA_CHOICES,
        blank=True,
        default='',
        verbose_name='Situação do documento ético',
    )
    etica_submetida_em = models.DateField(blank=True, null=True)
    prazo_aprovacao_etica = models.DateField(blank=True, null=True)

    # Auditoria de correções feitas pela gestão e importação do acervo legado.
    importado_legado = models.BooleanField(default=False)
    ultima_alteracao_gestor_em = models.DateTimeField(blank=True, null=True)
    ultima_alteracao_gestor_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='projetos_alterados_como_gestor',
    )
    finalizado_em = models.DateTimeField(blank=True, null=True)
    encerrado_em = models.DateTimeField(blank=True, null=True)
    encerrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='projetos_encerrados_sem_conclusao',
    )
    motivo_encerramento = models.TextField(blank=True)

    eh_docente = models.BooleanField(default=False, verbose_name="É docente?", blank=True, null=True)
    eh_pesquisador = models.BooleanField(default=False, verbose_name="É pesquisador?", blank=True, null=True)
    eh_pesquisador_visitante = models.BooleanField(default=False, verbose_name="É pesquisador visitante?", blank=True, null=True)

    # Chaves Estrangeiras e Relações
    coordenador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='projetos_coordenados',
        null=True,
        blank=True,
    )
    coordenador_externo_nome = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Nome do coordenador não cadastrado',
    )
    coordenador_externo_cpf = models.CharField(
        max_length=14,
        blank=True,
        verbose_name='CPF do coordenador não cadastrado',
    )
    coordenador_externo_email = models.EmailField(
        blank=True,
        verbose_name='E-mail do coordenador não cadastrado',
    )
    curso = models.ForeignKey(
        CursoGraduacao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Curso de Graduação"
    )
    centro_lotacao = models.ForeignKey(
        CentroLotacao,
        on_delete=models.PROTECT,
        verbose_name="Centro Acadêmico",
        null=True,
        blank=True,
    )
    agencia_financiadora = models.ForeignKey(
        AgenciaFinanciadora,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Agência Financiadora"
    )
    tipo_etica = models.ForeignKey(
        TipoEtico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Tipo Ético"
    )
    ods = models.ManyToManyField(ODS, blank=True)
    grupos_pesquisa = models.ManyToManyField(
        GrupoPesquisa,
        blank=True,
        verbose_name="Grupos de Pesquisa"
    )
    alunos = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='EquipeProjeto',
        related_name='projetos_participados',
        blank=True
    )

    participa_pos_graduacao = models.BooleanField(default=False, blank=True, null=True, verbose_name="Participa de Programa de Pós-Graduação?")
    programa_pos = models.ForeignKey(
        'ProgramaPos',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Programa de Pós-Graduação"
    )

    palavras_chave = models.TextField(max_length=4000, blank=True, null=True, help_text="Separe por vírgulas. Ex.: Tecnologia, Educação, Web")
    parcerias = models.TextField(max_length=4000, blank=True, null=True)

    imagem_capa = models.ImageField(
        upload_to='projetos_capas/',
        null=True,
        blank=True,
        verbose_name="Imagem de Capa",
    )

    edital = models.ForeignKey(
        Edital,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='projetos',
        verbose_name="Edital Vinculado"
    )

    def __str__(self):
        return self.titulo or f"Projeto Rascunho (ID: {self.id})"

    @property
    def nome_coordenador(self):
        if self.coordenador_id:
            return self.coordenador.get_full_name() or self.coordenador.username
        return self.coordenador_externo_nome or 'Não informado'

    @property
    def cpf_coordenador(self):
        if self.coordenador_id:
            return self.coordenador.cpf
        return self.coordenador_externo_cpf

    @property
    def email_coordenador(self):
        if self.coordenador_id:
            return self.coordenador.email
        return self.coordenador_externo_email

    @property
    def eh_agencia_fomento(self):
        return self.tipo_projeto == self.TIPO_PROJETO_AGENCIA_FOMENTO

    @property
    def possui_financiamento(self):
        return self.tipo_projeto in (
            self.TIPO_PROJETO_AGENCIA_FOMENTO,
            self.TIPO_PROJETO_UFAC_COM_FINANCIAMENTO,
        )

    @property
    def requer_edital_ufac(self):
        return self.tipo_projeto == self.TIPO_PROJETO_UFAC_COM_FINANCIAMENTO

    @property
    def requer_ata_conselho(self):
        return self.tipo_projeto == self.TIPO_PROJETO_UFAC_SEM_FINANCIAMENTO

    @property
    def requer_tramitacao_centro(self):
        return self.tipo_projeto == self.TIPO_PROJETO_UFAC_COM_FINANCIAMENTO

    @property
    def anexos_documentais(self):
        """Anexos exibíveis no PDF, sem incluir o próprio relatório automático."""
        return self.anexos.exclude(tipo_anexo='relatorio_submissao')

    @property
    def comprovante_etica_aprovado(self):
        return self.anexos.filter(tipo_anexo='comite_etica').order_by('-data_upload').first()

    @property
    def comprovante_submissao_etica(self):
        return self.anexos.filter(tipo_anexo='submissao_comite_etica').order_by('-data_upload').first()

    @property
    def etica_pendente(self):
        return bool(
            self.etica_obrigatoria
            and not self.anexos.filter(tipo_anexo='comite_etica').exists()
        )

    @property
    def dias_restantes_etica(self):
        if not self.etica_pendente or not self.prazo_aprovacao_etica:
            return None
        return (self.prazo_aprovacao_etica - timezone.localdate()).days
    
    class Meta:
        ordering = ['-data_inicio']
        verbose_name = "Projeto"
        verbose_name_plural = "Projetos"


class EquipeProjeto(models.Model):
    """
    Modelo intermediário para registrar os membros da equipe de um projeto
    e suas informações específicas, como carga horária.
    """
    ORIGEM_SISTEMA = 'sistema'
    ORIGEM_MANUAL = 'manual'
    ORIGEM_CHOICES = [
        (ORIGEM_SISTEMA, 'Usuário do sistema'),
        (ORIGEM_MANUAL, 'Preenchimento manual'),
    ]

    FUNCAO_CHOICES = [
        ('coordenador', 'Coordenador'),
        ('estudante_graduacao', 'Estudante Graduação'),
        ('estudante_pos_mestrado', 'Estudante Pós (Mestrado)'),
        ('estudante_pos_doutorado', 'Estudante Pós (Doutorado)'),
        ('estudante_pos_especializacao', 'Estudante Pós (Especialização)'),
        ('estudante_ensino_medio', 'Estudante Ensino Médio'),
        ('estudante_ensino_fundamental', 'Estudante Ensino Fundamental'),
    ]

    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name='equipe')
    origem_membro = models.CharField(
        max_length=10,
        choices=ORIGEM_CHOICES,
        default=ORIGEM_SISTEMA,
        verbose_name='Forma de cadastro',
    )
    membro = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        related_name='participa_em',
        null=True,
        blank=True,
    )
    nome_membro_manual = models.CharField(max_length=255, blank=True, verbose_name='Nome do Membro')
    cpf_manual = models.CharField(max_length=14, blank=True, verbose_name='CPF')
    funcao = models.CharField(
        max_length=50,
        choices=FUNCAO_CHOICES,
        default='coordenador',
        verbose_name='Função na Equipe',
    )
    carga_horaria_semanal = models.PositiveIntegerField(verbose_name="Carga Horária Semanal (h)", null=True, blank=True)
    carga_horaria_total = models.PositiveIntegerField(verbose_name="Carga Horária Total (h)", null=True, blank=True)

    class Meta:
        verbose_name = "Membro da Equipe"
        verbose_name_plural = "Equipes dos Projetos"
        constraints = [
            models.UniqueConstraint(
                fields=('projeto', 'membro'),
                condition=models.Q(membro__isnull=False),
                name='equipe_usuario_unico_por_projeto',
            ),
            models.UniqueConstraint(
                fields=('projeto', 'cpf_manual'),
                condition=~models.Q(cpf_manual=''),
                name='equipe_cpf_manual_unico_por_projeto',
            ),
        ]

    @property
    def nome_exibicao(self):
        if self.membro_id:
            return self.membro.get_full_name() or self.membro.username
        return self.nome_membro_manual or 'Membro não informado'

    @property
    def cpf_exibicao(self):
        valor = self.membro.cpf if self.membro_id else self.cpf_manual
        numeros = ''.join(filter(str.isdigit, valor or ''))
        if len(numeros) == 11:
            return f'{numeros[:3]}.{numeros[3:6]}.{numeros[6:9]}-{numeros[9:]}'
        return valor

    @property
    def perfil_exibicao(self):
        return self.membro.get_perfil_display() if self.membro_id else 'Cadastro manual'

    @property
    def curso_exibicao(self):
        if self.membro_id and self.membro.curso_id:
            return str(self.membro.curso)
        return 'Não informado'

    def __str__(self):
        return f"{self.nome_exibicao} ({self.get_funcao_display()}) no projeto {self.projeto.titulo}"

# Modelos relacionados a um projeto
def caminho_upload_arquivo(instance, filename): # função para gerar um caminho dinâmico para o upload de um arquivo
    return f'projetos/{instance.projeto.id}/{instance.__class__.__name__.lower()}/{filename}'


class Documento(models.Model):
    nome = models.CharField(max_length=255)
    tipo = models.CharField(max_length=100)
    caminho_arquivo = models.FileField(upload_to=caminho_upload_arquivo, storage=_raw_storage(), max_length=500, verbose_name="Arquivo")
    enviado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name="documentos")
    
    def __str__(self):
        return self.nome
    

class Ata(models.Model):
    descricao = models.CharField(max_length=255, verbose_name="Descrição")
    data_reuniao = models.DateField(verbose_name="Data da Reunião")
    arquivo_pdf = models.FileField(upload_to=caminho_upload_arquivo, storage=_raw_storage(), max_length=500)
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name='atas'
    )
    
    def __str__(self):
        return f"Ata de {self.data_reuniao.strftime('%d/%m/%Y')} - {self.projeto.titulo}"
    
    class Meta:
        verbose_name_plural = "Atas"


class Anexo(models.Model):
    """
    Modelo para armazenar arquivos anexados a um projeto,
    com um tipo definido para cada arquivo.
    """
    TIPO_ANEXO_CHOICES = (
        ('comite_etica', 'Aprovação do Comitê de Ética'),
        ('submissao_comite_etica', 'Comprovante de Submissão ao Comitê de Ética'),
        ('cronograma', 'Cronograma'),
        ('imagens', 'Figuras, Imagens, etc.'),
        ('projeto_completo', 'Projeto Completo'),
        ('comprovante_fomento', 'Comprovante de Aprovação da Agência de Fomento'),
        ('comprovante_aprovacao', 'Comprovante de Aprovação (Gestor)'),
        ('ata_conselho', 'Ata de Deliberação do Centro Acadêmico'),
        ('relatorio_submissao', 'Relatório de Submissão (Automático)'),
        ('outro', 'Outro'),
    )

    projeto = models.ForeignKey(
        Projeto, 
        on_delete=models.CASCADE, 
        related_name='anexos'
    )
    
    tipo_anexo = models.CharField(
        max_length=50, 
        choices=TIPO_ANEXO_CHOICES, 
        verbose_name="Tipo de Anexo"
    )
    arquivo = models.FileField(
        upload_to='anexos/%Y/%m/',
        storage=_raw_storage(),
        max_length=500,
        verbose_name="Arquivo"
    )
    
    descricao = models.CharField(max_length=255, blank=True, null=True, verbose_name="Descrição")
    data_upload = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.projeto.titulo} - {self.get_tipo_anexo_display()}"

    class Meta:
        verbose_name = "Anexo"
        verbose_name_plural = "Anexos"


class SolicitacaoAprovacaoCentro(models.Model):
    """Convite restrito para o Centro Acadêmico registrar sua deliberação."""

    RESULTADO_CHOICES = (
        ('aprovado', 'Aprovado pelo Centro Acadêmico'),
        ('reprovado', 'Reprovado pelo Centro Acadêmico'),
    )

    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name='solicitacoes_aprovacao_centro',
    )
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    email_destinatario = models.EmailField()
    criada_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField()
    utilizada_em = models.DateTimeField(blank=True, null=True)
    invalidada_em = models.DateTimeField(blank=True, null=True)
    responsavel_nome = models.CharField(max_length=255, blank=True)
    responsavel_cargo = models.CharField(max_length=255, blank=True)
    resultado_deliberacao = models.CharField(
        max_length=20,
        choices=RESULTADO_CHOICES,
        blank=True,
    )
    ata = models.OneToOneField(
        Anexo,
        on_delete=models.SET_NULL,
        related_name='solicitacao_centro',
        blank=True,
        null=True,
    )

    @staticmethod
    def calcular_hash(token):
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    @classmethod
    def emitir(cls, projeto, email_destinatario, validade_horas=168):
        """Invalida convites anteriores e devolve a solicitação e o token bruto."""
        agora = timezone.now()
        cls.objects.filter(
            projeto=projeto,
            utilizada_em__isnull=True,
            invalidada_em__isnull=True,
        ).update(invalidada_em=agora)

        token = secrets.token_urlsafe(32)
        solicitacao = cls.objects.create(
            projeto=projeto,
            token_hash=cls.calcular_hash(token),
            email_destinatario=email_destinatario,
            expira_em=agora + timedelta(hours=validade_horas),
        )
        return solicitacao, token

    @property
    def esta_ativa(self):
        return (
            self.utilizada_em is None
            and self.invalidada_em is None
            and self.expira_em > timezone.now()
        )

    def __str__(self):
        return f'Deliberação do Centro Acadêmico - {self.projeto}'

    class Meta:
        ordering = ['-criada_em']
        verbose_name = 'Solicitação de Deliberação do Centro Acadêmico'
        verbose_name_plural = 'Solicitações de Deliberação do Centro Acadêmico'


class Relatorio(models.Model):
    TIPO_CHOICES = (
        ('parcial', 'Parcial'),
        ('final', 'Final')
    )
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    data_envio = models.DateTimeField(auto_now_add=True)
    anexo_pdf = models.FileField(upload_to=caminho_upload_arquivo, storage=_raw_storage(), max_length=500)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name='Responsável'
    )
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name='relatorios'
    )

    def __str__(self):
        return f"Relatório {self.get_tipo_display()} para {self.projeto.titulo}"

    class Meta:
        verbose_name = "Relatório"
        verbose_name_plural = "Relatórios"


class EvidenciaRelatorio(models.Model):
    relatorio   = models.ForeignKey(Relatorio, on_delete=models.CASCADE, related_name='evidencias')
    arquivo     = models.FileField(upload_to='relatorios/evidencias/', storage=_raw_storage(), max_length=500)
    descricao   = models.CharField(max_length=255, blank=True, default='')
    data_upload = models.DateTimeField(auto_now_add=True)

    @property
    def is_imagem(self):
        return self.arquivo.name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))

    def __str__(self):
        return f"Evidência do {self.relatorio}"

    class Meta:
        verbose_name = "Evidência de Relatório"
        verbose_name_plural = "Evidências de Relatório"


class Notificacao(models.Model):
    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notificacoes',
    )
    mensagem = models.TextField()
    lida = models.BooleanField(default=False)
    data_criacao = models.DateTimeField(auto_now_add=True)
    link = models.URLField(blank=True, null=True, help_text="Link para a página relevante, se houver.")

    def __str__(self):
        return f"Notificação para {self.destinatario.username}: {self.mensagem[:30]}"

    class Meta:
        ordering = ['-data_criacao']
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"


class NotificacaoPrazoEtica(models.Model):
    """Evita o reenvio do mesmo alerta de prazo para um projeto."""

    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name='alertas_prazo_etica',
    )
    dias_restantes = models.PositiveSmallIntegerField()
    enviada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('projeto', 'dias_restantes'),
                name='alerta_etica_unico_por_prazo',
            ),
        ]
        ordering = ['-enviada_em']

    def __str__(self):
        return f'{self.projeto} - alerta de {self.dias_restantes} dia(s)'
