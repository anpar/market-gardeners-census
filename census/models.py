from django.contrib import admin
from django.db import models
from django.db.models.fields import CharField

from phonenumber_field.modelfields import PhoneNumberField


class Municipality(models.Model):
    class Meta:
        verbose_name = "Commune"
        verbose_name_plural = verbose_name + "s"

    name = models.CharField(verbose_name="Nom",
                            max_length=150,
                            unique=True)

    # Bruxelles is a region, not a province.
    PROVINCES = {
        "Brabant flamand": "Brabant flamand",
        "Brabant wallon": "Brabant wallon",
        "Bruxelles": "Bruxelles",
        "Hainaut": "Hainaut",
        "Liège": "Liège",
        "Luxembourg": "Luxembourg",
        "Namur": "Namur"
    }

    province = models.CharField(choices=PROVINCES,
                                verbose_name="Province")

    area = models.DecimalField(decimal_places=2,
                               max_digits=5,
                               verbose_name="Surface (en km²)")

    population = models.IntegerField(verbose_name="Population (au 01/01/2025)")

    def __str__(self):
        return self.name

class Farm(models.Model):
    class Meta:
        verbose_name = "Ferme"
        verbose_name_plural = verbose_name + "s"

    '''
        IDENTIFICATION DE LA FERME
    '''
    name = models.CharField(max_length=250,
                            verbose_name="Nom de la ferme")

    @admin.display(description="Nom", ordering="name")
    def name_display(self):
        return self.name

    municipality = models.ForeignKey(Municipality,
                                     on_delete=models.PROTECT,
                                     verbose_name="Commune du lieu de production",
                                     help_text="Parmi les 261 communes wallonnes, les 19 communes bruxelloises et les 6 communes à facilités.")

    @admin.display(description="Commune", ordering="name")
    def municipality_display(self):
        return self.municipality.name

    address = models.CharField(max_length=250,
                               blank=True,
                               null=True,
                               verbose_name="Adresse du lieu de production",
                               help_text="Nom de la rue et numéro du lieu de production.")

    GPS_coordinates = CharField(max_length=40,
                                blank=True,
                                null=True,
                                verbose_name="Coordonnées GPS",
                                help_text="latitude, longitude du lieu de production (tel qu'extrait via un clic-droit sur Google Maps)")

    # TODO: make a custom validator to accept URL starting with "www" ?
    website = models.URLField(blank=True,
                              null=True,
                              unique=True,
                              verbose_name="Site web",
                              help_text="Doit commencer par http:// ou https://.")

    fb_page = models.URLField(blank=True,
                              null=True,
                              unique=True,
                              verbose_name="Page Facebook")

    """
        INFORMATIONS DE CONTACT
    """
    email = models.EmailField(max_length=250,
                              unique=True,
                              blank=False,
                              null=True,
                              verbose_name="Adresse email")

    # See https://django-phonenumber-field.readthedocs.io/en/latest/index.html
    phone = PhoneNumberField(region='BE',
                             blank=True,
                             null=True,
                             unique=True,
                             verbose_name="N° de téléphone",
                             help_text="Peut être un numéro fixe ou GSM.")

    consent = models.BooleanField(blank=False,
                                  default=False,
                                  verbose_name="J'accepte d'être contacté·e par l'UCLouvain pour des questions de recherche "
                                               "liées au maraîchage diversifié.",
                                  help_text="Cela n'engage à rien d'autre qu'à peut-être un jour être contacté·e.")

    @admin.display(boolean=True, description="Contact ?", ordering="consent")
    def consent_display(self):
        return self.consent

    """
        CARACTÉRISTIQUES DE LA FERME
    """

    area = models.DecimalField(decimal_places=2,
                               max_digits=4,
                               blank=True,
                               null=True,
                               verbose_name="Surface dédiée à la production de légumes (en ha)")

    @admin.display(description="Surface (ha)")
    def area_display(self):
        return self.area

    FTE = models.DecimalField(decimal_places=1,
                              max_digits=4,
                              blank=True,
                              null=True,
                              verbose_name="Nombre d'équivalents temps plein rémunérés")

    @admin.display(description="ETPr")
    def fte_display(self):
        return self.FTE

    PRODUCTION = {
        "Bio certifié": "Bio certifié",
        "Bio non-certifié": "Bio non-certifié",
        "Conventionnel": "Conventionnel"
    }

    production = models.CharField(choices=PRODUCTION,
                                  blank=True,
                                  null=True,
                                  verbose_name="Mode de production")

    start_year = models.IntegerField(blank=True,
                                     null=True,
                                     verbose_name="Année d'installation")

    @admin.display(description="Début")
    def start_year_display(self):
        return self.start_year

    end_year = models.IntegerField(blank=True,
                                   null=True,
                                   verbose_name="Année de fin d'activité (le cas échéant)",
                                   help_text="Laisser vide si le projet est toujours actif.")

    @admin.display(description="Fin")
    def end_year_display(self):
        return self.end_year

    """
        DIVERS
    """

    comment = models.TextField(max_length=1000,
                               blank=True,
                               null=True,
                               verbose_name="Commentaire(s)")

    last_update = models.DateTimeField(auto_now=True,
                                       verbose_name="Dernière mise à jour")

    public = models.BooleanField(blank=False,
                                 default=False,
                                 verbose_name="Public",
                                 help_text="Indique si la ferme maraîchère est listée sur la plateforme ou non.")

    flagged = models.BooleanField(default=False,
                                  verbose_name="Flagged",
                                  help_text="Permet de marquer une ferme en cas de doute sur les données."
                                            " (Utiliser le champ commentaire pour détailler.)")

    edited_by_user = models.BooleanField(default=True,
                                         verbose_name="Edited by user",
                                         help_text="Indique si les données ont été éditées par un·e utilisateur·rice.")

    ADDED_BY = {
        "Staff": "Staff",
        "User": "User"
    }

    added_by = models.CharField(choices=ADDED_BY,
                                default=ADDED_BY["User"],
                                verbose_name="Ajouté par",
                                help_text="Indique si la ferme a été ajoutée par un utilisateur de la plateforme ou non.")

    @admin.display(boolean=True, description="Actif", ordering="end_year")
    def is_active(self):
        return self.end_year is None

    def email_list(self):
        return [self.email] + list(self.marketgardener_set.values_list("email", flat=True))

    def __str__(self):
        return self.name

