from rest_framework import viewsets
from django.shortcuts import render

def request_home(request):
    return render(request, 'home/home.html')

