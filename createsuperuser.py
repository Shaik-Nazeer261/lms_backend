import os
import django
from django.contrib.auth import get_user_model

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AgriClinic.settings')
django.setup()

# Get the custom User model
User = get_user_model()

# Superuser credentials
username = "super"
password = "super"
email = "super@gmail.com"
role = "admin"

# Check by email (or username) instead of phone_number
if not User.objects.filter(email=email).exists():
    User.objects.create_superuser(
        username=username,
        email=email,
        password=password,
        role=role
    )
    print("✅ Superuser created.")
else:
    print("⚠️ Superuser already exists.")
