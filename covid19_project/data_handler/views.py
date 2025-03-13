import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.core.paginator import Paginator
from .models import CovidCountyData, CovidStateData, CovidUSData

def get_paginated_data(request):
    # Get the page numbers from the request (default to 1)
    county_page = int(request.GET.get('county_page', 1))
    state_page = int(request.GET.get('state_page', 1))
    us_page = int(request.GET.get('us_page', 1))

    # Number of entries per page for each dataset
    entries_per_page = 10

    # Query all data and order by date (change ordering if desired)
    county_queryset = CovidCountyData.objects.all().order_by('date')
    state_queryset = CovidStateData.objects.all().order_by('date')
    us_queryset = CovidUSData.objects.all().order_by('date')

    # Create individual paginators
    county_paginator = Paginator(county_queryset, entries_per_page)
    state_paginator = Paginator(state_queryset, entries_per_page)
    us_paginator = Paginator(us_queryset, entries_per_page)

    # Get each requested page
    county_page_obj = county_paginator.get_page(county_page)
    state_page_obj = state_paginator.get_page(state_page)
    us_page_obj = us_paginator.get_page(us_page)

    # Convert each set of objects to a list of dictionaries
    county_data = list(county_page_obj.object_list.values())
    state_data = list(state_page_obj.object_list.values())
    us_data = list(us_page_obj.object_list.values())

    # Build and return a JSON response
    return JsonResponse({
        'county_data': county_data,
        'county_pagination': {
            'has_next': county_page_obj.has_next(),
            'has_previous': county_page_obj.has_previous(),
            'current_page': county_page_obj.number,
            'total_pages': county_paginator.num_pages,
        },
        'state_data': state_data,
        'state_pagination': {
            'has_next': state_page_obj.has_next(),
            'has_previous': state_page_obj.has_previous(),
            'current_page': state_page_obj.number,
            'total_pages': state_paginator.num_pages,
        },
        'us_data': us_data,
        'us_pagination': {
            'has_next': us_page_obj.has_next(),
            'has_previous': us_page_obj.has_previous(),
            'current_page': us_page_obj.number,
            'total_pages': us_paginator.num_pages,
        },
    })


def early_dashboard(request):
    # Separate page numbers for each dataset
    county_page = int(request.GET.get('county_page', 1))
    state_page = int(request.GET.get('state_page', 1))
    us_page = int(request.GET.get('us_page', 1))

    # Fetch and order the data
    county_list = CovidCountyData.objects.all().order_by('date')
    state_list = CovidStateData.objects.all().order_by('date')
    us_list = CovidUSData.objects.all().order_by('date')

    # Paginator for each dataset
    county_paginator = Paginator(county_list, 10)
    state_paginator = Paginator(state_list, 10)
    us_paginator = Paginator(us_list, 10)

    # Get pages
    county_data = county_paginator.get_page(county_page)
    state_data = state_paginator.get_page(state_page)
    us_data = us_paginator.get_page(us_page)

    context = {
        'county_data': county_data,
        'state_data': state_data,
        'us_data': us_data,
    }
    return render(request, 'early_dashboard.html', context)

