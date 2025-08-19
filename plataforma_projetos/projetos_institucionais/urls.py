from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjetoViewSet, CentroLotacaoViewSet, OdsViewSet, RelatorioViewSet, AlunoViewSet

router = DefaultRouter()
router.register(r'projetos', ProjetoViewSet, basename='projeto')
router.register(r'centros-lotacao', CentroLotacaoViewSet, basename='centrolotacao')
router.register(r'ods', OdsViewSet, basename='ods')
router.register(r'relatorios', RelatorioViewSet, basename='relatorio')
router.register(r'alunos', AlunoViewSet, basename='aluno')
# Registre as outras ViewSets aqui

urlpatterns = [
    path('', include(router.urls)),
]