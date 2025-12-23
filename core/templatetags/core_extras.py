from django import template
from core.utils import is_seller

register = template.Library()


@register.filter
def has_group(user, group_name):
    """Return True if the user is authenticated and belongs to the given group."""
    try:
        return user.is_authenticated and user.groups.filter(name=group_name).exists()
    except Exception:
        return False


@register.filter(name="is_seller")
def is_seller_filter(user):
    """Return True when the user is a superuser or member of the Seller group."""
    return is_seller(user)
