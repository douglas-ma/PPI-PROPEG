from django.db import models
from django.contrib.auth import authenticate, login, get_user_model

# Create your models here.
User = get_user_model()
User.get_full_name()