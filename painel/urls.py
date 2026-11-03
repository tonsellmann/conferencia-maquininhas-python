from django.urls import path

from . import views

app_name = "painel"
urlpatterns = [
    path("", views.lista, name="lista"),
    path("saude", views.saude, name="saude"),
    path("conferencias/nova", views.nova, name="nova"),
    path("conferencias/<int:pk>", views.detalhe, name="detalhe"),
]
