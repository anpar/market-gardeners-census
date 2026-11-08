from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .factories import make_farm, make_gardener, make_link, make_municipality, make_superuser
from .models import ExpiringUniqueEditLink, Farm


class AdminAccessTestCase(TestCase):
    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse("admin:census_farm_changelist"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response["Location"])


class AdminPagesTestCase(TestCase):
    """Every admin page renders, with data, so list_display/fieldsets/inlines stay valid."""

    def setUp(self):
        self.client.force_login(make_superuser())
        self.farm = make_farm(area=1, FTE=1, FTEv=0, production="Bio certifié", start_year=2015, end_year=2024)
        self.gardener = make_gardener(self.farm)
        self.link = make_link(self.farm)

    def test_index(self):
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_changelists(self):
        for model in ["farm", "municipality", "marketgardener", "expiringuniqueeditlink"]:
            with self.subTest(model=model):
                response = self.client.get(reverse(f"admin:census_{model}_changelist"))
                self.assertEqual(response.status_code, 200)

    def test_farm_changelist_filters_search_and_sort(self):
        url = reverse("admin:census_farm_changelist")
        for params in [{"q": self.farm.name}, {"municipality__province": "Brabant wallon"},
                       {"edited_by_user__exact": "1"}, {"o": "2"}, {"o": "-7"}]:
            with self.subTest(params=params):
                self.assertEqual(self.client.get(url, params).status_code, 200)

    def test_change_and_add_pages(self):
        pages = [
            reverse("admin:census_farm_change", args=(self.farm.pk,)),
            reverse("admin:census_farm_add"),
            reverse("admin:census_municipality_change", args=(self.farm.municipality.pk,)),
            reverse("admin:census_marketgardener_change", args=(self.gardener.pk,)),
            reverse("admin:census_expiringuniqueeditlink_change", args=(self.link.pk,)),
        ]
        for url in pages:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_farm_form_cannot_edit_municipalities_inline(self):
        response = self.client.get(reverse("admin:census_farm_change", args=(self.farm.pk,)))
        widget = response.context["adminform"].form.fields["municipality"].widget
        self.assertFalse(widget.can_add_related)
        self.assertFalse(widget.can_change_related)
        self.assertFalse(widget.can_delete_related)

    def test_import_export_pages(self):
        for model in ["farm", "municipality", "marketgardener"]:
            for page in ["import", "export"]:
                with self.subTest(model=model, page=page):
                    response = self.client.get(reverse(f"admin:census_{model}_{page}"))
                    self.assertEqual(response.status_code, 200)

    def test_save_farm_without_email(self):
        """formfield_overrides lets staff save a farm with no known e-mail."""
        url = reverse("admin:census_farm_change", args=(self.farm.pk,))
        data = {
            "name": "Sans e-mail", "municipality": self.farm.municipality.pk, "email": "",
            "address": "", "GPS_coordinates": "", "area": "", "FTE": "", "FTEv": "", "production": "",
            "start_year": "", "end_year": "", "phone": "", "website": "", "fb_page": "", "comment": "",
            "public": "on", "added_by": "Staff",
        }
        for prefix in ["marketgardener_set", "otherlinks_set"]:
            data.update({f"{prefix}-TOTAL_FORMS": "0", f"{prefix}-INITIAL_FORMS": "0",
                         f"{prefix}-MIN_NUM_FORMS": "0", f"{prefix}-MAX_NUM_FORMS": "1000"})
        response = self.client.post(url, data)

        errors = response.context["adminform"].form.errors if response.status_code == 200 else None
        self.assertEqual(response.status_code, 302, errors)
        self.farm.refresh_from_db()
        self.assertEqual(self.farm.name, "Sans e-mail")
        self.assertIsNone(self.farm.email)


class AdminActionsTestCase(TestCase):
    def setUp(self):
        self.client.force_login(make_superuser())

    def run_action(self, model, action, objects):
        return self.client.post(reverse(f"admin:census_{model}_changelist"), {
            "action": action,
            ACTION_CHECKBOX_NAME: [o.pk for o in objects],
        })

    def test_visibility_and_origin_actions(self):
        farms = [make_farm(public=False), make_farm(public=False)]
        cases = [("make_public", "public", True), ("hide", "public", False),
                 ("mark_staff", "added_by", "Staff"), ("mark_user", "added_by", "User")]
        for action, field, expected in cases:
            with self.subTest(action=action):
                self.assertEqual(self.run_action("farm", action, farms).status_code, 302)
                for farm in farms:
                    farm.refresh_from_db()
                    self.assertEqual(getattr(farm, field), expected)

    def test_campaign(self):
        active = make_farm(email="active@example.com")
        make_gardener(active, email="g@example.com")
        old_link = make_link(active)
        inactive = make_farm(end_year=2020)
        no_email = make_farm(email=None)

        self.run_action("farm", "campaign", [active, inactive, no_email])

        # Active farm: old links replaced by a single 21-day link, e-mailed to all its addresses
        self.assertFalse(ExpiringUniqueEditLink.objects.filter(pk=old_link.pk).exists())
        link = ExpiringUniqueEditLink.objects.get(farm=active)
        self.assertGreater((link.expiration_date - old_link.expiration_date).days, 18)
        self.assertEqual(len(mail.outbox), 1)
        self.assertCountEqual(mail.outbox[0].to, ["active@example.com", "g@example.com"])
        self.assertIn(link.token, mail.outbox[0].body)
        self.assertIn("2026", mail.outbox[0].subject)

        # Inactive farm: untouched. Farm without e-mail: link created, nothing sent.
        self.assertFalse(ExpiringUniqueEditLink.objects.filter(farm=inactive).exists())
        self.assertTrue(ExpiringUniqueEditLink.objects.filter(farm=no_email).exists())

    def test_reminder(self):
        municipality = make_municipality()
        to_remind = make_farm(municipality, edited_by_user=False)
        old_link = make_link(to_remind)
        already_done = make_farm(municipality, edited_by_user=True)
        inactive = make_farm(municipality, edited_by_user=False, end_year=2020)

        self.run_action("farm", "reminder", [to_remind, already_done, inactive])

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [to_remind.email])
        self.assertTrue(mail.outbox[0].subject.startswith("RAPPEL"))
        # Old links are kept (people may still use them), a new one is added
        self.assertTrue(ExpiringUniqueEditLink.objects.filter(pk=old_link.pk).exists())
        self.assertEqual(ExpiringUniqueEditLink.objects.filter(farm=to_remind).count(), 2)
        self.assertFalse(ExpiringUniqueEditLink.objects.filter(farm__in=[already_done, inactive]).exists())

    def test_campaign_municipality(self):
        with_emails = make_municipality(email="commune@example.com", alt_email3="echevin@example.com")
        without_email = make_municipality()
        make_farm(with_emails)
        make_farm(with_emails)
        make_farm(with_emails, public=False)

        self.run_action("municipality", "campaign_municipality", [with_emails, without_email])

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["commune@example.com", "echevin@example.com"])
        self.assertIn("communes", mail.outbox[0].subject)
