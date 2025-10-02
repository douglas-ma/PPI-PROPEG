from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.conf import settings
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
    perfil = models.CharField(max_length=20, choices=PERFIL_CHOICES)
    regime_trabalho = models.CharField(max_length=3, blank=True, null=True, verbose_name="Regime de Trabalho")
    is_active = models.BooleanField(default=False, verbose_name="Ativo", help_text="Marque esta opção para ativar a conta do usuário.")

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
        verbose_name="Centro de Lotação"
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
        verbose_name = "Centro de Lotação"
        verbose_name_plural = "Centros de Lotação"


class CursoGraduacao(models.Model):
    nome = models.CharField(max_length=255)
    centro_lotacao = models.ForeignKey(
        CentroLotacao,
        on_delete=models.PROTECT,
        verbose_name="Centro de Lotação"
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
        verbose_name="Centro de Lotação"
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

    titulo = models.CharField(max_length=255, verbose_name="Título do Edital")
    descricao = models.TextField(verbose_name="Descrição Resumida")
    data_inicio_submissoes = models.DateField(verbose_name="Início das Submissões")
    data_fim_submissoes = models.DateField(verbose_name="Fim das Submissões")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='rascunho')
    
    documento_principal = models.FileField(
        upload_to='editais/documentos/',
        verbose_name="Documento Principal do Edital (PDF)"
    )
    
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titulo

    class Meta:
        verbose_name = "Edital"
        verbose_name_plural = "Editais"
        ordering = ['-data_inicio_submissoes']


class AnexoEdital(models.Model):
    edital = models.ForeignKey(Edital, on_delete=models.CASCADE, related_name='anexos')
    descricao = models.CharField(max_length=255, verbose_name="Descrição do Anexo")
    arquivo = models.FileField(upload_to='editais/anexos/')
    data_upload = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Anexo '{self.descricao}' do edital '{self.edital.titulo}'"

    class Meta:
        verbose_name = "Anexo do Edital"
        verbose_name_plural = "Anexos do Edital"


# Entidade Principal
class Projeto(models.Model):
    STATUS_CHOICES = [
        ('rascunho', 'Rascunho'),
        ('submetido', 'Submetido'),
        ('aguardando_conselho', 'Aguardando aprovação do conselho'),
        ('aprovado', 'Aprovado'),
        ('reprovado', 'Reprovado'),
        ('em_andamento', 'Em andamento'),
        ('aguardando_encerramento', 'Aguardando Encerramento'),
        ('encerrado', 'Encerrado'),
    ]
    
    titulo = models.CharField(max_length=255, blank=True, null=True)
    descricao = models.TextField(verbose_name="Descrição", blank=True, null=True)
    resumo = models.TextField(blank=True, null=True)
    introducao = models.TextField(verbose_name="Introdução", blank=True, null=True)
    objetivos = models.TextField(blank=True, null=True)
    metodologia = models.TextField(blank=True, null=True)
    resultados = models.TextField(blank=True, null=True)
    referencias = models.TextField(blank=True, null=True)
    data_inicio = models.DateField(verbose_name="Data de Início", blank=True, null=True)
    data_fim = models.DateField(verbose_name="Data de Fim", blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='rascunho')
    valor_fomento = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    etica_obrigatoria = models.BooleanField(default=False, verbose_name="Envolve Aspectos Éticos?", blank=True, null=True)

    eh_docente = models.BooleanField(default=False, verbose_name="É docente?", blank=True, null=True)
    eh_pesquisador = models.BooleanField(default=False, verbose_name="É pesquisador?", blank=True, null=True)
    eh_pesquisador_visitante = models.BooleanField(default=False, verbose_name="É pesquisador visitante?", blank=True, null=True)

    # Chaves Estrangeiras e Relações
    coordenador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='projetos_coordenados'
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
        verbose_name="Centro de Lotação",
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

    palavras_chave = models.CharField(max_length=255, blank=True, null=True, help_text="Separe por vírgulas. Ex.: Tecnologia, Educação, Web")
    parcerias = models.TextField(blank=True, null=True)

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
    
    class Meta:
        ordering = ['-data_inicio']
        verbose_name = "Projeto"
        verbose_name_plural = "Projetos"


class EquipeProjeto(models.Model):
    """
    Modelo intermediário para registrar os membros da equipe de um projeto
    e suas informações específicas, como carga horária.
    """
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name='equipe')
    membro = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='participa_em')
    
    carga_horaria_semanal = models.PositiveIntegerField(verbose_name="Carga Horária Semanal (h)")
    carga_horaria_total = models.PositiveIntegerField(verbose_name="Carga Horária Total (h)")

    class Meta:
        verbose_name = "Membro da Equipe"
        verbose_name_plural = "Equipes dos Projetos"
        unique_together = ('projeto', 'membro')

    def __str__(self):
        return f"{self.membro.get_full_name()} no projeto {self.projeto.titulo}"

# Modelos relacionados a um projeto
def caminho_upload_arquivo(instance, filename): # função para gerar um caminho dinâmico para o upload de um arquivo
    return f'projetos/{instance.projeto.id}/{instance.__class__.__name__.lower()}/{filename}'


class Documento(models.Model):
    nome = models.CharField(max_length=255)
    tipo = models.CharField(max_length=100)
    caminho_arquivo = models.FileField(upload_to=caminho_upload_arquivo, verbose_name="Arquivo")
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
    arquivo_pdf = models.FileField(upload_to=caminho_upload_arquivo)
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
        ('cronograma', 'Cronograma'),
        ('imagens', 'Figuras, Imagens, etc.'),
        ('projeto_completo', 'Projeto Completo'),
        ('comprovante_aprovacao', 'Comprovante de Aprovação (Gestor)'),
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
        verbose_name="Arquivo"
    )
    
    descricao = models.CharField(max_length=255, blank=True, null=True, verbose_name="Descrição")
    data_upload = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.projeto.titulo} - {self.get_tipo_anexo_display()}"

    class Meta:
        verbose_name = "Anexo"
        verbose_name_plural = "Anexos"


class Relatorio(models.Model):
    TIPO_CHOICES = (
        ('parcial', 'Parcial'),
        ('final', 'Final')
    )
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    data_envio = models.DateTimeField(auto_now_add=True)
    anexo_pdf = models.FileField(upload_to=caminho_upload_arquivo)
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
