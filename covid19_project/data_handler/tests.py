from datetime import date
from io import StringIO
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .management.commands.import_historical_data import (
    Command as ImportHistoricalDataCommand,
)
from .models import CovidCountyData, CovidStateData, CovidUSData


class PageTests(TestCase):
    """Basic checks for the application's main pages."""

    def test_landing_page_loads(self):
        response = self.client.get(reverse("main"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "main.html")

    def test_historical_page_loads(self):
        response = self.client.get(reverse("early_pandemic_data_page"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "early_data.html")

    @patch("data_handler.views.fetch_who_data.delay")
    @patch("data_handler.views.fetch_cdc_deaths_from_api_weekly.delay")
    def test_live_page_loads_without_running_background_tasks(
        self,
        mock_cdc_task,
        mock_who_task,
    ):
        # Celery calls are mocked so the test does not need Redis or internet access.
        response = self.client.get(reverse("live_data_page"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "live_data.html")
        mock_cdc_task.assert_called_once_with("united states")
        mock_who_task.assert_called_once_with()


class ChartDataApiTests(TestCase):
    """Checks the JSON data used to build the historical charts."""

    def test_national_chart_returns_cases_and_deaths(self):
        CovidUSData.objects.create(
            date=date(2020, 1, 21),
            cases=1,
            deaths=0,
        )
        CovidUSData.objects.create(
            date=date(2020, 1, 22),
            cases=2,
            deaths=1,
        )

        response = self.client.get(reverse("chart_data_api"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "labels": ["2020-01-21", "2020-01-22"],
                "datasets": [
                    {
                        "label": "US Cases",
                        "data": [1, 2],
                        "borderColor": "rgb(75, 192, 192)",
                        "tension": 0.1,
                    },
                    {
                        "label": "US Deaths",
                        "data": [0, 1],
                        "borderColor": "rgb(255, 99, 132)",
                        "tension": 0.1,
                    },
                ],
            },
        )

    def test_state_chart_only_returns_selected_state(self):
        # A second state makes sure the API is actually applying the filter.
        CovidStateData.objects.create(
            date=date(2020, 1, 21),
            state="California",
            fips=6,
            cases=10,
            deaths=1,
        )
        CovidStateData.objects.create(
            date=date(2020, 1, 21),
            state="Texas",
            fips=48,
            cases=20,
            deaths=2,
        )

        response = self.client.get(
            reverse("chart_data_api"),
            {"state": "California"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["datasets"][0]["data"], [10])
        self.assertEqual(response.json()["datasets"][1]["data"], [1])

    def test_unknown_state_returns_404(self):
        response = self.client.get(
            reverse("chart_data_api"),
            {"state": "Atlantis"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.json())


class HistoricalFilterApiTests(TestCase):
    """Tests the state and county APIs used by the historical dashboard."""

    def test_county_chart_only_returns_the_selected_state_and_county(self):
        # Both states have an Orange County, ensuring the state filter is applied.
        CovidCountyData.objects.create(
            date=date(2020, 1, 21),
            county="Orange",
            state="California",
            fips=6059,
            cases=10,
            deaths=1,
        )
        CovidCountyData.objects.create(
            date=date(2020, 1, 21),
            county="Orange",
            state="Florida",
            fips=12095,
            cases=25,
            deaths=3,
        )

        response = self.client.get(
            reverse("chart_data_api"),
            {"state": "California", "county": "Orange"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["datasets"][0]["data"], [10])
        self.assertEqual(response.json()["datasets"][1]["data"], [1])

    def test_state_list_returns_unique_states(self):
        # California appears twice to confirm duplicate names are removed.
        CovidStateData.objects.create(
            date=date(2020, 1, 21),
            state="California",
            fips=6,
            cases=10,
            deaths=1,
        )
        CovidStateData.objects.create(
            date=date(2020, 1, 22),
            state="California",
            fips=6,
            cases=15,
            deaths=2,
        )
        CovidStateData.objects.create(
            date=date(2020, 1, 21),
            state="Texas",
            fips=48,
            cases=20,
            deaths=2,
        )

        response = self.client.get(reverse("get_states_api"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ["California", "Texas"])

    def test_county_list_only_returns_counties_in_selected_state(self):
        CovidCountyData.objects.create(
            date=date(2020, 1, 21),
            county="Alameda",
            state="California",
            fips=6001,
            cases=8,
            deaths=0,
        )
        CovidCountyData.objects.create(
            date=date(2020, 1, 21),
            county="Orange",
            state="California",
            fips=6059,
            cases=10,
            deaths=1,
        )
        CovidCountyData.objects.create(
            date=date(2020, 1, 21),
            county="Orange",
            state="Florida",
            fips=12095,
            cases=25,
            deaths=3,
        )

        response = self.client.get(
            reverse("get_counties_api"),
            {"state": "California"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ["Alameda", "Orange"])

    def test_county_list_requires_a_state(self):
        response = self.client.get(reverse("get_counties_api"))

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())


class HistoricalDataImportTests(TestCase):
    """Tests the historical CSV import command with small sample files."""

    def test_imports_national_state_and_county_csv_data(self):
        # Small in-memory samples keep the test independent of the real datasets.
        csv_files = {
            "us-counties.csv": (
                "date,county,state,fips,cases,deaths\n"
                "2020-01-21,Snohomish,Washington,53061,1,0\n"
                "2020-01-22,Unknown,New York,,2,0\n"
            ),
            "us-states.csv": (
                "date,state,fips,cases,deaths\n"
                "2020-01-21,Washington,53,1,0\n"
            ),
            "us.csv": (
                "date,cases,deaths\n"
                "2020-01-21,1,0\n"
            ),
        }

        def open_test_csv(path, *args, **kwargs):
            return StringIO(csv_files[path.name])

        # Replace file access so the real CSV files are never opened.
        with patch("builtins.open", side_effect=open_test_csv):
            command = ImportHistoricalDataCommand(stdout=StringIO())
            command.handle()

        self.assertEqual(CovidCountyData.objects.count(), 2)
        self.assertEqual(CovidStateData.objects.count(), 1)
        self.assertEqual(CovidUSData.objects.count(), 1)

        county_without_fips = CovidCountyData.objects.get(county="Unknown")
        self.assertIsNone(county_without_fips.fips)

        national_record = CovidUSData.objects.get(date=date(2020, 1, 21))
        self.assertEqual(national_record.cases, 1)
        self.assertEqual(national_record.deaths, 0)
