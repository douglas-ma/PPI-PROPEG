from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # path('', include(router.urls)),
    path('', views.request_home, name='home'),
    path('telaprincipal/', views.tela_principal, name='tela_principal'),

    path('aluno/projetos/meusprojetos/', views.aluno_projeto_dashboard, name='aluno_meus_projetos'),

    path('projetos/', views.projeto_listar, name='projeto_listar'),
    path('projetos/<int:pk>/', views.projeto_detalhe, name='projeto_detalhe'),
    path('projetos/criar/', views.ProjetoCreateWizard.as_view(), name='projeto_criar'),
    path('projetos/<int:pk>/editar/', views.projeto_editar, name='projeto_editar'),
    path('projetos/<int:pk>/deletar/', views.projeto_deletar, name='projeto_deletar'),
    path('projetos/meusprojetos/', views.projeto_dashboard, name='projeto_dashboard'),

    path('gestor/dashboard/', views.gestor_dashboard, name='gestor_dashboard'),
    path('gestor/usuarios/', views.gerenciar_usuarios, name='gerenciar_usuarios'),
    path('gestor/usuarios/<int:pk>/', views.usuario_detalhe, name='usuario_detalhe'),
    path('gestor/usuarios/<int:pk>/editar/', views.usuario_editar, name='usuario_editar'),
    path('gestor/usuarios/<int:pk>/deletar/', views.usuario_deletar, name='usuario_deletar'),

    path('gestor/projetos/historico/', views.historico_projetos, name='historico_projetos'),

    path('projetos/<int:pk>/aprovar/', views.aprovar_projeto, name='aprovar_projeto'),
    path('projetos/<int:pk>/reprovar/', views.reprovar_projeto, name='reprovar_projeto'),
    path('projetos/<int:pk>/anexar-comprovante/', views.anexar_comprovante, name='anexar_comprovante'),
]   

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)