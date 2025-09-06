from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # path('', include(router.urls)),
    path('', views.request_home, name='home'),
    path('projetos/', views.projeto_listar, name='projeto_listar'),
    path('projetos/<int:pk>/', views.projeto_detalhe, name='projeto_detalhe'),
    path('projetos/novo/', views.projeto_criar, name='projeto_criar'),
    path('projetos/<int:pk>/editar/', views.projeto_editar, name='projeto_editar'),
    path('projetos/<int:pk>/deletar/', views.projeto_deletar, name='projeto_deletar'),
    path('projetos/meusprojetos/', views.projeto_dashboard, name='projeto_dashboard'),
]   

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)