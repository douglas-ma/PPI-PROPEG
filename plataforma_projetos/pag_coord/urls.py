from django.urls import path

from . import views

urlpatterns = [
    path("", views.coord_dashboard, name="pag_coord_dashboard")
]