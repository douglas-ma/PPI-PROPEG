from rest_framework import serializers
from .models import Endereco, CentroLotacao, UsuarioProfile, ODS, GrupoPesquisa, Projeto, Relatorio
from django.contrib.auth.models import User # Usando o User padrão
from django.db import transaction # Para garantir que ambas as criações funcionem ou falhem juntas


# Serializer para o modelo de Usuário padrão do Django
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']

class CentroLotacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CentroLotacao
        fields = '__all__'

class OdsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ODS
        fields = '__all__'

# Serializer principal para Projetos
class ProjetoSerializer(serializers.ModelSerializer):
    # Para leitura (GET), queremos ver os detalhes, não apenas os IDs.
    coordenador = UserSerializer(read_only=True)
    centro_lotacao = CentroLotacaoSerializer(read_only=True)
    ods = OdsSerializer(many=True, read_only=True)
    
    # Para escrita (POST/PUT), esperamos receber apenas os IDs.
    coordenador_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='coordenador', write_only=True
    )
    centro_lotacao_id = serializers.PrimaryKeyRelatedField(
        queryset=CentroLotacao.objects.all(), source='centro_lotacao', write_only=True
    )
    ods_ids = serializers.PrimaryKeyRelatedField(
        queryset=ODS.objects.all(), source='ods', many=True, write_only=True
    )
    alunos_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(profile__perfil='aluno'), source='alunos', many=True, write_only=True, required=False
    )

    class Meta:
        model = Projeto
        fields = [
            'id', 'titulo', 'descricao', 'resumo', 'introducao', 'objetivos', 
            'metodologia', 'resultados', 'referencias', 'data_inicio', 'data_fim', 
            'status', 'valor_fomento', 'coordenador', 'centro_lotacao', 'ods',
            # Campos apenas para escrita
            'coordenador_id', 'centro_lotacao_id', 'ods_ids', 'alunos_ids'
        ]

class RelatorioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Relatorio
        fields = '__all__'

# Primeiro, um serializer para exibir os dados de um Aluno já existente
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']

class AlunoDetailSerializer(serializers.ModelSerializer):
    """Serializer para LER (GET) os detalhes de um aluno."""
    usuario = UserSerializer()

    class Meta:
        model = UsuarioProfile
        exclude = ['perfil'] # Não precisamos mostrar o campo 'perfil', já sabemos que é aluno

# Agora, o serializer principal para CRIAR e ATUALIZAR um aluno
class AlunoSerializer(serializers.ModelSerializer):
    """Serializer para CRIAR (POST) e ATUALIZAR (PUT/PATCH) um Aluno."""
    # Campos do modelo User do Django
    username = serializers.CharField(source='usuario.username')
    password = serializers.CharField(write_only=True) # Apenas para escrita, nunca será retornado
    email = serializers.EmailField(source='usuario.email')
    first_name = serializers.CharField(source='usuario.first_name', required=False, allow_blank=True)
    last_name = serializers.CharField(source='usuario.last_name', required=False, allow_blank=True)

    class Meta:
        model = UsuarioProfile
        # Inclui os campos do UsuarioProfile e os que definimos acima
        fields = [
            'username', 'password', 'email', 'first_name', 'last_name',
            'cpf', 'telefone', 'endereco', 'centro_lotacao', 'regime_trabalho'
        ]

    @transaction.atomic # Garante que as operações no banco sejam atômicas
    def create(self, validated_data):
        # 1. Separar os dados do User e do Profile
        user_data = validated_data.pop('usuario')
        password = validated_data.pop('password')
        
        # O perfil é fixo para este endpoint
        validated_data['perfil'] = 'aluno'

        # 2. Criar o objeto User
        # Usamos create_user para garantir que a senha seja corretamente "hasheada"
        user = User.objects.create_user(
            username=user_data['username'],
            email=user_data.get('email', ''),
            password=password,
            first_name=user_data.get('first_name', ''),
            last_name=user_data.get('last_name', '')
        )

        # 3. Criar o objeto UsuarioProfile, ligando-o ao User recém-criado
        aluno_profile = UsuarioProfile.objects.create(usuario=user, **validated_data)
        
        return aluno_profile