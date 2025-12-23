from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from core.utils import SELLER_GROUP_NAME
from products.models import Product, Category


class Command(BaseCommand):
    help = "Create default roles (groups) and assign permissions."

    def handle(self, *args, **options):
        admin_group, _ = Group.objects.get_or_create(name="Admin")
        seller_group, _ = Group.objects.get_or_create(name=SELLER_GROUP_NAME)
        customer_group, _ = Group.objects.get_or_create(name="Customer")

        product_ct = ContentType.objects.get_for_model(Product)
        category_ct = ContentType.objects.get_for_model(Category)

        # Product permissions
        add_product = Permission.objects.get(
            codename="add_product", content_type=product_ct)
        change_product = Permission.objects.get(
            codename="change_product", content_type=product_ct)
        delete_product = Permission.objects.get(
            codename="delete_product", content_type=product_ct)
        view_product = Permission.objects.get(
            codename="view_product", content_type=product_ct)

        add_category = Permission.objects.get(
            codename="add_category", content_type=category_ct)
        change_category = Permission.objects.get(
            codename="change_category", content_type=category_ct)
        delete_category = Permission.objects.get(
            codename="delete_category", content_type=category_ct)
        view_category = Permission.objects.get(
            codename="view_category", content_type=category_ct)

        seller_group.permissions.set([
            add_product, change_product, view_product,
            add_category, change_category, view_category,
        ])

        customer_group.permissions.set([view_product, view_category])
        admin_group.permissions.set([
            add_product, change_product, delete_product, view_product,
            add_category, change_category, delete_category, view_category,
        ])

        self.stdout.write(self.style.SUCCESS(
            "Roles created/updated: Admin, Seller, Customer"))
