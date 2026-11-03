from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Conferência das maquininhas"
admin.site.site_title = "Conferência das maquininhas"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("painel.urls")),
]
