from django.shortcuts import render
from django.contrib.auth.decorators import login_required
# Create your views here.

# @login_required
def coord_dashboard(request):
    return render(request, "pagina_coordenador/dashboard.html", 
    {
        # "user": request.user
    })