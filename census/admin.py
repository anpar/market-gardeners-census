from django.contrib import admin
from import_export.widgets import ForeignKeyWidget

from census.models import Municipality, Farm, MarketGardener, OtherLinks, ExpiringUniqueEditLink

from import_export import fields, resources
from import_export.admin import ImportExportModelAdmin

from django.urls import reverse

from census.utils import send_email

admin.site.site_header = 'Administration'

"""
    MUNICIPALITY
"""
class MunicipalityResource(resources.ModelResource):

    class Meta:
        model = Municipality

class MunicipalityAdmin(ImportExportModelAdmin):
    list_display = ('id', 'name', 'province', 'population', 'area')
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

@admin.action(description="Lancer la campagne de collecte de données")
def campaign(modeladmin, request, queryset):
    for farm in queryset:
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

        send_email(farm.email_list(),
                   "Le recensement du maraîchage diversifié",
                   "campaign",
                   context)

class FarmAdmin(ImportExportModelAdmin):
    list_display = ('name_display', 'municipality_display', 'area_display', 'fte_display', 'production', 'flagged',
                    'is_active', 'public', 'consent_display', 'email', 'phone', 'added_by', 'edited_by_user',
                    'last_update')
    ordering = ['name']
    search_fields = ['name']
    actions = [make_public, hide, mark_staff, mark_user, campaign]
    list_per_page = 500

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
                "production",
                "start_year",
                "end_year",
                "research_priorities"],
            "classes": [""]
        }),
        ("Contacts", {
            "fields": [
                "email",
                "phone",
                "website",
                "fb_page"],
            "classes": [""]
        }),
        ("Divers", {
            "fields": [
                "comment",
                "public",
                "added_by",
                "edited_by_user",
                "flagged",
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