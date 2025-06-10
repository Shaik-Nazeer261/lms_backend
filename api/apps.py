from django.apps import AppConfig
from django.conf import settings
from django.db import IntegrityError
import os, json

class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        from django.contrib.auth import get_user_model
        from .models import Category, SubCategory
        from django.core.exceptions import ObjectDoesNotExist

        # 🔹 Load categories and subcategories from JSON
        file_path = os.path.join(settings.BASE_DIR, 'api', 'seed_data', 'categories.json')
        if os.path.exists(file_path):
            with open(file_path) as f:
                data = json.load(f)
                for cat_name, subcats in data.items():
                    category, _ = Category.objects.get_or_create(name=cat_name)
                    for subcat in subcats:
                        try:
                            SubCategory.objects.get_or_create(category=category, name=subcat)
                        except IntegrityError:
                            continue
            print("✅ Categories and subcategories loaded successfully.")

        # 🔹 Create default admin user
        User = get_user_model()
        admin_email = "admin@lms.com"
        admin_password = "admin123"

        try:
            if not User.objects.filter(email=admin_email).exists():
                User.objects.create_superuser(
                    username="admin",
                    email=admin_email,
                    password=admin_password,
                    role="admin",
                    first_name="Admin",
                    last_name="User"
                )
                print("✅ Default admin user created.")
            else:
                print("ℹ️ Admin user already exists.")
        except Exception as e:
            print("❌ Error creating default admin:", e)

