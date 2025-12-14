from django import forms

from django.forms import ModelForm

from .models import Farm, MarketGardener

class EmailForm(forms.Form):
    email = forms.EmailField()

    def __init__(self, *args, **kwargs):
        super(EmailForm, self).__init__(*args, **kwargs)
        # Replace class attribute of form fields with form-control/form-select for proper styling with Bootstrap 5
        for visible in self.visible_fields():
            visible.field.widget.attrs['class'] = 'form-control'
            visible.field.widget.attrs['placeholder'] = 'Adresse e-mail de la ferme'

    # Check if the given email address matches one in a given list
    def check_match(self, email_list):
        if self.cleaned_data['email'] in email_list:
            return True
        else:
            return False

class FarmForm(ModelForm):
    class Meta:
        model = Farm
        exclude = ['comment', 'last_update', 'flagged', 'edited_by_user', 'added_by', 'public']

        # labels (verbose_name in the model) and help_texts can be overridden too, but better change it directly in the model
        error_messages ={
            'email' : {
                'unique': "Une ferme maraîchère avec cette adresse e-mail existe déjà."
            },
            'phone' : {
                'invalid': "Veuillez indiquer un numéro de téléphone valide (GSM ou fixe).",
                'unique': "Une ferme maraîchère avec ce numéro de téléphone existe déjà."
            },
            'website' : {
                'unique': "Une ferme maraîchère avec ce site web existe déjà."
            },
            'fb_page' : {
                'unique': "Une ferme maraîchère avec cette page Facebook existe déjà."
            }

        }

    # Replace class attribute of form fields with form-control/form-select for proper styling with Bootstrap 5
    def __init__(self, *args, **kwargs):
        super(FarmForm, self).__init__(*args, **kwargs)
        for visible in self.visible_fields():
            if visible.widget_type == 'select':
                visible.field.widget.attrs['class'] = 'form-select'
            elif visible.widget_type == 'checkbox':
                visible.field.widget.attrs['class'] = 'form-check-input'
            else:
                visible.field.widget.attrs['class'] = 'form-control'

                if visible.widget_type == 'textarea':
                    visible.field.widget.attrs['rows'] = '5'

            if visible.name == 'GPS_coordinates':
                visible.field.widget.attrs['placeholder'] = '50.66677974362429, 4.620421360598303'

class MarketGardenerForm(ModelForm):
    class Meta:
        model = MarketGardener
        exclude = ['farm']

        error_messages ={
            'email' : {
                'unique': "Un·e maraîcher·ère avec cette adresse e-mail existe déjà."
            },
            'phone' : {
                'invalid': "Veuillez indiquer un numéro de téléphone valide (GSM ou fixe).",
                'unique': "Un·e maraîcher·ère avec ce numéro de téléphone existe déjà."
            }
        }

    # Replace class attribute of form fields with form-control/form-select for proper styling with Bootstrap 5
    def __init__(self, *args, **kwargs):
        super(MarketGardenerForm, self).__init__(*args, **kwargs)
        for visible in self.visible_fields():
            if visible.widget_type == 'checkbox':
                visible.field.widget.attrs['class'] = 'form-check-input'
            else:
                visible.field.widget.attrs['class'] = 'form-control'
