from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('sair/', views.logout_view, name='logout'),
    path('esqueceu_senha/', views.esqueceu_senha, name='esqueceu_senha'),
    path('registrar/', views.registro_view, name='registrar'),
    path('perfil/', views.perfil_view, name='perfil'),
    path('perfil/editar/', views.perfil_editar_view, name='perfil_editar'),
    path('perfil/endereco/', views.endereco_editar_view, name='perfil_endereco'),
]