import requests
import csv
from io import StringIO
from django.shortcuts import render
from django.http import JsonResponse
from django.core.paginator import Paginator
from .models import CovidCountyData, CovidStateData, CovidUSData, CDCData
import logging
from .tasks import fetch_cdc_data  # Import the task

logger = logging.getLogger(__name__)

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
    """
    Fetches and displays CDC and WHO COVID-19 data.
    For CDC data, only state filtering is allowed (default is United States).
    WHO data filtering remains separate.
    """
    logger.info("Entering live_data_page view")
    # Default selected_state to 'united states' if not provided.
    selected_state = request.GET.get('selected_state', 'united states').lower()
    # Remove date filtering for CDC data (selected_date not used for CDC)
    # WHO filters remain unchanged.
    selected_country = request.GET.get('selected_country', '')
    selected_region = request.GET.get('selected_region', '')

    # Trigger the Celery task to fetch CDC data (using selected_state)
    if selected_state:
        fetch_cdc_data.delay(selected_state, '')

    # Retrieve CDC data from the database, filtered only by state.
    us_data = CDCData.objects.all()
    if selected_state:
        us_data = us_data.filter(state__iexact=selected_state)
    us_data = list(us_data.values('state', 'date', 'deaths_total'))
    # ----------------------
    # Global Data (WHO CSV)
    # ----------------------
    global_csv_url = "https://covid19.who.int/WHO-COVID-19-global-data.csv"
    try:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/90.0.4430.93 Safari/537.36'
            )
        }
        csv_response = requests.get(global_csv_url, headers=headers, timeout=10)
        csv_response.raise_for_status()
        csv_text = csv_response.text

        logger.info(f"Fetched WHO CSV: {len(csv_text)} characters")
        logger.debug(f"CSV content (first 100 chars): {csv_text[:100]}")
        logger.debug(f"WHO CSV Content-Type: {csv_response.headers.get('Content-Type')}")
        logger.debug(f"Final URL after redirects: {csv_response.url}")
        logger.debug(f"WHO CSV first 300 chars: {csv_text[:300]}")

        csv_file = StringIO(csv_text)
        reader = csv.DictReader(csv_file)
        logger.debug(f"CSV header fields: {reader.fieldnames}")

        global_data_raw = list(reader)
        logger.info(f"Parsed {len(global_data_raw)} rows from WHO CSV")
    except requests.RequestException as e:
        logger.error(f"Failed to fetch WHO CSV data: {e}")
        global_data_raw = []

    global_data = []
    # Normalize filter values for comparison.
    selected_country_norm = selected_country.strip().lower() if selected_country else ''
    selected_region_norm = selected_region.strip().lower() if selected_region else ''

    for row in global_data_raw:
        # Normalize CSV country/region values.
        country = row.get('Country', '').strip().lower()
        region = row.get('WHO_region', '').strip().lower() if row.get('WHO_region') else ''

        # Instead of exact equality, use substring matching.
        if selected_country_norm and selected_country_norm not in country:
            continue
        if selected_region_norm and selected_region_norm not in region:
            continue

        try:
            global_data.append({
                'date': row.get('Date_reported', '').strip(),
                'country': row.get('Country', '').strip(),
                'region': row.get('WHO_region', '').strip(),
                'cases_new': int(row.get('New_cases', 0)),
                'cases_total': int(row.get('Cumulative_cases', 0)),
                'deaths_new': int(row.get('New_deaths', 0)),
                'deaths_total': int(row.get('Cumulative_deaths', 0)),
                'recovered_new': 0,
                'recovered_total': 0,
            })
        except ValueError as ve:
            logger.error(f"Data conversion error for row {row}: {ve}")

    logger.info(f"Final global_data has {len(global_data)} entries")
    # Pagination (remains unchanged)
    entries_per_page = 10
    us_paginator = Paginator(us_data, entries_per_page)
    us_page = request.GET.get('us_page', 1)
    us_page_obj = us_paginator.get_page(us_page)

    global_paginator = Paginator(global_data, entries_per_page)
    global_page = request.GET.get('global_page', 1)
    global_page_obj = global_paginator.get_page(global_page)

    context = {
        'selected_state': selected_state,
        'selected_country': selected_country,
        'selected_region': selected_region,
        'us_data': us_page_obj,
        'global_data': global_page_obj,
        'us_pagination': {
            'has_next': us_page_obj.has_next(),
            'has_previous': us_page_obj.has_previous(),
            'current_page': us_page_obj.number,
            'total_pages': us_paginator.num_pages,
        },
        'global_pagination': {
            'has_next': global_page_obj.has_next(),
            'has_previous': global_page_obj.has_previous(),
            'current_page': global_page_obj.number,
            'total_pages': global_paginator.num_pages,
        },
        'us_pagination_range': us_paginator.page_range,
        'global_pagination_range': global_paginator.page_range,
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        response_data = {
            'us_data': {
                'object_list': list(us_page_obj),
                'has_next': us_page_obj.has_next(),
                'has_previous': us_page_obj.has_previous(),
                'current_page': us_page_obj.number,
                'total_pages': us_paginator.num_pages,
            },
            'global_data': {
                'object_list': list(global_page_obj),
                'has_next': global_page_obj.has_next(),
                'has_previous': global_page_obj.has_previous(),
                'current_page': global_page_obj.number,
                'total_pages': global_paginator.num_pages,
            },
        }
        return JsonResponse(response_data)

    return render(request, 'live_dashboard.html', context)