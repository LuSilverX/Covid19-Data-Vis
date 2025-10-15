from django.db import models

class CovidCountyData(models.Model):
    date = models.DateField()
    county = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    fips = models.IntegerField(null=True, blank=True)
    cases = models.IntegerField()
    deaths = models.IntegerField()

    class Meta:
        db_table = "us_counties_data"

    def __str__(self):
        return f"{self.county}, {self.state} - {self.date}: {self.cases} cases, {self.deaths} deaths"


class CovidStateData(models.Model):
    date = models.DateField()
    state = models.CharField(max_length=100)
    fips = models.IntegerField()
    cases = models.IntegerField()
    deaths = models.IntegerField()

    class Meta:
        db_table = "us_states_data"

    def __str__(self):
        return f"{self.state} - {self.date}: {self.cases} cases, {self.deaths} deaths"


class CovidUSData(models.Model):
    date = models.DateField()
    cases = models.IntegerField()
    deaths = models.IntegerField()

    class Meta:
        db_table = "us_covid_data"

    def __str__(self):
        return f"US - {self.date}: {self.cases} cases, {self.deaths} deaths"


class CDCData(models.Model):
    state = models.CharField(max_length=100)
    date = models.DateField()
    weekly_deaths = models.IntegerField(default=0)
    deaths_total = models.IntegerField(default=0)
    data_as_of = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ('state', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.state} - {self.date.strftime('%Y-%m-%d') if self.date else 'No Date'}"


class WHOData(models.Model):
    date_reported = models.DateField(db_index=True)
    country_code = models.CharField(max_length=10, blank=True)
    country = models.CharField(max_length=100, db_index=True)
    who_region = models.CharField(max_length=10, blank=True)
    new_cases = models.IntegerField(default=0)
    cumulative_cases = models.IntegerField(default=0)
    new_deaths = models.IntegerField(default=0)
    cumulative_deaths = models.IntegerField(default=0)

    class Meta:
        unique_together = ('date_reported', 'country_code')
        ordering = ['-date_reported', 'country']
        verbose_name = "WHO COVID Data"
        verbose_name_plural = "WHO COVID Data"

    def __str__(self):
        return f"{self.country} ({self.country_code}) - {self.date_reported.strftime('%Y-%m-%d')}"