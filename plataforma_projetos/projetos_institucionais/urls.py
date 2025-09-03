from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'projetos', views.ProjetoViewSet, basename='projeto')
router.register(r'centros-lotacao', views.CentroLotacaoViewSet, basename='centrolotacao')
router.register(r'ods', views.OdsViewSet, basename='ods')
router.register(r'relatorios', views.RelatorioViewSet, basename='relatorio')
router.register(r'alunos', views.AlunoViewSet, basename='aluno')
# Registre as outras ViewSets aqui

urlpatterns = [
    # path('', include(router.urls)),
    path('', views.request_home, name='home'),
]