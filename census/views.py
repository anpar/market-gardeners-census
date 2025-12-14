import datetime

from string import ascii_letters, digits
from random import choice

from django.core.mail import send_mail
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views import generic
from django.contrib import messages
from django.utils import timezone
from django.views import View

from .forms import EmailForm, FarmForm
from .models import Farm, ExpiringUniqueEditLink

def index(request):
    farm_list = Farm.objects.filter(public=True, end_year=None)

    context = {
        'farm_count': farm_list.count(),
        'municipality_count': farm_list.values('municipality').distinct().count(),
    }

    return render(request, "census/index.html", context)

def cgu(request):
    return render(request, "census/cgu.html")

class MapView(generic.ListView):
    template_name = "census/map.html"
    context_object_name = "farms"

    def get_queryset(self):
        return Farm.objects.filter(public=True, end_year=None).exclude(GPS_coordinates='').exclude(GPS_coordinates=None)

class ListingView(generic.ListView):
    template_name = "census/listing.html"
    context_object_name = "farms"

    def get_queryset(self):
        return Farm.objects.filter(public=True, end_year=None).order_by('municipality')

class FarmUpdatePreviewView(generic.DetailView):
    model = Farm
    template_name = "census/view.html"

    def get_context_data(self, **kwargs):
        context = super(FarmUpdatePreviewView, self).get_context_data(**kwargs)

        # Build a list of email address associated with that farm
        email_list = self.get_object().email_list()

        # There probably is a nicer way of censoring those emails (with python regex module 're' ?)
        context['censored_emails'] = ["*" * len(e.split('@')[0]) + "@" + e.split('@')[1] for e in email_list if e is not None and e != ""]

        context['form'] = EmailForm()

        return context

class GetEditLinkFormView(generic.FormView):
    form_class = EmailForm
    template_name = "census/view.html"

    def form_valid(self, form):
        farm_id = self.kwargs['pk']
        email_list = Farm.objects.get(id=farm_id).email_list()

        self.success_url = reverse("census:view", args=(farm_id,))

        if form.check_match(email_list):
            # Delete existing link pointing to the same farm (if any)
            ExpiringUniqueEditLink.objects.filter(farm_id=farm_id).delete()

            # Create a new expiring unique edit link
            link = ExpiringUniqueEditLink(farm_id=farm_id)
            link.token = ''.join(choice(ascii_letters + digits) for i in range(60))
            link.expiration_date = timezone.now() + datetime.timedelta(days=1)
            link.save()

            # Build absolute URI
            unique_edit_url = self.request.build_absolute_uri(reverse("census:update", args=(link.token,)))

            send_mail(
                subject="Votre lien d'édition unique",
                message="Pour modifier votre ferme pendant 24 heures : " + unique_edit_url,
                from_email="from@example.com",
                recipient_list=["paris.antoine.paris@gmail.com"],
                fail_silently=False,
            )

            messages.success(self.request,"Le lien est parti et devrait arriver dans quelques minutes !"
                                          " Vérifiez vos courriers indésirables.")
        else:
            messages.error(self.request,"L'adresse e-mail indiquée ne correspond pas à celle(s) se trouvant"
                                        " dans notre base données.")

        return super(GetEditLinkFormView, self).form_valid(form)

class FarmView(View):
    def get(self, request, *args, **kwargs):
        view = FarmUpdatePreviewView.as_view()
        return view(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        view = GetEditLinkFormView.as_view()
        return view(request, *args, **kwargs)

class FarmCreateView(generic.CreateView):
    model = Farm
    form_class = FarmForm
    template_name = "census/create.html"

    def get_context_data(self, **kwargs):
        context = super(FarmCreateView, self).get_context_data(**kwargs)
        context['display_form'] = True

        return context

    def form_valid(self, form):
        new_farm = form.save()

        self.success_url = reverse("census:thanks", args=(new_farm.id,))

        admin_change_url = self.request.build_absolute_uri(reverse("admin:census_farm_change",
                                                                   args=(new_farm.id,)))

        send_mail(
            subject="Une nouvelle ferme a été ajoutée !",
            message="Pour voir ou valider la ferme : " + admin_change_url,
            from_email="from@example.com",
            recipient_list=["paris.antoine.paris@gmail.com"],
            fail_silently=False,
        )

        return super(FarmCreateView, self).form_valid(form)

def thanks(request, farm_id):
    return render(request, "census/thanks.html", context={'id': farm_id})

class FarmUpdateView(generic.UpdateView):
    model = Farm
    form_class = FarmForm
    template_name = "census/update.html"

    display_form = False
    farm_id = None

    def get_object(self, queryset = None):
        # Retrieve the unique token in the URL
        token = self.kwargs['token']

        self.success_url = reverse("census:update", args=(token,))

        # Get the ExpiringUniqueEditLink and the corresponding farm
        link = get_object_or_404(ExpiringUniqueEditLink, token=token)
        farm = get_object_or_404(Farm, pk=link.farm_id)

        # Needed in the context if the link has expired to redirect to farm/<farm_id>
        self.farm_id = link.farm_id

        # If expiration date is in the future
        if link.expiration_date > timezone.now():
            self.display_form = True

        return farm

    def get_context_data(self, **kwargs):
        context = super(FarmUpdateView, self).get_context_data(**kwargs)

        context['display_form'] = self.display_form
        context['farm_id'] = self.farm_id

        return context

    def form_valid(self, form):
        # save() returns the instance that has been saved to the database
        modified_farm = form.save()

        # If we're here, then the farm has been edit by a user of the platform
        modified_farm.edited_by_user = True

        admin_change_url = self.request.build_absolute_uri(reverse("admin:census_farm_change",
                                                                   args=(modified_farm.id,)))

        send_mail(
            subject="Une ferme vient d'être modifiée !",
            message="Pour voir la ferme : " + admin_change_url,
            from_email="from@example.com",
            recipient_list=["paris.antoine.paris@gmail.com"],
            fail_silently=False,
        )

        messages.success(self.request,"Modifications enregistrées !")

        return super(FarmUpdateView, self).form_valid(form)