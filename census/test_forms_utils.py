from django.core import mail
from django.test import TestCase

from .factories import farm_form_data, make_farm, make_municipality
from .forms import EmailForm, FarmForm, MarketGardenerForm
from .utils import send_email

ADMIN_EMAIL = "antoine.paris@uclouvain.be"


class FarmFormTestCase(TestCase):
    def setUp(self):
        self.municipality = make_municipality()

    def form(self, **overrides):
        return FarmForm(data=farm_form_data(self.municipality, **overrides))

    def test_minimal_valid(self):
        form = self.form()
        self.assertTrue(form.is_valid(), form.errors)

    def test_full_valid(self):
        form = self.form(address="Rue du Test 1", website="https://ferme.be", fb_page="https://facebook.com/ferme",
                         phone="010 12 34 56", area="1.25", FTE="2.5", FTEv="0.5", production="Bio certifié",
                         start_year="2015", research_priorities="Le sol", cover_crop="True",
                         why_no_cover_crop="", consent="on")
        self.assertTrue(form.is_valid(), form.errors)
        farm = form.save()
        self.assertEqual(str(farm.phone), "+3210123456")  # normalised to E.164, region BE
        self.assertTrue(farm.cover_crop)
        self.assertTrue(farm.consent)

    def test_cover_crop_required(self):
        # The "/" (unknown) choice cannot be submitted: farmers must answer Oui or Non.
        form = self.form(cover_crop="")
        self.assertFalse(form.is_valid())
        self.assertIn("cover_crop", form.errors)

    def test_cgu_consent_required(self):
        form = self.form(cgu_consent=None)
        self.assertFalse(form.is_valid())
        self.assertIn("conditions générales", str(form.non_field_errors()))

    def test_required_fields(self):
        for field in ["name", "municipality", "email"]:
            with self.subTest(field=field):
                form = self.form(**{field: ""})
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)

    def test_invalid_values(self):
        cases = {
            "email": "pas-un-email",
            "website": "pas une url",
            "phone": "123",
            "area": "100",  # max_digits=4, decimal_places=2 -> max 99.99
            "production": "Biodynamie",
            "start_year": "deux-mille",
            "municipality": "999999",
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                form = self.form(**{field: value})
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)

    def test_website_without_scheme_gets_https(self):
        form = self.form(website="www.ferme.be")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["website"], "https://www.ferme.be")

    def test_duplicate_email_rejected(self):
        make_farm(email="deja@example.com")
        form = self.form(email="deja@example.com")
        self.assertFalse(form.is_valid())
        self.assertIn("déjà utilisée", str(form.errors))

    def test_admin_only_fields_excluded(self):
        form = FarmForm()
        for field in ["GPS_coordinates", "comment", "last_update", "flagged", "edited_by_user", "added_by", "public"]:
            self.assertNotIn(field, form.fields)

    def test_bootstrap_classes(self):
        form = FarmForm()
        self.assertEqual(form.fields["municipality"].widget.attrs["class"], "form-select")
        self.assertEqual(form.fields["cgu_consent"].widget.attrs["class"], "form-check-input")
        self.assertEqual(form.fields["name"].widget.attrs["class"], "form-control")
        self.assertEqual(form.fields["research_priorities"].widget.attrs["rows"], "5")


class EmailFormTestCase(TestCase):
    def test_valid_and_match(self):
        form = EmailForm(data={"email": "a@example.com"})
        self.assertTrue(form.is_valid())
        self.assertTrue(form.check_match(["b@example.com", "a@example.com"]))
        self.assertFalse(form.check_match(["b@example.com"]))
        self.assertFalse(form.check_match([]))

    def test_match_ignores_case_and_spaces(self):
        form = EmailForm(data={"email": "A@Example.COM"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.matching_email(["b@example.com", " a@example.com"]), " a@example.com")
        self.assertIsNone(form.matching_email(["b@example.com", None, ""]))
        self.assertTrue(form.check_match(["a@EXAMPLE.com"]))

    def test_invalid(self):
        self.assertFalse(EmailForm(data={"email": "nope"}).is_valid())
        self.assertFalse(EmailForm(data={}).is_valid())

    def test_widget_attrs(self):
        attrs = EmailForm().fields["email"].widget.attrs
        self.assertEqual(attrs["class"], "form-control")
        self.assertIn("placeholder", attrs)


class MarketGardenerFormTestCase(TestCase):
    def test_valid(self):
        form = MarketGardenerForm(data={"firstname": "Jeanne", "lastname": "Dupont", "email": "", "phone": ""})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn("farm", form.fields)

    def test_custom_phone_message(self):
        form = MarketGardenerForm(data={"firstname": "Jeanne", "phone": "123"})
        self.assertFalse(form.is_valid())
        self.assertIn("numéro de téléphone valide", str(form.errors["phone"]))


class SendEmailTestCase(TestCase):
    def test_sends_text_and_html_with_admin_bcc(self):
        send_email(["x@example.com"], "Sujet", "edit_link", {"url": "https://example.com/update/abc/"})

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["x@example.com"])
        self.assertEqual(message.bcc, [ADMIN_EMAIL])
        self.assertEqual(message.subject, "Sujet")
        self.assertIn("recensement@maraichage-wallonie.be", message.from_email)
        self.assertIn("https://example.com/update/abc/", message.body)
        html, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertIn("https://example.com/update/abc/", html)

    def test_no_bcc_when_sending_to_admin(self):
        send_email([ADMIN_EMAIL], "Sujet", "edit_link", {"url": "u"})
        self.assertEqual(mail.outbox[0].bcc, [])

    def test_empty_recipient_list_sends_nothing(self):
        send_email([], "Sujet", "edit_link", {"url": "u"})
        self.assertEqual(len(mail.outbox), 0)

    def test_all_mail_templates_render(self):
        farm = make_farm()
        context = {
            "url": "u", "farm": farm, "new_farm": farm, "modified_farm": farm, "diff": {"name": {"old": "a", "new": "b"}},
            "home_url": "h", "listing_url": "l", "map_url": "m", "unique_edit_url": "e", "admin_change_url": "a",
            "farm_count": 3, "farm_count_mun": 1, "farm_count_province": 2,
        }
        for template in ["campaign", "campaign_municipality", "edit_link", "farm_updated", "new_farm", "reminder"]:
            with self.subTest(template=template):
                send_email(["x@example.com"], "S", template, context)
        self.assertEqual(len(mail.outbox), 6)
