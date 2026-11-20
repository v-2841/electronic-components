from django.db.models import CharField, TextField, Transform
from django.db.backends.signals import connection_created


# SQLite lower() and LIKE fold case only for ASCII, so «резистор» would
# not find «Резистор». ULOWER is Python's str.lower registered in every
# SQLite connection: name__ulower__contains=query.lower() finds both.
class ULower(Transform):
    lookup_name = 'ulower'
    function = 'ULOWER'


def _lower(value):
    return value.lower() if isinstance(value, str) else value


def register_ulower(sender, connection, **kwargs):
    if connection.vendor == 'sqlite':
        connection.connection.create_function(
            'ULOWER', 1, _lower, deterministic=True)


def setup():
    CharField.register_lookup(ULower)
    TextField.register_lookup(ULower)
    connection_created.connect(register_ulower)
