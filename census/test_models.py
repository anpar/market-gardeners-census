from django.test import TestCase

from .models import Farm, Municipality

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
