from django.apps import AppConfig

class DataHandlerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'data_handler'

    def ready(self):
        # Import the Dash app during the app's ready phase
        from . import dash_app