class OtherLinks(models.Model):
    class Meta:
        verbose_name = "Autre lien"
        verbose_name_plural = "Autres liens"

    farm = models.ForeignKey(Farm,
                             on_delete=models.CASCADE,
                             verbose_name="Ferme")

    author = models.CharField(max_length=100,
                              verbose_name="Auteur")

    title = models.CharField(max_length=255,
                             verbose_name="Titre")

    link = models.URLField(unique=True,
                           verbose_name="Lien")

class MarketGardener(models.Model):

    firstname = models.CharField(max_length=50,
                                 verbose_name="Prénom")

    lastname = models.CharField(max_length=100,
                                blank=True,
                                verbose_name="Nom de famille")

    # See https://django-phonenumber-field.readthedocs.io/en/latest/index.html
    phone = PhoneNumberField(region='BE',
                             unique=True,
                             blank=True,
                             null=True,
                             default=None,
                             verbose_name="N° de téléphone",
                             help_text="N° de téléphone personnel.")

    email = models.EmailField(max_length=254,
                             unique=True,
                             blank=True,
                             null=True,
                             default=None,
                             verbose_name="Adresse email",
                             help_text="Adresse email personnelle liée au projet si elle existe.")

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, verbose_name="Ferme")

    class Meta:
        verbose_name = "Maraîcher·ère"
        verbose_name_plural = verbose_name + "s"

        unique_together = ('firstname', 'lastname')

    def __str__(self):
        return self.firstname + " " + self.lastname

class ExpiringUniqueEditLink(models.Model):
    class Meta:
        verbose_name = "Lien d'édition"
        verbose_name_plural = "Liens d'édition"

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, verbose_name="Ferme associée")

    token = models.CharField(max_length=120, null=False, unique=True,
                             verbose_name="Token d'accès unique")

    # TODO: check it its works whatever timezone
    expiration_date = models.DateTimeField(null=False, verbose_name="Date d'expiration")

    def __str__(self):
        return self.farm.name