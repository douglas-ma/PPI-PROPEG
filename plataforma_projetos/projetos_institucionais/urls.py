from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # path('', include(router.urls)),
    path('', views.request_home, name='home'),
    path('telaprincipal/', views.tela_principal, name='tela_principal'),

    path('perfil/<int:pk>/visualizar/', views.visualizar_perfil, name='visualizar_perfil'),
    path('aluno/projetos/meusprojetos/', views.aluno_projeto_dashboard, name='aluno_meus_projetos'),
    path('notificacoes/', views.lista_notificacoes, name='lista_notificacoes'),
    path('editais/abertos/', views.listar_editais_abertos, name='listar_editais_abertos'),
    path('projetos/relatorios/selecionar/', views.listar_projetos_para_relatorio, name='relatorio_lista_projetos'),

    path('projetos/', views.projeto_listar, name='projeto_listar'),
    path('projetos/<int:pk>/', views.projeto_detalhe, name='projeto_detalhe'),
    path('projetos/criar/', views.ProjetoCreateWizard.as_view(), name='projeto_criar'),
    path('projetos/<int:pk>/editar/', views.ProjetoUpdateWizard.as_view(), name='projeto_editar'),
    path('projetos/<int:pk>/deletar/', views.projeto_deletar, name='projeto_deletar'),
    path('projetos/meusprojetos/', views.projeto_dashboard, name='projeto_dashboard'),

    path('gestor/dashboard/', views.gestor_dashboard, name='gestor_dashboard'),
    path('gestor/usuarios/', views.gerenciar_usuarios, name='gerenciar_usuarios'),
    path('gestor/usuarios/<int:pk>/', views.usuario_detalhe, name='usuario_detalhe'),
    path('gestor/usuarios/<int:pk>/editar/', views.usuario_editar, name='usuario_editar'),
    path('gestor/usuarios/<int:pk>/deletar/', views.usuario_deletar, name='usuario_deletar'),
    path('gestor/relatorios/', views.listar_relatorios_gestor, name='gestor_relatorios'),
    path('gestor/projetos/historico/', views.historico_projetos, name='historico_projetos'),
    path('gestor/editais/', views.gestor_listar_editais, name='gestor_listar_editais'),
    path('gestor/editais/novo/', views.gestor_criar_edital, name='gestor_criar_edital'),
    path('gestor/editais/<int:pk>/editar/', views.gestor_editar_edital, name='gestor_editar_edital'),
    path('gestor/editais/<int:pk>/deletar/', views.gestor_deletar_edital, name='gestor_deletar_edital'),

    path('projetos/<int:pk>/aprovar/', views.aprovar_projeto, name='aprovar_projeto'),
    path('projetos/<int:pk>/reprovar/', views.reprovar_projeto, name='reprovar_projeto'),
    path('projetos/<int:pk>/adicionar_anexo/', views.adicionar_anexo, name='adicionar_anexo'),
    path('projetos/<int:pk>/anexar-comprovante/', views.anexar_comprovante, name='anexar_comprovante'),
    path('projetos/<int:pk>/anexos/', views.projeto_anexos, name='projeto_anexos'),
    path('projetos/<int:pk>/iniciar/', views.iniciar_projeto, name='iniciar_projeto'),
    path('projetos/<int:pk>/encerrar/', views.encerrar_projeto, name='encerrar_projeto'),
    path('projetos/<int:pk>/encaminhar-conselho/', views.encaminhar_para_conselho, name='encaminhar_para_conselho'),
    path('projetos/anexo/<int:anexo_id>/deletar/', views.deletar_anexo, name='deletar_anexo'),
    path('projetos/relatorios/selecionar/', views.listar_projetos_para_relatorio, name='relatorio_lista_projetos'),
    path('projetos/<int:pk>/criar-relatorio/', views.criar_relatorio, name='relatorio_criar'),
    path('ajax/load-cursos/', views.load_cursos, name='ajax_load_cursos'),
]   

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)