def live_dashboard(request):
    # API endpoint and key
    API_URL = "https://api.api-ninjas.com/v1/covid19"
    API_KEY = "xwxWr+NMRgjCiE6KfSiWWA==HYSKdpGFBTtWvOes"

    # Get filter parameters
    selected_date = request.GET.get('date', '')
    selected_country = request.GET.get('country', '')
    selected_region = request.GET.get('region', '')
    selected_county = request.GET.get('county', '')

    # Build API query parameters
    params = {}
    if selected_date:i
        params['date'] = selected_date
    if selected_country:
        params['country'] = selected_country
    if selected_region:
        params['region'] = selected_region
    if selected_county and selected_country.lower() == 'united states':
        params['county'] = selected_county

    # Fetch data from the API
    try:
        headers = {'X-Api-Key': API_KEY}
        response = requests.get(API_URL, headers=headers, params=params)
        response.raise_for_status()
        api_data = response.json()
    except requests.RequestException as e:
        print(f"API request failed: {e}")
        api_data = []

    # Debugging: Print API response details
    if api_data:
        print(f"API returned {len(api_data)} items")
        print(api_data)
    else:
        print("API returned no data")

    # Initialize data lists
    national_data = []
    state_data = []
    county_data = []

    # Process API response based on selection
    if api_data:
        if selected_county:
            # County-level data (US only)
            for county_obj in api_data:
                for date_str, stats in county_obj.get('cases', {}).items():
                    row = {
                        'country': selected_country,
                        'region': selected_region,
                        'county': selected_county,
                        'date': date_str,
                        'cases_total': stats.get('total', 0),
                        'cases_new': stats.get('new', 0),
                        'deaths_total': county_obj.get('deaths', {}).get(date_str, {}).get('total', 0),
                        'deaths_new': county_obj.get('deaths', {}).get(date_str, {}).get('new', 0),
                        'recovered_total': 0,
                        'recovered_new': 0,
                    }
                    county_data.append(row)
        elif selected_region:
            # Region-level data (e.g., state/province)
            for region_obj in api_data:
                for date_str, stats in region_obj.get('cases', {}).items():
                    row = {
                        'country': selected_country,
                        'region': selected_region,
                        'date': date_str,
                        'cases_total': stats.get('total', 0),
                        'cases_new': stats.get('new', 0),
                        'deaths_total': region_obj.get('deaths', {}).get(date_str, {}).get('total', 0),
                        'deaths_new': region_obj.get('deaths', {}).get(date_str, {}).get('new', 0),
                        'recovered_total': 0,
                        'recovered_new': 0,
                    }
                    state_data.append(row)
                # Include counties if present (e.g., for US states)
                for county in region_obj.get('counties', []):
                    county_name = county.get('county', '')
                    for date_str, stats in county.get('cases', {}).items():
                        row = {
                            'country': selected_country,
                            'region': selected_region,
                            'county': county_name,
                            'date': date_str,
                            'cases_total': stats.get('total', 0),
                            'cases_new': stats.get('new', 0),
                            'deaths_total': county.get('deaths', {}).get(date_str, {}).get('total', 0),
                            'deaths_new': county.get('deaths', {}).get(date_str, {}).get('new', 0),
                            'recovered_total': 0,
                            'recovered_new': 0,
                        }
                        county_data.append(row)
        else:
            # Country-level data (national and regions)
            for country_data in api_data:
                country_name = country_data.get('country', '')
                # National data
                for date_str, stats in country_data.get('cases', {}).items():
                    row = {
                        'country': country_name,
                        'region': 'National',
                        'date': date_str,
                        'cases_total': stats.get('total', 0),
                        'cases_new': stats.get('new', 0),
                        'deaths_total': country_data.get('deaths', {}).get(date_str, {}).get('total', 0),
                        'deaths_new': country_data.get('deaths', {}).get(date_str, {}).get('new', 0),
                        'recovered_total': 0,
                        'recovered_new': 0,
                    }
                    national_data.append(row)
                # State/province data
                for region in country_data.get('regions', []):
                    region_name = region.get('region', '')
                    for date_str, stats in region.get('cases', {}).items():
                        row = {
                            'country': country_name,
                            'region': region_name,
                            'date': date_str,
                            'cases_total': stats.get('total', 0),
                            'cases_new': stats.get('new', 0),
                            'deaths_total': region.get('deaths', {}).get(date_str, {}).get('total', 0),
                            'deaths_new': region.get('deaths', {}).get(date_str, {}).get('new', 0),
                            'recovered_total': 0,
                            'recovered_new': 0,
                        }
                        state_data.append(row)
                    # County data (if available, e.g., US)
                    for county in region.get('counties', []):
                        county_name = county.get('county', '')
                        for date_str, stats in county.get('cases', {}).items():
                            row = {
                                'country': country_name,
                                'region': region_name,
                                'county': county_name,
                                'date': date_str,
                                'cases_total': stats.get('total', 0),
                                'cases_new': stats.get('new', 0),
                                'deaths_total': county.get('deaths', {}).get(date_str, {}).get('total', 0),
                                'deaths_new': county.get('deaths', {}).get(date_str, {}).get('new', 0),
                                'recovered_total': 0,
                                'recovered_new': 0,
                            }
                            county_data.append(row)

    # Pagination (assuming this is part of your full code)
    entries_per_page = 20
    national_paginator = Paginator(national_data, entries_per_page)
    state_paginator = Paginator(state_data, entries_per_page)
    county_paginator = Paginator(county_data, entries_per_page)

    national_page = int(request.GET.get('national_page', 1))
    state_page = int(request.GET.get('state_page', 1))
    county_page = int(request.GET.get('county_page', 1))

    national_page_obj = national_paginator.get_page(national_page)
    state_page_obj = state_paginator.get_page(state_page)
    county_page_obj = county_paginator.get_page(county_page)

    # Hardcoded countries list
    countries_list = ['United States', 'India', 'Brazil', 'France', 'Germany']

    # Context
    context = {
        'national_data': national_page_obj,
        'state_data': state_page_obj,
        'county_data': county_page_obj,
        'countries_list': countries_list,
        'selected_date': selected_date,
        'selected_country': selected_country,
        'selected_region': selected_region,
        'selected_county': selected_county,
        'national_pagination': {
            'has_next': national_page_obj.has_next(),
            'has_previous': national_page_obj.has_previous(),
            'current_page': national_page_obj.number,
            'total_pages': national_paginator.num_pages,
        },
        'state_pagination': {
            'has_next': state_page_obj.has_next(),
            'has_previous': state_page_obj.has_previous(),
            'current_page': state_page_obj.number,
            'total_pages': state_paginator.num_pages,
        },
        'county_pagination': {
            'has_next': county_page_obj.has_next(),
            'has_previous': county_page_obj.has_previous(),
            'current_page': county_page_obj.number,
            'total_pages': county_paginator.num_pages,
        },
        'error': 'No data available from API' if not (national_data or state_data or county_data) else None,
    }
    return render(request, 'live_dashboard.html', context)