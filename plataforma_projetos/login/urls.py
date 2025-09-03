from django.urls import path
from . import views

urlpatterns = [
    path('<str:tipo_usuario>', views.login_view, name='login'),
    path('esqueceu_senha/', views.esqueceu_senha, name='esqueceu_senha'),
    path('registrar/', views.registrar, name='registrar')
]