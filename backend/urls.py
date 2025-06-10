from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def health_check(request):
    return JsonResponse({'status': 'ok'})
urlpatterns = [
    path('', health_check),  # This fixes the 404 on /
    path('admin/', admin.site.urls),
    path('api/', include('api.urls'))
]
