# coding=utf-8
"""The public API: ``notification.notify`` and ``notify_groups``.

This is what other apps call, so its refusals matter as much as its writes -- a
notification aimed at a deactivated account must not be delivered, and re-notifying the
same slug must update rather than pile up.

The two scenarios that used to live in ``xplugin_notification/tests.py`` are preserved
here; that module shipped inside the wheel and used ``assertEquals``, which Python 3.12
removed.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from guardian.shortcuts import get_perms

from xplugin_notification.models import Notification
from xplugin_notification.register import notification

User = get_user_model()


def make_user(username, is_staff=True, is_active=True):
    return User.objects.create(username=username, is_staff=is_staff, is_active=is_active)


class NotifyTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("user")
        cls.source = make_user("sender")

    def test_creating_notification(self):
        """Two notifications with no slug are two rows.

        Preserved from the original suite: the default slug is a fresh uuid4, so
        update_or_create never matches an existing row.
        """
        first = notification.notify(self.user, message="Hello1")
        second = notification.notify(self.user, message="Hello2")
        self.assertNotEqual(first, second)
        self.assertEqual(Notification.objects.count(), 2)

    def test_update_notification(self):
        """Re-notifying the same slug updates the row instead of adding one.

        Preserved from the original suite. This is what lets a caller keep a single
        standing notification per subject -- "3 pending reviews" rather than three rows.
        """
        first = notification.notify(self.user, message="Hello World!", slug="notifs")
        second = notification.notify(self.user, message="Hello Universe!", slug="notifs")
        self.assertEqual(first, second)
        self.assertNotEqual(first.message, second.message)
        self.assertEqual(Notification.objects.count(), 1)

    def test_the_message_and_recipient_are_stored(self):
        obj = notification.notify(self.user, message="Hi", source=self.source)
        self.assertEqual(obj.message, "Hi")
        self.assertEqual(obj.recipient, self.user)
        self.assertEqual(obj.source, self.source)
        self.assertFalse(obj.is_read)

    def test_extra_options_land_on_the_model(self):
        obj = notification.notify(self.user, message="Hi", url="/somewhere/")
        self.assertEqual(obj.url, "/somewhere/")

    def test_the_same_slug_for_a_different_recipient_is_a_new_row(self):
        # The identity is (slug, recipient, source), so one slug can address everyone.
        other = make_user("other")
        notification.notify(self.user, message="Hi", slug="shared")
        notification.notify(other, message="Hi", slug="shared")
        self.assertEqual(Notification.objects.count(), 2)

    def test_the_same_slug_from_a_different_source_is_a_new_row(self):
        notification.notify(self.user, message="Hi", slug="shared", source=None)
        notification.notify(self.user, message="Hi", slug="shared", source=self.source)
        self.assertEqual(Notification.objects.count(), 2)

    def test_a_non_staff_recipient_is_skipped(self):
        """Notifications are an admin feature, so a non-staff account gets none.

        The call returns None rather than raising, because callers notify in bulk.
        """
        outsider = make_user("outsider", is_staff=False)
        self.assertIsNone(notification.notify(outsider, message="Hi"))
        self.assertEqual(Notification.objects.count(), 0)

    def test_an_inactive_recipient_is_skipped(self):
        # A deactivated account must not accumulate notifications it can never read.
        retired = make_user("retired", is_active=False)
        self.assertIsNone(notification.notify(retired, message="Hi"))
        self.assertEqual(Notification.objects.count(), 0)


class SlugDefaultSettingTests(TestCase):
    """XNOTIFICATION_SLUG_DEFAULT can replace the uuid4 default.

    The field default is read at class-definition time, so the setting only takes effect
    for a process started with it -- which is why notify() consults the *field's* default
    rather than the setting. A plain string default works, and it makes every
    notification without an explicit slug collapse into one row per recipient.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("user")

    def test_a_non_callable_field_default_is_used_as_is(self):
        from unittest import mock

        field = Notification._meta.get_field("slug")
        with mock.patch.object(field, "default", "fixed-slug"):
            first = notification.notify(self.user, message="First")
            second = notification.notify(self.user, message="Second")
        self.assertEqual(first, second)
        self.assertEqual(Notification.objects.count(), 1)


