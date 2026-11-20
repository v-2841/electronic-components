from django.apps import AppConfig


class PartsConfig(AppConfig):
    name = 'parts'
    verbose_name = 'Радиодетали'

    def ready(self):
        from parts import lookups

        lookups.setup()
