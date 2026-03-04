from django import template

register = template.Library()

@register.filter
def active_and_public(farms):
    return farms.filter(public=True, end_year=None)