class MenuActivationTests(TestCase):

    def test_the_menu_plugin_activates_unconditionally(self):
        """init_request has an empty body, so it returns None -- which xadmin reads as
        "no opinion" and leaves the plugin enabled. It gates itself later instead, by
        rendering nothing when the user has no notifications.
        """
        from django.test import RequestFactory
        from xadmin.views import CommAdminView

        from xplugin_notification.plugin import NotificationMenuPlugin

        view = CommAdminView.__new__(CommAdminView)
        view.request = RequestFactory().get("/admin/")
        view.request.user = make_user("user")
        view.user = view.request.user
        view.args, view.kwargs = (), {}
        view.admin_site = type("Site", (), {"name": "xadmin", "app_name": "xadmin"})()
        self.assertIsNone(NotificationMenuPlugin(view).init_request())


class ObjectPermissionTests(TestCase):
    """Every notification grants its recipient four per-object permissions.

    That is what GuardianAdminPlugin filters the changelist on, so without them a
    recipient sees an empty list.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("user")
        cls.other = make_user("other")

    def test_the_recipient_gets_all_four_permissions(self):
        obj = notification.notify(self.user, message="Hi")
        self.assertEqual(
            sorted(get_perms(self.user, obj)),
            [
                "add_notification",
                "change_notification",
                "delete_notification",
                "view_notification",
            ],
        )

    def test_nobody_else_gets_them(self):
        obj = notification.notify(self.user, message="Hi")
        self.assertEqual(get_perms(self.other, obj), [])

    def test_updating_a_notification_keeps_the_permissions(self):
        notification.notify(self.user, message="First", slug="s")
        obj = notification.notify(self.user, message="Second", slug="s")
        self.assertIn("view_notification", get_perms(self.user, obj))


class NotifyGroupsTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.group = Group.objects.create(name="editors")
        cls.other_group = Group.objects.create(name="readers")
        cls.member = make_user("member")
        cls.member.groups.add(cls.group)
        cls.outsider = make_user("outsider")
        cls.outsider.groups.add(cls.other_group)

    def test_every_member_of_the_group_is_notified(self):
        notification.notify_groups((self.group,), message="Announcement")
        self.assertEqual(
            list(Notification.objects.values_list("recipient__username", flat=True)),
            ["member"],
        )

    def test_members_of_other_groups_are_not(self):
        notification.notify_groups((self.group,), message="Announcement")
        self.assertFalse(Notification.objects.filter(recipient=self.outsider).exists())

    def test_a_user_in_two_targeted_groups_is_notified_once(self):
        # The queryset is distinct(), which is what prevents the double delivery.
        self.member.groups.add(self.other_group)
        notification.notify_groups(
            (self.group, self.other_group), message="Announcement"
        )
        self.assertEqual(Notification.objects.filter(recipient=self.member).count(), 1)

    def test_non_staff_and_inactive_members_are_filtered_out(self):
        make_user("nonstaff", is_staff=False).groups.add(self.group)
        make_user("inactive", is_active=False).groups.add(self.group)
        notification.notify_groups((self.group,), message="Announcement")
        self.assertEqual(Notification.objects.count(), 1)

    def test_it_returns_one_entry_per_targeted_user(self):
        """Documented shape: the list can contain None.

        notify() returns None for a recipient it skips, and notify_groups appends
        whatever it returns -- so a caller counting the result counts skipped users too.
        Here the queryset already excludes them, so the entries are all real.
        """
        result = notification.notify_groups((self.group,), message="Announcement")
        self.assertEqual(len(result), 1)
        self.assertTrue(all(result))

    def test_a_slug_addresses_the_whole_group_as_one_standing_notification(self):
        notification.notify_groups((self.group,), message="First", slug="standing")
        notification.notify_groups((self.group,), message="Second", slug="standing")
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(Notification.objects.get().message, "Second")
