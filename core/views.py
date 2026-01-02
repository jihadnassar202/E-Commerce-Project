from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from core.utils import SELLER_GROUP_NAME, is_seller
from products.models import Category, Product

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
    seller_group, _ = Group.objects.get_or_create(name=SELLER_GROUP_NAME)
    users = User.objects.all().order_by("username")

    if request.method == "POST":
        uid = request.POST.get("user_id")
        user = get_object_or_404(User, pk=uid)

        if user.groups.filter(id=seller_group.id).exists():
            user.groups.remove(seller_group)
            messages.success(request, _("Removed Seller role from %(username)s.") % {'username': user.username})
        else:
            user.groups.add(seller_group)
            messages.success(request, _("Granted Seller role to %(username)s.") % {'username': user.username})

        return redirect("manage_sellers")

    seller_ids = set(seller_group.user_set.values_list("id", flat=True))

    return render(
        request,
        "core/manage_sellers.html",
        {
            "users": users,
            "seller_group": seller_group,
            "seller_ids": seller_ids,
        },
    )


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
            messages.success(request, _("Category created."))
            return redirect("category_list")
        messages.error(request, _("Name is required."))
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
            messages.success(request, _("Category updated."))
            return redirect("category_list")
        messages.error(request, _("Name is required."))
    return render(
        request,
        "core/category_form.html",
        {"mode": "update", "category": category},
    )
