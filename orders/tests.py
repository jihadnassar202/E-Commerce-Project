from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.contrib.auth.models import Group
from products.models import Category, Product
from orders.models import Order, OrderItem
from core.utils import SELLER_GROUP_NAME

User = get_user_model()


class OrdersListViewTest(TestCase):
    """Test orders_list view to ensure OrderItem.status field works correctly."""

    def setUp(self):
        """Set up test data: users, categories, products, orders."""
        self.client = Client()

        # Create admin user
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123',
            is_staff=True
        )

        # Create seller user
        self.seller_user = User.objects.create_user(
            username='seller',
            email='seller@test.com',
            password='testpass123'
        )
        seller_group, _ = Group.objects.get_or_create(name=SELLER_GROUP_NAME)
        self.seller_user.groups.add(seller_group)

        # Create regular user
        self.customer_user = User.objects.create_user(
            username='customer',
            email='customer@test.com',
            password='testpass123'
        )

        # Create category
        self.category = Category.objects.create(name='Test Category')

        # Create product owned by seller
        self.product = Product.objects.create(
            owner=self.seller_user,
            category=self.category,
            name='Test Product',
            description='Test description',
            price=Decimal('10.00'),
            stock=100,
            is_active=True
        )

        # Create order with order items
        self.order = Order.objects.create(
            user=self.customer_user,
            status=Order.STATUS_PAID,
            is_paid=True,
            total_amount=Decimal('20.00')
        )

        # Create order items - these should have status field with default 'pending'
        self.order_item1 = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            price_at_purchase=Decimal('10.00'),
            status=OrderItem.STATUS_PENDING
        )

        self.order_item2 = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            price_at_purchase=Decimal('10.00'),
            status=OrderItem.STATUS_SHIPPED
        )

    def test_orders_list_admin_view(self):
        """Test that admin can access orders_list without ProgrammingError."""
        self.client.login(username='admin', password='testpass123')

        # Access the orders list view - should not raise ProgrammingError
        response = self.client.get('/ar/orders/')

        # Should return 200 OK
        self.assertEqual(response.status_code, 200)

        # Should contain order data
        self.assertContains(response, str(self.order.id))
        self.assertContains(response, self.customer_user.username)

        # Should contain order item status displays (template uses item.get_status_display)
        # Status display for order_item1
        self.assertContains(response, 'Pending')
        # Status display for order_item2
        self.assertContains(response, 'Shipped')

    def test_orders_list_seller_view(self):
        """Test that seller can access orders_list without ProgrammingError."""
        self.client.login(username='seller', password='testpass123')

        # Access the orders list view - should not raise ProgrammingError
        response = self.client.get('/ar/orders/')

        # Should return 200 OK
        self.assertEqual(response.status_code, 200)

        # Should contain order data
        self.assertContains(response, str(self.order.id))
        self.assertContains(response, self.customer_user.username)

        # Should contain order item status displays
        self.assertContains(response, 'Pending')

    def test_orders_list_regular_user_redirect(self):
        """Test that regular users are redirected to my_orders."""
        self.client.login(username='customer', password='testpass123')

        response = self.client.get('/ar/orders/')

        # Should redirect to my_orders
        self.assertEqual(response.status_code, 302)
        self.assertIn('/ar/my-orders/', response.url)

    def test_order_item_status_field_exists(self):
        """Test that OrderItem.status field is accessible without database errors."""
        # Access status field directly - should not raise ProgrammingError
        self.assertEqual(self.order_item1.status, OrderItem.STATUS_PENDING)
        self.assertEqual(self.order_item2.status, OrderItem.STATUS_SHIPPED)

        # Test get_status_display() method
        self.assertEqual(self.order_item1.get_status_display(), 'Pending')
        self.assertEqual(self.order_item2.get_status_display(), 'Shipped')

    def test_order_item_prefetch_related_with_status(self):
        """Test that prefetch_related works with OrderItem.status field."""
        # This simulates what the view does: prefetch_related("items__product")
        order = Order.objects.prefetch_related(
            "items__product", "items__product__owner", "user").get(pk=self.order.pk)

        # Access items - should not raise ProgrammingError
        items = list(order.items.all())
        self.assertEqual(len(items), 2)

        # Access status on each item - should work
        for item in items:
            self.assertIsNotNone(item.status)
            self.assertIn(item.status, [choice[0]
                          for choice in OrderItem.STATUS_CHOICES])
            # This is what the template does - should not raise error
            status_display = item.get_status_display()
            self.assertIsNotNone(status_display)
