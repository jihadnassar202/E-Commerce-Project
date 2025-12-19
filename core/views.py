from django.shortcuts import render
from products.models import Product

def home(request):
    latest = (
        Product.objects.filter(is_active=True)
        .select_related("category")
        .order_by("-created_at")[:6]
    )
    return render(request, "core/home.html", {"latest": latest})
