from django.core.management.base import BaseCommand
from data_handler.models import CovidCountyData, CovidStateData, CovidUSData
import csv
from datetime import datetime
from django.conf import settings

class Command(BaseCommand):
    help = 'Import historical COVID-19 data from CSVs'

    def handle(self, *args, **options):
        base_path = settings.BASE_DIR / 'Data'

        # Optional: Clear existing data to avoid duplicates
        CovidCountyData.objects.all().delete()
        CovidStateData.objects.all().delete()
        CovidUSData.objects.all().delete()

        # Import counties
        with open(base_path / 'us-counties.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                date_str = row.get('date')
                if not date_str:
                    continue
                try:
                    parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    continue

                fips = int(row['fips']) if row.get('fips') else None
                cases = int(row.get('cases', 0))
                deaths = int(row.get('deaths', 0))

                CovidCountyData.objects.create(
                    date=parsed_date,
                    county=row.get('county', ''),
                    state=row.get('state', ''),
                    fips=fips,
                    cases=cases,
                    deaths=deaths
                )

        # Import states
        with open(base_path / 'us-states.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                date_str = row.get('date')
                if not date_str:
                    continue
                try:
                    parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    continue

                fips = int(row['fips']) if row.get('fips') else 0
                cases = int(row.get('cases', 0))
                deaths = int(row.get('deaths', 0))

                CovidStateData.objects.create(
                    date=parsed_date,
                    state=row.get('state', ''),
                    fips=fips,
                    cases=cases,
                    deaths=deaths
                )

        # Import US national
        with open(base_path / 'us.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                date_str = row.get('date')
                if not date_str:
                    continue
                try:
                    parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    continue

                cases = int(row.get('cases', 0))
                deaths = int(row.get('deaths', 0))

                CovidUSData.objects.create(
                    date=parsed_date,
                    cases=cases,
                    deaths=deaths
                )

        self.stdout.write(self.style.SUCCESS('Historical data imported successfully'))