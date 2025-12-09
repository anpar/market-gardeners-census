from django import template

register = template.Library()

@register.inclusion_tag("census/field.html")
def show_field(field):
    return {'field': field}
