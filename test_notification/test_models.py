# coding=utf-8
"""The Notification model."""
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from xplugin_notification.models import Notification

User = get_user_model()


class ModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(username="user", is_staff=True)

    def _notification(self, **kwargs):
        kwargs.setdefault("recipient", self.user)
        kwargs.setdefault("message", "Hello")
        return Notification.objects.create(**kwargs)

    def test_str_strips_markup_from_the_message(self):
        """The message is rendered as HTML in the detail view but not in a list.

        __str__ feeds the changelist and the admin log, so leaving the tags in would put
        raw markup in both.
        """
        obj = self._notification(message='<b>Bold</b> and <a href="#">link</a>')
        self.assertEqual(str(obj), "Bold and link")

    def test_the_slug_defaults_to_a_fresh_uuid(self):
        first, second = self._notification(), self._notification()
        self.assertNotEqual(first.slug, second.slug)
        uuid.UUID(str(first.slug))

    def test_a_fresh_instance_holds_a_uuid_object_not_a_string(self):
        """Worth knowing before comparing a slug: the default is ``uuid.uuid4``.

        The callable returns a UUID, so an in-memory instance carries one until it comes
        back from the database, where SlugField's get_prep_value has stringified it. So
        ``obj.slug == "3f2b..."`` is False right after create() and True after a reload.
        Harmless in practice -- callers pass their own slug, and update_or_create
        coerces on the way to SQL -- but it is a real difference between the two states.
        """
        obj = self._notification()
        self.assertIsInstance(obj.slug, uuid.UUID)
        obj.refresh_from_db()
        self.assertIsInstance(obj.slug, str)
        self.assertEqual(len(obj.slug), 36)

    def test_the_slug_is_not_editable(self):
        # It is an identity, not a field a user fills in.
        self.assertFalse(Notification._meta.get_field("slug").editable)

    def test_the_slug_fits_the_field(self):
        """The host project relies on this: it truncates a signature to 50 chars.

        plus_base's CSP report model comments on exactly that limit.
        """
        self.assertEqual(Notification._meta.get_field("slug").max_length, 50)

    def test_a_notification_starts_unread_with_no_read_date(self):
        obj = self._notification()
        self.assertFalse(obj.is_read)
        self.assertIsNone(obj.read_datetime)

    def test_the_source_is_optional(self):
        # A system notification has no human sender.
        self.assertIsNone(self._notification().source)

    def test_deleting_the_recipient_deletes_the_notification(self):
        obj = self._notification()
        self.user.delete()
        self.assertFalse(Notification.objects.filter(pk=obj.pk).exists())

    def test_deleting_the_source_deletes_the_notification(self):
        source = User.objects.create(username="sender", is_staff=True)
        obj = self._notification(source=source)
        source.delete()
        self.assertFalse(Notification.objects.filter(pk=obj.pk).exists())

    def test_the_newest_notification_comes_first(self):
        older = self._notification(message="older")
        newer = self._notification(message="newer")
        self.assertEqual(
            [n.pk for n in Notification.objects.all()], [newer.pk, older.pk]
        )

    def test_the_related_names_the_project_queries_by(self):
        obj = self._notification(
            source=User.objects.create(username="sender", is_staff=True)
        )
        self.assertEqual(self.user.notification_admin_recipient.count(), 1)
        self.assertEqual(obj.source.notification_admin_source.count(), 1)

    def test_timestamps_are_maintained(self):
        obj = self._notification()
        self.assertIsNotNone(obj.created_at)
        self.assertIsNotNone(obj.updated_at)
