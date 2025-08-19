# É uma boa prática importar o get_user_model para referenciar o usuário
from django.contrib.auth import get_user_model
from django.db import models

# Vamos usar o modelo de Usuário padrão do Django, que já tem nome, email, senha, etc.
# Podemos estendê-lo se precisarmos de campos adicionais como 'perfil', 'cpf', 'regime_trabalho'.
# Para isso, o ideal seria criar um "Custom User Model" no início do projeto.
# Por simplicidade aqui, vamos conectar os dados extras a ele.

class Endereco(models.Model):
    rua = models.CharField(max_length=255)
    numero = models.CharField(max_length=20)
    complemento = models.CharField(max_length=100, blank=True, null=True)
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)
    cep = models.CharField(max_length=9)

    def __str__(self):
        return f"{self.rua}, {self.numero} - {self.cidade}"

class CentroLotacao(models.Model):
    nome = models.CharField(max_length=255)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return self.nome

# O ideal seria um Custom User Model, mas para um projeto já iniciado,
# podemos usar um "Profile Model" ligado por OneToOneField.
class UsuarioProfile(models.Model):
    PERFIL_CHOICES = [('professor', 'Professor'), ('aluno', 'Aluno'), ('gestor', 'Gestor')]
    
    usuario = models.OneToOneField(get_user_model(), on_delete=models.CASCADE, related_name='profile')
    cpf = models.CharField(max_length=14, unique=True)
    telefone = models.CharField(max_length=20)
    perfil = models.CharField(max_length=20, choices=PERFIL_CHOICES)
    endereco = models.ForeignKey(Endereco, on_delete=models.SET_NULL, null=True, blank=True)
    centro_lotacao = models.ForeignKey(CentroLotacao, on_delete=models.SET_NULL, null=True)
    regime_trabalho = models.CharField(max_length=50, blank=True, null=True) # Apenas para professores

    def __str__(self):
        return self.usuario.username

class ODS(models.Model):
    # Tabela referente aos Objetivos de Desenvolvimento Sustentável da ONU
    titulo = models.CharField(max_length=255)

    def __str__(self):
        return self.titulo

class GrupoPesquisa(models.Model):
    nome = models.CharField(max_length=255)

    def __str__(self):
        return self.nome

class Projeto(models.Model):
    STATUS_CHOICES = [
        ('aguardando_conselho', 'Aguardando aprovação do conselho'),
        ('aprovado', 'Aprovado'),
        ('reprovado', 'Reprovado'),
        ('em_andamento', 'Em andamento'),
        ('encerrado', 'Encerrado'),
    ]
    
    titulo = models.CharField(max_length=255)
    descricao = models.TextField()
    resumo = models.TextField()
    introducao = models.TextField()
    objetivos = models.TextField()
    metodologia = models.TextField()
    resultados = models.TextField(blank=True, null=True)
    referencias = models.TextField(blank=True, null=True)
    data_inicio = models.DateField()
    data_fim = models.DateField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='aguardando_conselho')
    valor_fomento = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Chaves Estrangeiras e Relações
    coordenador = models.ForeignKey(get_user_model(), on_delete=models.PROTECT, related_name='projetos_coordenados')
    centro_lotacao = models.ForeignKey(CentroLotacao, on_delete=models.PROTECT)
    alunos = models.ManyToManyField(get_user_model(), related_name='projetos_participantes', blank=True)
    ods = models.ManyToManyField(ODS, blank=True)
    grupos_pesquisa = models.ManyToManyField(GrupoPesquisa, blank=True)

    def __str__(self):
        return self.titulo

class Relatorio(models.Model):
    TIPO_CHOICES = [('parcial', 'Parcial'), ('final', 'Final')]
    
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name='relatorios')
    data_envio = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    anexo_pdf = models.FileField(upload_to='relatorios/')
    responsavel = models.ForeignKey(get_user_model(), on_delete=models.PROTECT)

    def __str__(self):
        return f"Relatório {self.tipo} para {self.projeto.titulo}"
