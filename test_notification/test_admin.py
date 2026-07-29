# coding=utf-8
"""The changelist and the bulk action.

The changelist is where a staff user reads their notifications, and it is scoped by
recipient for everyone except superusers -- so the scoping is the part that matters.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.utils.safestring import SafeString

from xplugin_notification.actions import MarkAsReadAction
from xplugin_notification.adminx import NotificationAdmin
from xplugin_notification.models import Notification
from xplugin_notification.register import notification

User = get_user_model()
PASSWORD = "secret-for-tests"
CHANGELIST = "/admin/xplugin_notification/notification/"


class ChangelistTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        cls.root = User.objects.create_user(
            username="root", password=PASSWORD, is_staff=True, is_superuser=True
        )
        cls.staff = User.objects.create_user(
            username="staff", password=PASSWORD, is_staff=True
        )
        # The model-level permission has to be granted separately: notify() assigns
        # four *per-object* permissions with guardian, and xadmin's changelist gates on
        # the model permission before any of that is consulted. So a recipient who was
        # only ever notified gets 403 on "All notifications" -- the host project grants
        # the model permission itself (plus_base/xpublique/permissions.py). Recorded in
        # ModelPermissionRequirementTests below.
        cls.staff.user_permissions.add(
            Permission.objects.get(
                content_type=ContentType.objects.get_for_model(Notification),
                codename="view_notification",
            )
        )
        cls.mine = notification.notify(cls.staff, message="Mine")
        cls.theirs = notification.notify(cls.root, message="Theirs")

    def test_a_superuser_sees_every_notification(self):
        self.client.force_login(self.root)
        response = self.client.get(CHANGELIST)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mine")
        self.assertContains(response, "Theirs")

    def test_a_staff_user_sees_only_their_own(self):
        """The scoping that keeps one staff user out of another's inbox.

        GuardianAdminPlugin filters by per-object permission as well, but this queryset
        override is the plain-SQL half of it.
        """
        self.client.force_login(self.staff)
        response = self.client.get(CHANGELIST)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mine")
        self.assertNotContains(response, "Theirs")

    def _admin_view(self, user):
        self.client.force_login(user)
        # Asserted on the view rather than the HTML: xadmin renders a column-chooser
        # listing every available field, so every verbose name appears in the markup
        # whether or not the column is displayed.
        return self.client.get(CHANGELIST).context["admin_view"]

    def test_the_recipient_column_is_only_shown_to_superusers(self):
        self.assertIn("recipient", self._admin_view(self.root).list_display)
        self.assertNotIn("recipient", self._admin_view(self.staff).list_display)

    def test_the_recipient_filter_is_only_offered_to_superusers(self):
        self.assertIn("recipient", self._admin_view(self.root).list_filter)
        self.assertNotIn("recipient", self._admin_view(self.staff).list_filter)

    def test_the_source_filter_is_offered_to_everyone(self):
        for user in (self.root, self.staff):
            with self.subTest(user=user.username):
                self.assertIn("source", self._admin_view(user).list_filter)


class ModelPermissionRequirementTests(TestCase):
    """Being notified is not enough to open the changelist.

    notify() grants four per-object permissions through guardian, which is what
    GuardianAdminPlugin filters on -- but xadmin checks the *model* permission before it
    ever reaches the plugin. So a recipient with no model permission gets 403 on "All
    notifications", even for notifications that are theirs.

    Recorded rather than changed: granting a model permission from a notify() call would
    widen a user's rights far beyond the notification being sent, which is a decision for
    the host project. plus_base grants it in its own permission configuration.
    """

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            username="staff", password=PASSWORD, is_staff=True
        )
        cls.obj = notification.notify(cls.staff, message="Mine")

    def test_the_recipient_alone_cannot_open_the_changelist(self):
        from guardian.shortcuts import get_perms

        # The object-level grants are there ...
        self.assertIn("view_notification", get_perms(self.staff, self.obj))
        # ... and the changelist still refuses.
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(CHANGELIST).status_code, 403)

    def test_the_notification_itself_stays_reachable(self):
        """The menu and the read-and-redirect view do not gate on the model permission.

        So a recipient can always read what they were sent; only the full list is gated.
        """
        self.client.force_login(self.staff)
        response = self.client.get(
            "/admin/notification/admin/{0}/read".format(self.obj.pk)
        )
        self.assertEqual(response.status_code, 302)


class DisplayHelperTests(TestCase):
    """The two computed columns, called directly.

    Both return SafeString, so both are responsible for their own escaping.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(username="user", is_staff=True)

    def _admin(self):
        # The display helpers only read their argument, so a bare instance is enough.
        return NotificationAdmin.__new__(NotificationAdmin)

    def _notification(self, **kwargs):
        kwargs.setdefault("message", "Hello")
        return Notification.objects.create(recipient=self.user, **kwargs)

    def test_an_unread_notification_shows_the_unread_marker(self):
        html = self._admin().status_display(self._notification())
        self.assertIsInstance(html, SafeString)
        self.assertIn("fa-circle", html)
        self.assertIn("text-primary", html)

    def test_a_read_notification_shows_the_read_marker(self):
        html = self._admin().status_display(self._notification(is_read=True))
        self.assertIn("fa-check", html)
        self.assertIn("text-muted", html)

    def test_a_short_message_is_rendered_whole(self):
        html = self._admin().message_display(self._notification(message="Short"))
        self.assertEqual(html, "Short")

    def test_a_long_message_is_truncated_with_the_full_text_in_the_title(self):
        message = "x" * 300
        html = self._admin().message_display(self._notification(message=message))
        self.assertIn("&hellip;", html)
        self.assertIn('title="{0}"'.format(message), html)
        self.assertEqual(html.count("x"), 500)  # 200 shown + 300 in the title

    def test_markup_never_reaches_the_column(self):
        """message_display renders str(instance), and __str__ strips the tags.

        So the changelist cell and its title attribute are both plain text even though
        the message is stored as HTML and rendered as HTML in the detail view. That is
        the property worth pinning: the list is the one place the markup must not run.
        """
        html = self._admin().message_display(
            self._notification(message='<b>' + "y" * 250 + '</b><script>x</script>')
        )
        self.assertNotIn("<b>", html)
        self.assertNotIn("<script>", html)
        self.assertIn("&hellip;", html)


class MarkAsReadActionTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(username="user", is_staff=True)

    def _action(self, can_change=True):
        action = MarkAsReadAction.__new__(MarkAsReadAction)
        # do_action is wrapped in xadmin's @filter_hook, which consults self.plugins.
        action.plugins = []
        action.request = RequestFactory().post("/admin/")
        action.request.user = self.user
        action.opts = Notification._meta
        action.messages = []
        action.has_change_permission = lambda obj=None: can_change
        action.message_user = lambda message, level=None: action.messages.append(message)
        return action

    def test_it_marks_the_unread_ones_read(self):
        unread = notification.notify(self.user, message="Unread")
        action = self._action()
        action.do_action(Notification.objects.all())
        unread.refresh_from_db()
        self.assertTrue(unread.is_read)
        self.assertIsNotNone(unread.read_datetime)

    def test_it_reports_how_many_it_changed(self):
        notification.notify(self.user, message="a")
        notification.notify(self.user, message="b")
        action = self._action()
        action.do_action(Notification.objects.all())
        self.assertIn("2", action.messages[0])

    def test_an_already_read_notification_is_not_counted_again(self):
        obj = notification.notify(self.user, message="a")
        Notification.objects.filter(pk=obj.pk).update(is_read=True)
        action = self._action()
        action.do_action(Notification.objects.all())
        self.assertIn("0", action.messages[0])

    def test_it_refuses_without_the_change_permission(self):
        notification.notify(self.user, message="a")
        with self.assertRaises(PermissionDenied):
            self._action(can_change=False).do_action(Notification.objects.all())
        self.assertFalse(Notification.objects.filter(is_read=True).exists())

    def test_it_declares_the_permission_it_needs(self):
        self.assertEqual(MarkAsReadAction.model_perm, "change")
        self.assertEqual(MarkAsReadAction.action_name, "read_selected")
