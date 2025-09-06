from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

# Classe de usuário
class Usuario(AbstractUser):
    PERFIL_CHOICES = (
        ('coordenador', 'Coordenador'),
        ('aluno', 'Aluno'),
        ('gestor', 'Gestor'),
    )
    cpf = models.CharField(max_length=14, unique=True, verbose_name="CPF")
    telefone = models.CharField(max_length=20, blank=True, null=True)
    perfil = models.CharField(max_length=20, choices=PERFIL_CHOICES)
    regime_trabalho = models.CharField(max_length=3, blank=True, null=True, verbose_name="Regime de Trabalho")

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

    def __str__(self):
        return self.get_full_name() or self.username

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

# Entidade Principal
class Projeto(models.Model):
    STATUS_CHOICES = [
        ('submetido', 'Submetido'),
        ('aguardando_conselho', 'Aguardando aprovação do conselho'),
        ('aprovado', 'Aprovado'),
        ('reprovado', 'Reprovado'),
        ('em_andamento', 'Em andamento'),
        ('encerrado', 'Encerrado'),
    ]
    
    titulo = models.CharField(max_length=255)
    descricao = models.TextField(verbose_name="Descrição")
    resumo = models.TextField()
    introducao = models.TextField(verbose_name="Introdução")
    objetivos = models.TextField()
    metodologia = models.TextField()
    resultados = models.TextField(blank=True, null=True)
    referencias = models.TextField(blank=True, null=True)
    data_inicio = models.DateField(verbose_name="Data de Início")
    data_fim = models.DateField(verbose_name="Data de Fim")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='submetido')
    valor_fomento = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
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
        verbose_name="Centro de Lotação"
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
        related_name='projetos_participados',
        limit_choices_to={'perfil': 'aluno'},
        blank=True
    )

    def __str__(self):
        return self.titulo
    
    class Meta:
        ordering = ['-data_inicio']
        verbose_name = "Projeto"
        verbose_name_plural = "Projetos"

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

class Relatorio(models.Model):
    TIPO_CHOICES = (
        ('parcial', 'Parcial'),
        ('final', 'Final')
    )
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    data_envio = models.DateField(auto_now_add=True)
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
