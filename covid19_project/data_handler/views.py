import requests
import csv
from io import StringIO
from django.shortcuts import render
from django.http import JsonResponse
from django.core.paginator import Paginator
from .models import CovidCountyData, CovidStateData, CovidUSData, CDCData, WHOData
import logging
from django.core.cache import cache
from .tasks import fetch_cdc_data, fetch_who_data

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


def early_data(request):
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
    return render(request, 'early_data.html', context)

def format_chart_data(queryset, label_prefix="", cases_label="Cases", deaths_label="Deaths"):
    """Helper function to format data for Chart.js"""
    if not queryset: # Check if queryset is empty or None
        return None

    try:
        labels = [item.date.strftime('%Y-%m-%d') for item in queryset]
        cases_data = [item.cases for item in queryset]
        deaths_data = [item.deaths for item in queryset]

        return {
            'labels': labels,
            'datasets': [
                {
                    'label': f'{label_prefix} {cases_label}',
                    'data': cases_data,
                    'borderColor': 'rgb(75, 192, 192)',
                    'tension': 0.1
                },
                {
                    'label': f'{label_prefix} {deaths_label}',
                    'data': deaths_data,
                    'borderColor': 'rgb(255, 99, 132)',
                    'tension': 0.1
                }
            ]
        }
    except AttributeError:
        # Handle cases where items might not have expected attributes (e.g., date, cases)
        print(f"Error formatting chart data for prefix: {label_prefix}. Queryset might be malformed.")
        return None


def chart_data_api(request):
    """
    API endpoint to provide data formatted for Chart.js.
    Accepts optional 'state' and 'county' GET parameters.
    """
    state_name = request.GET.get('state', None)
    county_name = request.GET.get('county', None)

    chart_data = None
    error_message = None
    status_code = 200

    try:
        if state_name and county_name:
            # County Data
            queryset = CovidCountyData.objects.filter(
                state__iexact=state_name, # Case-insensitive match
                county__iexact=county_name # Case-insensitive match
            ).order_by('date')
            if queryset.exists():
                label = f"{county_name.title()}, {state_name.title()}"
                chart_data = format_chart_data(queryset, label_prefix=label)
            else:
                error_message = f"No data found for County: {county_name}, State: {state_name}"
                status_code = 404

        elif state_name:
            # State Data
            queryset = CovidStateData.objects.filter(
                state__iexact=state_name # Case-insensitive match
            ).order_by('date')
            if queryset.exists():
                 label = f"{state_name.title()}"
                 chart_data = format_chart_data(queryset, label_prefix=label)
            else:
                error_message = f"No data found for State: {state_name}"
                status_code = 404

        else:
            # US Data (Default)
            queryset = CovidUSData.objects.all().order_by('date')
            if queryset.exists():
                 chart_data = format_chart_data(queryset, label_prefix="US")
            else:
                error_message = "No US data found"
                status_code = 404

        if chart_data:
            return JsonResponse(chart_data)
        else:
            # Ensure error message is set if chart_data is None after processing
            if not error_message:
                error_message = "Data formatting error or empty queryset."
                status_code = 500 # Internal error if formatting fails
            return JsonResponse({'error': error_message}, status=status_code)

    except Exception as e:
        # Catch unexpected errors during query or formatting
        print(f"Unexpected error in chart_data_api: {e}")
        return JsonResponse({'error': 'An unexpected server error occurred.'}, status=500)

def get_states_api(request):
    try:
        # Get distinct state names, order them, ignore null/empty
        states = CovidStateData.objects.exclude(state__isnull=True).exclude(state__exact='').order_by('state').values_list('state', flat=True).distinct()
        return JsonResponse(list(states), safe=False) # safe=False needed for list response
    except Exception as e:
        print(f"Error in get_states_api: {e}")
        return JsonResponse({'error': 'Could not retrieve states.'}, status=500)


