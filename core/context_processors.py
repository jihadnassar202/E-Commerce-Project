from products.models import Category

def categories(request):
    """Add active categories to all templates."""
    return {
        'navbar_categories': Category.objects.filter(is_active=True).order_by("name")
    }
