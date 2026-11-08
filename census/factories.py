"""
    Small helpers to create test data. Used by the census/test_*.py files.
"""
import datetime
from itertools import count

from django.contrib.auth.models import User
from django.utils import timezone

from .models import Farm, Municipality, MarketGardener, ExpiringUniqueEditLink

_counter = count(1)


def make_municipality(**kwargs):
    n = next(_counter)
    defaults = {
        "name": f"Commune {n}",
        "province": "Brabant wallon",
        "area": 50,
        "population": 10000,
    }
    defaults.update(kwargs)
    return Municipality.objects.create(**defaults)


def make_farm(municipality=None, **kwargs):
    n = next(_counter)
    defaults = {
        "name": f"Ferme {n}",
        "municipality": municipality or make_municipality(),
        "email": f"ferme{n}@example.com",
        "public": True,
    }
    defaults.update(kwargs)
    return Farm.objects.create(**defaults)


def make_gardener(farm, **kwargs):
    n = next(_counter)
    defaults = {
        "firstname": f"Prénom{n}",
        "lastname": f"Nom{n}",
        "email": f"maraicher{n}@example.com",
        "farm": farm,
    }
    defaults.update(kwargs)
    return MarketGardener.objects.create(**defaults)


def make_link(farm, days=1, expired=False):
    link = ExpiringUniqueEditLink.create(farm=farm, days=days)
    if expired:
        link.expiration_date = timezone.now() - datetime.timedelta(minutes=1)
    link.save()
    return link


def make_superuser():
    return User.objects.create_superuser("admin", "admin@example.com", "pw")


def farm_form_data(municipality, /, **overrides):
    """Minimal valid POST data for FarmForm (create and update views)."""
    data = {
        "name": "Le potager du test",
        "municipality": municipality.pk,
        "email": "nouvelle@example.com",
        "cgu_consent": "on",
        "address": "",
        "website": "",
        "fb_page": "",
        "phone": "",
        "area": "",
        "FTE": "",
        "FTEv": "",
        "production": "",
        "start_year": "",
        "end_year": "",
        "research_priorities": "",
        "cover_crop": "False",  # required by the public form (Oui/Non)
        "why_no_cover_crop": "",
    }
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}
