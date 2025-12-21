from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from .decorators import seller_required
from .forms import ProductForm
from .models import Product, Category

def product_list(request):
    q = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()
    sort = request.GET.get("sort", "newest").strip()
    mine = request.GET.get("mine", "").strip()

    products = Product.objects.filter(is_active=True).select_related("category")

    # Filter by owner if mine=1 and user is seller/admin
    if mine == "1" and request.user.is_authenticated:
        if request.user.is_superuser or request.user.groups.filter(name="Seller").exists():
            products = products.filter(owner=request.user)

    if q:
        products = products.filter(
            Q(name__icontains=q) | Q(description__icontains=q) | Q(category__name__icontains=q)
        )

    if category_id:
        products = products.filter(category_id=category_id)

    if sort == "price_asc":
        products = products.order_by("price")
    elif sort == "price_desc":
        products = products.order_by("-price")
    else:
        products = products.order_by("-created_at")

    categories = Category.objects.filter(is_active=True).order_by("name")
    paginator = Paginator(products, 9)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "products/product_list.html", {
        "categories": categories,
        "page_obj": page_obj,
        "q": q,
        "category_id": category_id,
        "sort": sort,
        "mine": mine,
    })

def product_list_api(request):
    q = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()
    sort = request.GET.get("sort", "newest").strip()
    mine = request.GET.get("mine", "").strip()

    products = Product.objects.filter(is_active=True).select_related("category")
    
    # Filter by owner if mine=1 and user is seller/admin
    if mine == "1" and request.user.is_authenticated:
        if request.user.is_superuser or request.user.groups.filter(name="Seller").exists():
            products = products.filter(owner=request.user)
    
    if q:
        products = products.filter(
            Q(name__icontains=q) | Q(description__icontains=q) | Q(category__name__icontains=q)
        )
    if category_id:
        products = products.filter(category_id=category_id)
    if sort == "price_asc":
        products = products.order_by("price")
    elif sort == "price_desc":
        products = products.order_by("-price")
    else:
        products = products.order_by("-created_at")

    paginator = Paginator(products, 9)
    page_obj = paginator.get_page(request.GET.get("page"))

    html = render_to_string("products/_product_grid.html", {"page_obj": page_obj}, request=request)
    pagination = render_to_string("products/_pagination.html", {
        "page_obj": page_obj,
        "q": q,
        "category_id": category_id,
        "sort": sort,
        "mine": mine,
    }, request=request)
    return JsonResponse({"html": html, "pagination": pagination})

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    return render(request, "products/product_detail.html", {"product": product})

@login_required
@seller_required
def product_create(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.owner = request.user
            product.save()
            messages.success(request, "Product created successfully.")
            return redirect("product_detail", pk=product.pk)
        messages.error(request, "Fix the errors below.")
    else:
        form = ProductForm()
    return render(request, "products/product_form.html", {"form": form, "mode": "create"})

@login_required
@seller_required
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk) if request.user.is_superuser else \
              get_object_or_404(Product, pk=pk, owner=request.user)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Product updated successfully.")
            return redirect("product_detail", pk=product.pk)
        messages.error(request, "Fix the errors below.")
    else:
        form = ProductForm(instance=product)
    return render(request, "products/product_form.html", {"form": form, "mode": "update", "product": product})

@login_required
@seller_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk) if request.user.is_superuser else \
              get_object_or_404(Product, pk=pk, owner=request.user)
    if request.method == "POST":
        product.delete()
        messages.success(request, "Product deleted.")
        return redirect("product_list")
    # Should not reach here - modal handles confirmation
    return redirect("product_detail", pk=pk)

@login_required
def product_list_admin(request):
    """Product list for admin/sellers showing additional information."""
    if not (request.user.is_superuser or request.user.groups.filter(name="Seller").exists()):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    
    q = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()
    sort = request.GET.get("sort", "newest").strip()
    mine = request.GET.get("mine", "").strip()

    # Show all products (including inactive) for admin/sellers
    products = Product.objects.all().select_related("category", "owner")

    # Filter by owner if mine=1
    if mine == "1":
        products = products.filter(owner=request.user)

    if q:
        products = products.filter(
            Q(name__icontains=q) | Q(description__icontains=q) | Q(category__name__icontains=q)
        )

    if category_id:
        products = products.filter(category_id=category_id)

    if sort == "price_asc":
        products = products.order_by("price")
    elif sort == "price_desc":
        products = products.order_by("-price")
    else:
        products = products.order_by("-created_at")

    categories = Category.objects.filter(is_active=True).order_by("name")
    paginator = Paginator(products, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "products/product_list_admin.html", {
        "categories": categories,
        "page_obj": page_obj,
        "q": q,
        "category_id": category_id,
        "sort": sort,
        "mine": mine,
    })