from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.shortcuts import render, redirect
from django.contrib import messages
from products.models import Product  
from django.contrib.admin.views.decorators import staff_member_required
from products.models import Category
from django.shortcuts import get_object_or_404

User = get_user_model()

def home(request):
    latest = (
        Product.objects.filter(is_active=True)
        .select_related("category")
        .order_by("-created_at")[:6]
    )
    return render(request, "core/home.html", {"latest": latest})

@staff_member_required
def manage_sellers(request):
    seller_group, _ = Group.objects.get_or_create(name="Seller")
    users = User.objects.all().order_by("username")
    if request.method == "POST":
        uid = request.POST.get("user_id")
        user = User.objects.get(pk=uid)
        if user.groups.filter(name="Seller").exists():
            user.groups.remove(seller_group)
            messages.success(request, f"Removed Seller role from {user.username}.")
        else:
            user.groups.add(seller_group)
            messages.success(request, f"Granted Seller role to {user.username}.")
        return redirect("manage_sellers")
    return render(request, "core/manage_sellers.html", {"users": users, "seller_group": seller_group})

@staff_member_required
def category_list(request):
    categories = Category.objects.all().order_by("name")
    return render(request, "core/category_list.html", {"categories": categories})

@staff_member_required
def category_create(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        is_active = request.POST.get("is_active") == "on"
        if name:
            Category.objects.create(name=name, is_active=is_active)
            messages.success(request, "Category created.")
            return redirect("category_list")
        messages.error(request, "Name is required.")
    return render(request, "core/category_form.html", {"mode": "create"})

@staff_member_required
def category_update(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        is_active = request.POST.get("is_active") == "on"
        if name:
            category.name = name
            category.is_active = is_active
            category.save()
            messages.success(request, "Category updated.")
            return redirect("category_list")
        messages.error(request, "Name is required.")
    return render(request, "core/category_form.html", {"mode": "update", "category": category})
    