from django.contrib import admin
from import_export.widgets import ForeignKeyWidget

from census.models import Municipality, Farm, MarketGardener, OtherLinks, ExpiringUniqueEditLink

from import_export import fields, resources
from import_export.admin import ImportExportModelAdmin

from django.urls import reverse

from django.db import models

from census.utils import send_email

admin.site.site_header = 'Administration'

"""
    MUNICIPALITY
"""
class MunicipalityResource(resources.ModelResource):

    class Meta:
        model = Municipality

class MunicipalityAdmin(ImportExportModelAdmin):
    list_display = ('id', 'name', 'province', 'population', 'area', 'GPS_coordinates')
    list_filter = ['province']
    ordering = ['name']
    search_fields = ['name']
    resource_class = MunicipalityResource

# TODO: does it need to be editable in the admin interface ? Municipalities don't often change.
admin.site.register(Municipality, MunicipalityAdmin)

"""
    MARKET GARDENERS
"""
class MarketGardernerInLine(admin.StackedInline):
    model = MarketGardener
    classes = ['']
    extra = 0

class MarketGardenerResource(resources.ModelResource):

    class Meta:
        model = MarketGardener

class MarketGardenerAdmin(ImportExportModelAdmin):
    list_display = ('lastname', 'firstname', 'farm', 'phone', 'email')
    ordering = ['lastname']
    search_fields = ['firstname', 'lastname']



admin.site.register(MarketGardener, MarketGardenerAdmin)

"""
    OTHER LINKS
"""
class OtherLinksInLine(admin.StackedInline):
    model = OtherLinks
    classes = ['collapse']
    extra = 0

"""
    FARM
"""
class FarmResource(resources.ModelResource):
    municipality = fields.Field(
        column_name='municipality',
        attribute='municipality',
        widget=ForeignKeyWidget(Municipality, field='name'))

    class Meta:
        model = Farm
        fields = ('municipality',)

"""
    TODO: repasser dessus + voir si il est possible d'override le verbose name (très bien pour l'utilisateur, trop long
    pour l'admin.
"""

@admin.action(description="Rendre publique")
def make_public(modeladmin, request, queryset):
    queryset.update(public=True)

@admin.action(description="Cacher")
def hide(modeladmin, request, queryset):
    queryset.update(public=False)

@admin.action(description='Marquer comme ajouté par "Staff"')
def mark_staff(modeladmin, request, queryset):
    queryset.update(added_by="Staff")

@admin.action(description='Marquer comme ajouté par "User"')
def mark_user(modeladmin, request, queryset):
    queryset.update(added_by="User")

@admin.action(description="Lancer la campagne annuelle")
def campaign(modeladmin, request, queryset):
    for farm in queryset:
        # Only send to farm with no known end_year
        if farm.end_year is None:
            # Delete existing link pointing to the same farm (if any)
            ExpiringUniqueEditLink.objects.filter(farm=farm).delete()

            # Create a new expiring unique edit link, expiring in three weeks
            link = ExpiringUniqueEditLink.create(farm=farm, days=21)
            link.save()

            home_url = request.build_absolute_uri(reverse("census:index"))
            unique_edit_url = request.build_absolute_uri(reverse("census:update", args=(link.token,)))

            context = {
                'farm': farm,
                'home_url': home_url,
                'unique_edit_url': unique_edit_url,
            }

            # FIXME: a try-catch here + message after operation is done ?
            send_email(farm.email_list(),
                       "Le recensement 2026 du maraîchage diversifié",
                       "campaign",
                       context)

class FarmAdmin(ImportExportModelAdmin):
    list_display = ('name_display', 'municipality_display', 'area_display', 'fte_display', 'ftev_display', 'production_display',
                    'start_year_display', 'end_year_display', 'flagged', 'email_display', 'phone', 'consent_display', 'edited_by_user_display',
                    'last_update_display')

    # TODO: nicer filter https://docs.djangoproject.com/fr/6.0/ref/contrib/admin/filters/
    list_filter = ['flagged', 'edited_by_user', 'cover_crop', 'production', 'end_year', 'consent']
    ordering = ['-last_update']
    search_fields = ['name', 'email', "municipality__name"]
    actions = [make_public, hide, mark_staff, mark_user, campaign]
    list_per_page = 500

    formfield_overrides = {
        # Allows to update a entry without a known email address
        models.EmailField: {'required': False},
        # Should do the same for the cover crop checkbox, but does not work
        # This is ignored for fields that have 'choices', see : https://github.com/django/django/pull/20559
        #models.NullBooleanField: {'required': False},
        #models.BooleanField: {'required': False},
    }

    # En attendant, en readonly pour éviter le "this field is mandatory" intempestif
    readonly_fields = ('cover_crop', 'why_no_cover_crop', 'research_priorities', 'consent', 'cgu_consent')

    fieldsets = [
        (None, {"fields": ["name"]}),
        ("Localisation de la ferme", {
            "fields": [
                "municipality",
                "address",
                "GPS_coordinates"],
            "classes": [""]
        }),
        ("Caractéristiques de la ferme", {
            "fields": [
                "area",
                "FTE",
                "FTEv",
                "production",
                "start_year",
                "end_year",
                ],
            "classes": [""]
        }),
        ("Priorités de la recherche", {
            "fields": [
                "research_priorities"],
            "classes": [""]
        }),
        ("Pratiques agricoles" , {
            "fields": [
                "cover_crop",
                "why_no_cover_crop"],
            "classes": [""]
        }),
        ("Contacts", {
            "fields": [
                "email",
                "phone",
                "consent",
                "website",
                "fb_page"],
            "classes": [""]
        }),
        ("Métadonnées", {
            "fields": [
                "comment",
                "public",
                "added_by",
                "edited_by_user",
                "flagged",
                "cgu_consent"
            ],
            "classes": [""]
        })
    ]

    inlines = [OtherLinksInLine, MarketGardernerInLine]

    # I don't want municipalities to be added, changed or worse - deleted - from here
    def get_form(self, request, obj=None, **kwargs):
        form = super(FarmAdmin, self).get_form(request, obj, **kwargs)
        field = form.base_fields["municipality"]
        field.widget.can_add_related = False
        field.widget.can_change_related = False
        field.widget.can_delete_related = False
        return form

admin.site.register(Farm, FarmAdmin)

admin.site.register(ExpiringUniqueEditLink)