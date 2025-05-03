from django.urls import path
from django.views.generic import TemplateView
from .views import early_data, get_paginated_data, live_data
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', TemplateView.as_view(template_name='main.html'), name='main'),  # renders main page
    path('early_pandemic/', early_data, name='early_pandemic_data_page'),  # displays early data
    path('live_data/', live_data, name='live_data_page'),  # display live data
    path('api/chart_data/', views.chart_data_api, name='chart_data_api'),
    path('api/get_states/', views.get_states_api, name='get_states_api'),
    path('api/get_counties/', views.get_counties_api, name='get_counties_api'),
    path('api/data/', get_paginated_data, name='get_paginated_data'),
]



