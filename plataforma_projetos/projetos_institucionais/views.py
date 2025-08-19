from rest_framework import viewsets
from .models import Projeto, Relatorio, CentroLotacao, ODS, UsuarioProfile
from .serializers import ProjetoSerializer, RelatorioSerializer, CentroLotacaoSerializer, OdsSerializer, AlunoSerializer, AlunoDetailSerializer


class ProjetoViewSet(viewsets.ModelViewSet):
    """
    Endpoint da API para gerenciar Projetos.
    """
    queryset = Projeto.objects.all()
    serializer_class = ProjetoSerializer

class CentroLotacaoViewSet(viewsets.ModelViewSet):
    """
    Endpoint da API para gerenciar Centros de Lotação.
    """
    queryset = CentroLotacao.objects.all()
    serializer_class = CentroLotacaoSerializer

class OdsViewSet(viewsets.ModelViewSet):
    """
    Endpoint da API para gerenciar ODS.
    """
    queryset = ODS.objects.all()
    serializer_class = OdsSerializer

# Crie ViewSets para os outros modelos conforme a necessidade...
# Por exemplo, para Relatórios:
class RelatorioViewSet(viewsets.ModelViewSet):
    queryset = Relatorio.objects.all()
    serializer_class = RelatorioSerializer


class AlunoViewSet(viewsets.ModelViewSet):
    """
    Endpoint da API que permite o CRUD de usuários do tipo Aluno.
    """
    # O queryset garante que este endpoint SÓ vai interagir com perfis de aluno
    queryset = UsuarioProfile.objects.filter(perfil='aluno')

    # Usamos serializers diferentes para ações diferentes
    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return AlunoDetailSerializer # Para GET, mostra mais detalhes
        return AlunoSerializer # Para POST, PUT, PATCH, DELETE