from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from .models import Municipality


class MigrationsTestCase(TestCase):
    def test_no_missing_migrations(self):
        """Fails if models.py and the migration files have drifted apart."""
        out = StringIO()
        try:
            call_command("makemigrations", "census", "--check", "--dry-run", stdout=out)
        except SystemExit:
            self.fail("Models have changes not reflected in migrations:\n" + out.getvalue())

    def test_municipality_email_columns_exist(self):
        with connection.cursor() as cursor:
            columns = {c.name for c in connection.introspection.get_table_description(cursor, "census_municipality")}
        self.assertTrue({"email", "alt_email", "alt_email2", "alt_email3"} <= columns)


class MunicipalityEmailListTestCase(TestCase):
    def test_email_list_includes_all_addresses(self):
        municipality = Municipality.objects.create(name="Genappe", province="Brabant wallon",
                                                   area=90.35, population=16165,
                                                   email="a@genappe.be", alt_email="",
                                                   alt_email2="c@genappe.be", alt_email3=None)
        self.assertEqual(municipality.email_list(), ["a@genappe.be", "c@genappe.be"])
