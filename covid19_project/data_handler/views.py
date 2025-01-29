from django.shortcuts import render
from .models import CovidCountyData, CovidStateData, CovidUSData

# Create your views here.
def pre_dashboard(request):
    county_data = CovidCountyData.objects.all()[:100]  # Limit data for performance
    state_data = CovidStateData.objects.all()[:100]
    us_data = CovidUSData.objects.all()[:100]

    context = {
        'county_data': county_data,
        'state_data': state_data,
        'us_data': us_data
    }
    return render(request, 'pre_dashboard.html', context)