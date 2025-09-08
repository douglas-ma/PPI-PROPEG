from django.urls import path
from . import views

urlpatterns = [
    path('coordenador/', views.login_view, {'tipo_usuario': 'coordenador'}, name='login_coordenador'),
    path('aluno/', views.login_view, {'tipo_usuario': 'aluno'}, name='login_aluno'),
    path('sair/', views.logout_view, name='logout'),
    path('esqueceu_senha/', views.esqueceu_senha, name='esqueceu_senha'),
    path('registrar/', views.registro_view, name='registrar'),
    path('perfil/', views.perfil_view, name='perfil'),
    path('perfil/editar/', views.perfil_editar_view, name='perfil_editar'),
    path('perfil/endereco/', views.endereco_editar_view, name='perfil_endereco'),
]