from unittest import mock

from django.contrib.messages import get_messages
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .factories import farm_form_data, make_farm, make_gardener, make_link, make_municipality
from .models import ExpiringUniqueEditLink, Farm

ADMIN_EMAIL = "antoine.paris@uclouvain.be"


def messages_of(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


class StaticPagesTestCase(TestCase):
    def test_pages_render(self):
        for name in ["census:index", "census:cgu", "census:map", "census:listing", "census:create"]:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_thanks(self):
        response = self.client.get(reverse("census:thanks", args=(42,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["id"], 42)

    def test_unknown_url_404(self):
        self.assertEqual(self.client.get("/does-not-exist/").status_code, 404)


class IndexTestCase(TestCase):
    def test_counts_only_public_active_farms(self):
        a, b = make_municipality(), make_municipality()
        make_farm(a, edited_by_user=True)
        make_farm(a, edited_by_user=False)
        make_farm(b, edited_by_user=True)
        make_farm(b, public=False)       # hidden
        make_farm(b, end_year=2020)      # inactive

        context = self.client.get(reverse("census:index")).context
        self.assertEqual(context["farm_count"], 3)
        self.assertEqual(context["farm_validated_count"], 2)
        self.assertEqual(context["municipality_count"], 2)


class ListingAndMapTestCase(TestCase):
    def test_listing_shows_only_public_active_farms(self):
        visible = make_farm(name="Visible")
        make_farm(name="Cachée", public=False)
        make_farm(name="Arrêtée", end_year=2019)

        response = self.client.get(reverse("census:listing"))
        self.assertEqual(list(response.context["farms"]), [visible])
        self.assertContains(response, "Visible")
        self.assertNotContains(response, "Cachée")
        self.assertNotContains(response, "Arrêtée")

    def test_listing_ordered_by_municipality(self):
        m1, m2 = make_municipality(), make_municipality()
        f2 = make_farm(m2)
        f1 = make_farm(m1)
        farms = list(self.client.get(reverse("census:listing")).context["farms"])
        self.assertEqual(farms, [f1, f2])

    def test_map_lists_municipalities(self):
        make_municipality(name="Genappe", GPS_coordinates="50.6, 4.4")
        make_farm()
        response = self.client.get(reverse("census:map"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["municipalities"].count(), 2)


class FarmViewTestCase(TestCase):
    def setUp(self):
        self.farm = make_farm(email="contact@ferme.be")
        make_gardener(self.farm, email="jeanne@ferme.be")
        self.url = reverse("census:view", args=(self.farm.pk,))

    def test_get_shows_censored_emails(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(response.context["censored_emails"], ["*******@ferme.be", "******@ferme.be"])
        self.assertNotContains(response, "contact@ferme.be")
        self.assertNotContains(response, "jeanne@ferme.be")

    def test_get_unknown_farm_404(self):
        self.assertEqual(self.client.get(reverse("census:view", args=(999999,))).status_code, 404)

    def test_request_link_with_farm_email(self):
        response = self.client.post(self.url, {"email": "contact@ferme.be"})

        self.assertRedirects(response, self.url)
        link = ExpiringUniqueEditLink.objects.get(farm=self.farm)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["contact@ferme.be"])
        self.assertIn(reverse("census:update", args=(link.token,)), mail.outbox[0].body)
        self.assertIn("Le lien est parti", messages_of(response)[0])

    def test_request_link_with_gardener_email(self):
        self.client.post(self.url, {"email": "jeanne@ferme.be"})
        self.assertEqual(mail.outbox[0].to, ["jeanne@ferme.be"])

    def test_request_link_ignores_case_and_spaces(self):
        response = self.client.post(self.url, {"email": "  Contact@FERME.be "})
        self.assertIn("Le lien est parti", messages_of(response)[0])
        self.assertEqual(mail.outbox[0].to, ["contact@ferme.be"])  # sent to the address on file

    def test_request_link_invalid_email_unknown_farm_404(self):
        response = self.client.post(reverse("census:view", args=(999999,)), {"email": "pas-un-email"})
        self.assertEqual(response.status_code, 404)

    def test_request_link_keeps_old_links(self):
        old = make_link(self.farm)
        self.client.post(self.url, {"email": "contact@ferme.be"})
        self.assertTrue(ExpiringUniqueEditLink.objects.filter(pk=old.pk).exists())
        self.assertEqual(ExpiringUniqueEditLink.objects.filter(farm=self.farm).count(), 2)

    def test_request_link_wrong_email(self):
        response = self.client.post(self.url, {"email": "intrus@example.com"})

        self.assertRedirects(response, self.url)
        self.assertFalse(ExpiringUniqueEditLink.objects.exists())
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn("ne correspond pas", messages_of(response)[0])

    def test_request_link_invalid_email(self):
        response = self.client.post(self.url, {"email": "pas-un-email"})
        self.assertEqual(response.status_code, 200)  # form redisplayed with errors
        self.assertFalse(ExpiringUniqueEditLink.objects.exists())

    def test_request_link_mail_failure(self):
        with mock.patch("census.views.send_email", side_effect=OSError("[SMTP down]")):
            response = self.client.post(self.url, {"email": "contact@ferme.be"})
        self.assertRedirects(response, self.url)
        self.assertIn("SMTP down", messages_of(response)[0])

    def test_request_link_unknown_farm_404(self):
        response = self.client.post(reverse("census:view", args=(999999,)), {"email": "a@example.com"})
        self.assertEqual(response.status_code, 404)


class FarmCreateViewTestCase(TestCase):
    def setUp(self):
        self.municipality = make_municipality(name="Genappe")
        self.url = reverse("census:create")

    def test_create(self):
        response = self.client.post(self.url, farm_form_data(self.municipality, name="Nouvelle ferme"))

        farm = Farm.objects.get(name="Nouvelle ferme")
        self.assertRedirects(response, reverse("census:thanks", args=(farm.id,)))
        self.assertFalse(farm.public)  # must be validated by staff before being listed
        self.assertEqual(farm.added_by, "User")
        self.assertTrue(farm.cgu_consent)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [ADMIN_EMAIL])
        self.assertEqual(mail.outbox[0].subject, "Nouvelle ferme : Nouvelle ferme à Genappe")
        self.assertIn(reverse("admin:census_farm_change", args=(farm.id,)), mail.outbox[0].body)

    def test_create_without_cgu(self):
        response = self.client.post(self.url, farm_form_data(self.municipality, cgu_consent=None))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Farm.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_cannot_set_admin_fields(self):
        self.client.post(self.url, farm_form_data(self.municipality, public="on", flagged="on",
                                                  added_by="Staff", comment="hack"))
        farm = Farm.objects.get()
        self.assertFalse(farm.public)
        self.assertFalse(farm.flagged)
        self.assertEqual(farm.added_by, "User")
        self.assertIsNone(farm.comment)

    def test_mail_failure_does_not_block_creation(self):
        with mock.patch("census.views.send_email", side_effect=OSError("down")):
            response = self.client.post(self.url, farm_form_data(self.municipality))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Farm.objects.exists())


class FarmUpdateViewTestCase(TestCase):
    def setUp(self):
        self.farm = make_farm(name="Ancien nom", email="contact@ferme.be", edited_by_user=False, public=True)
        self.link = make_link(self.farm)
        self.url = reverse("census:update", args=(self.link.token,))

    def post_data(self, **overrides):
        data = {"name": self.farm.name, "email": self.farm.email}
        data.update(overrides)
        return farm_form_data(self.farm.municipality, **data)

    def test_get_valid_link_shows_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["display_form"])
        self.assertEqual(response.context["farm"], self.farm)
        self.assertContains(response, "Ancien nom")

    def test_update(self):
        response = self.client.post(self.url, self.post_data(name="Nouveau nom", area="2.5"))

        self.assertRedirects(response, self.url)
        self.farm.refresh_from_db()
        self.assertEqual(self.farm.name, "Nouveau nom")
        self.assertEqual(str(self.farm.area), "2.50")
        self.assertTrue(self.farm.edited_by_user)
        self.assertTrue(self.farm.public)  # not touched by the form
        self.assertIn("Modifications enregistrées !", messages_of(response))

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [ADMIN_EMAIL])
        self.assertIn("Nouveau nom", mail.outbox[0].subject)
        self.assertIn("Ancien nom", mail.outbox[0].body)  # diff old -> new

    def test_link_reusable_until_expiry(self):
        self.client.post(self.url, self.post_data(name="Premier"))
        self.client.post(self.url, self.post_data(name="Second"))
        self.farm.refresh_from_db()
        self.assertEqual(self.farm.name, "Second")

    def test_update_invalid_data(self):
        response = self.client.post(self.url, self.post_data(email="pas-un-email"))
        self.assertEqual(response.status_code, 200)
        self.farm.refresh_from_db()
        self.assertEqual(self.farm.email, "contact@ferme.be")
        self.assertEqual(len(mail.outbox), 0)

    def test_get_expired_link(self):
        expired = make_link(self.farm, expired=True)
        response = self.client.get(reverse("census:update", args=(expired.token,)))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["display_form"])
        self.assertContains(response, "expiré")
        self.assertContains(response, reverse("census:view", args=(self.farm.pk,)))

    def test_get_unknown_token(self):
        response = self.client.get(reverse("census:update", args=("inexistant",)))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["display_form"])
        self.assertContains(response, "erroné")

    def test_post_expired_link_rejected(self):
        expired = make_link(self.farm, expired=True)
        response = self.client.post(reverse("census:update", args=(expired.token,)), self.post_data(name="Piraté"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "expiré")
        self.farm.refresh_from_db()
        self.assertEqual(self.farm.name, "Ancien nom")
        self.assertFalse(self.farm.edited_by_user)
        self.assertEqual(len(mail.outbox), 0)

    def test_post_unknown_token_rejected(self):
        count = Farm.objects.count()
        self.client.raise_request_exception = False
        response = self.client.post(reverse("census:update", args=("inexistant",)),
                         self.post_data(name="Fantôme", email="fantome@example.com"))
        self.assertEqual(Farm.objects.count(), count)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "erroné")
        self.assertEqual(len(mail.outbox), 0)
