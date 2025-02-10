from django.urls import path
from django.views.generic import TemplateView
from .views import pre_dashboard, get_paginated_data

urlpatterns = [
    path('', TemplateView.as_view(template_name='main.html'), name='main'),  # renders main page
    path('pandemic/', pre_dashboard, name='pandemic_data_page'),  # displays early data
    path('live/', TemplateView.as_view(template_name='live_data.html'), name='live_data_page'),  # display live data
    path('covid-dashboard/', pre_dashboard, name='covid_dashboard'),
    path('api/data/', get_paginated_data, name='get_paginated_data'),
]


