# coding=utf-8
"""The two registered views, through the real URLconf.

Both are reachable by any logged-in staff user, and both take an object id -- so the
thing worth proving is that neither lets one user touch another's notification.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from xplugin_notification.models import Notification

User = get_user_model()
PASSWORD = "secret-for-tests"


class ViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="user", password=PASSWORD, is_staff=True, is_superuser=True
        )
        cls.other = User.objects.create_user(
            username="other", password=PASSWORD, is_staff=True, is_superuser=True
        )

    def setUp(self):
        self.client.force_login(self.user)

    def notification(self, recipient=None, **kwargs):
        kwargs.setdefault("message", "Hello")
        return Notification.objects.create(
            recipient=recipient or self.user, **kwargs
        )

    def read_url(self, obj):
        return "/admin/notification/admin/{0}/read".format(obj.pk)

    def mark_url(self, obj):
        return "/admin/notification/{0}/mark-as-read".format(obj.pk)


class ReadRedirectViewTests(ViewTestCase):
    """The link the menu points at: mark as read, then go where it pointed."""

    def test_it_marks_the_notification_read(self):
        obj = self.notification()
        self.client.get(self.read_url(obj))
        obj.refresh_from_db()
        self.assertTrue(obj.is_read)
        self.assertIsNotNone(obj.read_datetime)

    def test_it_redirects_to_the_notification_target(self):
        obj = self.notification(url="/admin/somewhere/")
        response = self.client.get(self.read_url(obj))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/admin/somewhere/")

    def test_without_a_target_it_falls_back_to_the_changelist(self):
        response = self.client.get(self.read_url(self.notification()))
        self.assertEqual(response.status_code, 302)
        self.assertIn("notification", response["Location"])

    def test_an_already_read_notification_keeps_its_read_date(self):
        from django.utils import timezone

        stamp = timezone.now()
        obj = self.notification(is_read=True, read_datetime=stamp)
        self.client.get(self.read_url(obj))
        obj.refresh_from_db()
        self.assertEqual(obj.read_datetime, stamp)

    def test_another_user_s_notification_is_a_404(self):
        # The lookup is scoped to recipient=self.user, which is the only thing
        # separating two staff users' inboxes.
        obj = self.notification(recipient=self.other)
        self.assertEqual(self.client.get(self.read_url(obj)).status_code, 404)
        obj.refresh_from_db()
        self.assertFalse(obj.is_read)


class MarkAsReadViewTests(ViewTestCase):
    """The AJAX endpoint the dropdown calls."""

    def test_posting_marks_it_read_and_answers_json(self):
        obj = self.notification()
        response = self.client.post(self.mark_url(obj))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"success": True})
        obj.refresh_from_db()
        self.assertTrue(obj.is_read)
        self.assertIsNotNone(obj.read_datetime)

    def test_an_already_read_notification_is_a_404(self):
        # The lookup filters is_read=False, so a double click is a 404 rather than a
        # second write.
        obj = self.notification(is_read=True)
        self.assertEqual(self.client.post(self.mark_url(obj)).status_code, 404)

    def test_another_user_s_notification_is_a_404(self):
        obj = self.notification(recipient=self.other)
        self.assertEqual(self.client.post(self.mark_url(obj)).status_code, 404)
        obj.refresh_from_db()
        self.assertFalse(obj.is_read)

    def test_a_get_is_not_accepted(self):
        # The view only defines post(); xadmin answers anything else with 405.
        obj = self.notification()
        self.assertEqual(self.client.get(self.mark_url(obj)).status_code, 405)
        obj.refresh_from_db()
        self.assertFalse(obj.is_read)