# Add view to get counties for a specific state
def get_counties_api(request):
    state_name = request.GET.get('state', None)
    if not state_name:
        return JsonResponse({'error': 'State parameter is required.'}, status=400)
    try:
        # Get distinct county names for the state, order them, ignore null/empty
        counties = CovidCountyData.objects.filter(state__iexact=state_name).exclude(county__isnull=True).exclude(county__exact='').order_by('county').values_list('county', flat=True).distinct()
        if not counties:
             # Return empty list if state exists but has no counties listed (or state doesn't exist)
             return JsonResponse([], safe=False)
        return JsonResponse(list(counties), safe=False)
    except Exception as e:
         print(f"Error in get_counties_api for state {state_name}: {e}")
         return JsonResponse({'error': 'Could not retrieve counties.'}, status=500)


def live_data(request):
    """
    Fetches and displays CDC (from DB) and WHO (from DB) COVID-19 data.
    Handles filtering and AJAX pagination updates for each dataset independently.
    Triggers background tasks if data is missing on initial load.
    """
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    logger.info(f"Entering live_data_page view. AJAX: {is_ajax}")

    # --- Parameters ---
    selected_state = request.GET.get('selected_state', 'united states').lower()
    selected_country = request.GET.get('selected_country', '') # Keep original case for display
    selected_region = request.GET.get('selected_region', '')
    us_page_num = request.GET.get('us_page', 1)
    global_page_num = request.GET.get('global_page', 1)
    ajax_target = request.GET.get('target') if is_ajax else None

    # --- Initialize Data Structures ---
    us_data_page_obj = None
    global_data_page_obj = None
    who_country_list = []
    cdc_data_exists = False
    who_data_exists = False # Flag to check if WHO data exists at all
    cdc_task_error = None
    context = {} # Initialize context dictionary

    # --- CDC Data Processing (from DB) ---
    if not ajax_target or ajax_target == 'cdc':
        logger.info(f"Processing CDC data for state: {selected_state}")
        # QuerySet is ordered by Meta class: ordering = ['-date', 'state']
        us_queryset = CDCData.objects.filter(state__iexact=selected_state)

        cdc_data_exists = us_queryset.exists()
        logger.info(f"CDC Query for {selected_state} returned count: {us_queryset.count()}. Exists: {cdc_data_exists}")

        if not cdc_data_exists:
            cache_key = f"cdc_task_error_{selected_state}"
            cdc_task_error = cache.get(cache_key)
            logger.info(f"Checked cache for CDC task error ({cache_key}): {cdc_task_error}")
            # Trigger task ONLY on initial load if data doesn't exist
            if selected_state and not is_ajax:
                logger.info(f"Queueing fetch_cdc_data task for {selected_state} (initial load, data missing).")
                fetch_cdc_data.delay(selected_state, '')
        elif is_ajax and ajax_target == 'cdc':
             logger.info(f"AJAX poll for CDC {selected_state}: Data exists.")


        # Paginate the CDC QuerySet
        cdc_paginator = Paginator(us_queryset, 10) # 10 items per page
        try:
            us_data_page_obj = cdc_paginator.page(us_page_num)
        except PageNotAnInteger:
            us_data_page_obj = cdc_paginator.page(1)
        except EmptyPage:
            us_data_page_obj = cdc_paginator.page(cdc_paginator.num_pages)
        logger.info(f"CDC Pagination: Page {us_data_page_obj.number} of {cdc_paginator.num_pages}")


    # --- WHO Data Processing (from DB) ---
    if not ajax_target or ajax_target == 'who':
        logger.info(f"Processing WHO data from DB for country: '{selected_country}', region: '{selected_region}'")
        # QuerySet is ordered by Meta class: ordering = ['-date_reported', 'country']
        who_queryset = WHOData.objects.all()

        # Check if *any* WHO data exists (only need to do this once)
        # We do this before filtering to know if the table is populated at all
        if not is_ajax: # Only check on initial load
             who_data_exists = who_queryset.exists()
             if not who_data_exists:
                  logger.warning("WHOData table appears empty. Queueing initial fetch_who_data task.")
                  fetch_who_data.delay() # Trigger initial WHO data fetch if table is empty
             else:
                  logger.info("WHOData table has data.")

        # Apply filters
        if selected_country:
             # Use exact, case-insensitive match
             who_queryset = who_queryset.filter(country__iexact=selected_country)
        if selected_region:
             # Use case-insensitive contains
             who_queryset = who_queryset.filter(who_region__icontains=selected_region)

        # Paginate the WHO QuerySet
        who_paginator = Paginator(who_queryset, 10) # 10 items per page
        try:
            global_data_page_obj = who_paginator.page(global_page_num)
        except PageNotAnInteger:
            global_data_page_obj = who_paginator.page(1)
        except EmptyPage:
            global_data_page_obj = who_paginator.page(who_paginator.num_pages)
        logger.info(f"WHO DB Pagination: Page {global_data_page_obj.number} of {who_paginator.num_pages}")


    # --- Get Country List for Dropdown (Only on initial load & if data exists) ---
    if not is_ajax and who_data_exists:
         # Get distinct country names from the model, order them
         who_country_list = list(WHOData.objects.order_by('country').values_list('country', flat=True).distinct())
         logger.info(f"Generated WHO country list from DB with {len(who_country_list)} entries.")


    # --- Prepare response ---
    if is_ajax:
        response_data = {}
        # Prepare CDC data for JSON if requested and available
        if ajax_target == 'cdc' and us_data_page_obj:
            # Select only necessary fields for the template
            object_list = list(us_data_page_obj.object_list.values('state', 'date', 'deaths_total'))
            # Convert Date objects to YYYY-MM-DD strings for JSON
            for item in object_list:
                 if item['date']: item['date'] = item['date'].strftime('%Y-%m-%d')
                 # data_as_of is not currently displayed, but would need formatting too if added

            response_data['us_data'] = {
                'object_list': object_list,
                'current_page': us_data_page_obj.number,
                'total_pages': us_data_page_obj.paginator.num_pages,
                'has_previous': us_data_page_obj.has_previous(),
                'has_next': us_data_page_obj.has_next(),
                'cdc_data_exists': cdc_data_exists, # Still useful for the polling script
            }
        # Prepare WHO data for JSON if requested and available
        elif ajax_target == 'who' and global_data_page_obj:
             # Select only necessary fields for the template
             object_list = list(global_data_page_obj.object_list.values(
                 'date_reported', 'country', 'who_region', 'new_cases',
                 'cumulative_cases', 'new_deaths', 'cumulative_deaths'
             ))
             # Convert Date objects to YYYY-MM-DD strings for JSON
             for item in object_list:
                 if item['date_reported']: item['date_reported'] = item['date_reported'].strftime('%Y-%m-%d')

             response_data['global_data'] = {
                'object_list': object_list,
                'current_page': global_data_page_obj.number,
                'total_pages': global_data_page_obj.paginator.num_pages,
                'has_previous': global_data_page_obj.has_previous(),
                'has_next': global_data_page_obj.has_next(),
            }
        else:
             logger.warning(f"AJAX request received without valid target or data for target: {ajax_target}")
             # Return empty dict or specific error structure if needed

        logger.info(f"Returning AJAX response for target: {ajax_target}")
        return JsonResponse(response_data)

    else: # Full page load
        context = {
            'selected_state': selected_state,
            'selected_country': selected_country,
            'selected_region': selected_region,
            'us_data': us_data_page_obj, # Pass page object
            'global_data': global_data_page_obj, # Pass page object
            'cdc_data_exists': cdc_data_exists,
            'cdc_task_error': cdc_task_error,
            'who_country_list': who_country_list, # Pass country list
            # The template accesses pagination info directly from us_data and global_data page objects
        }
        logger.info("Rendering full HTML template.")
        return render(request, 'live_data.html', context)

