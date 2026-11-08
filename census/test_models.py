import datetime
import string
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from .factories import make_farm, make_gardener, make_municipality
from .models import ExpiringUniqueEditLink, Farm, Municipality


class FarmTestCase(TestCase):
    def setUp(self):
        self.genappe = Municipality.objects.create(name="Genappe",
                                                   province="Brabant wallon",
                                                   area=90.35,
                                                   population=16165)

    def test_farm_creation(self):
        farm = Farm.objects.create(name="Les légumes d'Antoine",
                                   municipality=self.genappe,
                                   email="paris.antoine.paris@gmail.com")

        self.assertEqual(farm.municipality.name, self.genappe.name)

    def test_defaults(self):
        farm = Farm.objects.create(name="F", municipality=self.genappe)
        self.assertFalse(farm.public)
        self.assertFalse(farm.flagged)
        self.assertFalse(farm.consent)
        self.assertFalse(farm.cgu_consent)
        self.assertTrue(farm.edited_by_user)
        self.assertEqual(farm.added_by, "User")
        self.assertIsNone(farm.cover_crop)
        self.assertIsNotNone(farm.last_update)

    def test_str(self):
        self.assertEqual(str(make_farm(name="La Binette")), "La Binette")

    def test_nullable_text_fields(self):
        # Fields made nullable by migration 0018
        farm = make_farm(research_priorities=None, why_no_cover_crop=None)
        farm.refresh_from_db()
        self.assertIsNone(farm.research_priorities)
        self.assertIsNone(farm.why_no_cover_crop)

    def test_is_active(self):
        self.assertTrue(make_farm(end_year=None).is_active())
        self.assertFalse(make_farm(end_year=2020).is_active())

    def test_area_decimal_round_trip(self):
        farm = make_farm(area=Decimal("12.34"))
        farm.refresh_from_db()
        self.assertEqual(farm.area, Decimal("12.34"))

    def test_municipality_protected_from_deletion(self):
        from django.db.models import ProtectedError
        farm = make_farm()
        with self.assertRaises(ProtectedError):
            farm.municipality.delete()


class FarmEmailListTestCase(TestCase):
    def test_farm_and_gardener_emails(self):
        farm = make_farm(email="ferme@example.com")
        make_gardener(farm, email="a@example.com")
        make_gardener(farm, email=None)
        self.assertCountEqual(farm.email_list(), ["ferme@example.com", "a@example.com"])

    def test_no_email_at_all(self):
        farm = make_farm(email=None)
        self.assertEqual(farm.email_list(), [])


class FarmAdminDisplayTestCase(TestCase):
    def test_simple_displays(self):
        farm = make_farm(name="N", area=Decimal("1.5"), FTE=Decimal("2.0"), FTEv=Decimal("0.5"),
                         production="Bio certifié", start_year=2015, consent=True, edited_by_user=False)
        self.assertEqual(farm.name_display(), "N")
        self.assertEqual(farm.municipality_display(), farm.municipality.name)
        self.assertEqual(farm.area_display(), Decimal("1.5"))
        self.assertEqual(farm.fte_display(), Decimal("2.0"))
        self.assertEqual(farm.ftev_display(), Decimal("0.5"))
        self.assertEqual(farm.production_display(), "Bio certifié")
        self.assertEqual(farm.start_year_display(), 2015)
        self.assertTrue(farm.consent_display())
        self.assertFalse(farm.edited_by_user_display())

    def test_email_display_truncates(self):
        self.assertEqual(make_farm(email="abcdefghijklmnop@example.com").email_display(), "abcdefghij...")
        self.assertIsNone(make_farm(email=None).email_display())

    def test_last_update_display_format(self):
        farm = make_farm()
        datetime.datetime.strptime(farm.last_update_display(), "%d/%m/%y %H:%M")

    def test_end_year_display(self):
        self.assertEqual(make_farm(end_year=2021).end_year_display(), 2021)

    def test_municipality_display_sorts_by_municipality(self):
        self.assertEqual(Farm.municipality_display.admin_order_field, "municipality__name")


class FarmUniqueConstraintsTestCase(TestCase):
    def assert_duplicate_rejected(self, **fields):
        make_farm(**fields)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_farm(**fields)

    def test_unique_email(self):
        self.assert_duplicate_rejected(email="same@example.com")

    def test_unique_website(self):
        self.assert_duplicate_rejected(website="https://example.com")

    def test_unique_fb_page(self):
        self.assert_duplicate_rejected(fb_page="https://facebook.com/ferme")

    def test_unique_phone(self):
        self.assert_duplicate_rejected(phone="+3210123456")

    def test_several_farms_without_contact_details(self):
        make_farm(email=None, website=None, fb_page=None, phone=None)
        make_farm(email=None, website=None, fb_page=None, phone=None)
        self.assertEqual(Farm.objects.count(), 2)


class MunicipalityTestCase(TestCase):
    def test_str(self):
        self.assertEqual(str(make_municipality(name="Genappe")), "Genappe")

    def test_unique_name(self):
        make_municipality(name="Genappe")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_municipality(name="Genappe")

    def test_email_list_includes_all_addresses(self):
        municipality = make_municipality(email="a@genappe.be", alt_email="",
                                         alt_email2="c@genappe.be", alt_email3=None)
        self.assertEqual(municipality.email_list(), ["a@genappe.be", "c@genappe.be"])

    def test_email_list_empty(self):
        self.assertEqual(make_municipality().email_list(), [])


class MarketGardenerTestCase(TestCase):
    def test_str(self):
        gardener = make_gardener(make_farm(), firstname="Jeanne", lastname="Dupont")
        self.assertEqual(str(gardener), "Jeanne Dupont")

    def test_deleted_with_farm(self):
        farm = make_farm()
        make_gardener(farm)
        farm.delete()
        from .models import MarketGardener
        self.assertEqual(MarketGardener.objects.count(), 0)

    def test_unique_email(self):
        farm = make_farm()
        make_gardener(farm, email="x@example.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_gardener(farm, email="x@example.com")


class ExpiringUniqueEditLinkTestCase(TestCase):
    def test_create(self):
        farm = make_farm()
        before = timezone.now()
        link = ExpiringUniqueEditLink.create(farm=farm, days=21)

        self.assertEqual(link.farm, farm)
        self.assertEqual(len(link.token), 60)
        self.assertTrue(set(link.token) <= set(string.ascii_letters + string.digits))
        self.assertAlmostEqual(link.expiration_date, before + datetime.timedelta(days=21),
                               delta=datetime.timedelta(seconds=5))
        self.assertIsNone(link.pk)  # create() does not save
        self.assertEqual(str(link), farm.name)

    def test_default_one_day(self):
        link = ExpiringUniqueEditLink.create(farm=make_farm())
        self.assertAlmostEqual(link.expiration_date, timezone.now() + datetime.timedelta(days=1),
                               delta=datetime.timedelta(seconds=5))

    def test_tokens_differ(self):
        farm = make_farm()
        tokens = {ExpiringUniqueEditLink.create(farm=farm).token for _ in range(20)}
        self.assertEqual(len(tokens), 20)
