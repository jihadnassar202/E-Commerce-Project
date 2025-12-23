from products.models import Category

def categories(request):
    """Add active categories to all templates."""
    return {
        'navbar_categories': Category.objects.filter(is_active=True).order_by("name")
    }

def cart_count(request):
    """Add cart item count to all templates."""
    cart = request.session.get("cart", {})
    count = sum(int(qty) for qty in cart.values()) if cart else 0
    return {
        'cart_count': count
    }
