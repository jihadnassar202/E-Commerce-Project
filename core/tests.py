from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from core.utils import SELLER_GROUP_NAME, is_seller


class SellerHelperTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.seller_group, _ = Group.objects.get_or_create(
            name=SELLER_GROUP_NAME)

    def test_superuser_is_seller(self):
        admin = self.User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pass1234")
        self.assertTrue(is_seller(admin))

    def test_group_member_is_seller(self):
        user = self.User.objects.create_user(
            username="seller1", email="seller1@example.com", password="pass1234")
        self.assertFalse(is_seller(user))
        user.groups.add(self.seller_group)
        self.assertTrue(is_seller(user))

    def test_anonymous_is_not_seller(self):
        class DummyUser:
            is_authenticated = False
        self.assertFalse(is_seller(DummyUser()))
