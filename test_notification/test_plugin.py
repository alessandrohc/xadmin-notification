# coding=utf-8
"""The four plugins, and the serializer they feed.

Two of them run on every admin page (the navbar menu on CommAdminView, the REST feed on
ModelAdminView), so what they refuse to do matters most.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.forms import Media
from django.test import RequestFactory, TestCase
from rest_framework.exceptions import PermissionDenied
from xadmin.views import CommAdminView, ModelAdminView

from xplugin_notification.models import Notification
from xplugin_notification.plugin import (
    GuardianAdminPlugin,
    NotificationAdminPlugin,
    NotificationDetailPlugin,
    NotificationMenuPlugin,
)
from xplugin_notification.register import notification

User = get_user_model()


class FakeAdminSite:
    # app_name too: the menu template resolves URLs through xadmin's tags, which read it.
    name = "xadmin"
    app_name = "xadmin"


def make_view(view_class, user, params=None, method="get", model=Notification):
    """A view instance without xadmin's setup chain.

    __new__ keeps the class identity the plugin registration depends on while skipping
    setup(), which wants a plugin manager, a form and a resolved URL.
    """
    view = view_class.__new__(view_class)
    view.request = RequestFactory().get("/admin/", params or {})
    view.request.user = user
    view.user = user
    view.request_method = method
    view.args = ()
    view.kwargs = {}
    view.admin_site = FakeAdminSite()
    view.model = model
    view.opts = model._meta
    view.get_model_url = lambda model, name, **kwargs: "/admin/{0}/".format(name)
    return view


class MenuPluginTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(username="user", is_staff=True)

    def _plugin(self, user=None):
        return NotificationMenuPlugin(make_view(CommAdminView, user or self.user))

    def _render(self, plugin):
        nodes = []
        plugin.block_top_navmenu({}, nodes)
        return nodes

    def test_no_menu_at_all_for_a_user_with_no_notifications(self):
        """The navbar stays clean until there is something to show.

        This runs on every admin page, so the early return is also the cheap path.
        """
        self.assertEqual(self._render(self._plugin()), [])

    def test_the_menu_appears_once_a_notification_exists(self):
        notification.notify(self.user, message="Hello")
        nodes = self._render(self._plugin())
        self.assertEqual(len(nodes), 3)  # menu + loading + retry
        # The messages themselves are fetched over AJAX from data-list_url, so the
        # markup carries the count and the endpoint rather than the text.
        self.assertIn('class="badge badge-pill badge-warning badge-notify"', nodes[0])
        self.assertIn("data-list_url=", nodes[0])
        self.assertIn("/notification/rest/", nodes[0])

    def test_the_unread_count_is_rendered(self):
        for index in range(3):
            notification.notify(self.user, message="n{0}".format(index))
        html = self._render(self._plugin())[0]
        self.assertIn("badge-notify", html)
        self.assertRegex(html, r"badge-notify\">\s*3\s*<")

    def test_a_read_notification_leaves_the_menu_without_the_dropdown(self):
        obj = notification.notify(self.user, message="Hello")
        Notification.objects.filter(pk=obj.pk).update(is_read=True)
        nodes = self._render(self._plugin())
        # The menu still renders (there is history), but the unread dropdown does not.
        self.assertEqual(len(nodes), 1)

    def test_another_user_s_notifications_are_invisible(self):
        other = User.objects.create(username="other", is_staff=True)
        notification.notify(other, message="Not yours")
        self.assertEqual(self._render(self._plugin()), [])

    def test_the_message_template_is_published_for_the_page(self):
        nodes = []
        self._plugin().block_extrabody({}, nodes)
        self.assertEqual(len(nodes), 1)

    def test_the_javascript_is_loaded(self):
        media = self._plugin().get_media(Media())
        self.assertIn(
            "xplugin_notification/js/notifications.js", [str(js) for js in media._js]
        )


class RestPluginTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(username="user", is_staff=True)

    def _plugin(self, params=None, method="get", **attrs):
        plugin = NotificationAdminPlugin(
            make_view(ModelAdminView, self.user, params=params, method=method)
        )
        for name, value in attrs.items():
            setattr(plugin, name, value)
        return plugin

    def test_inactive_without_the_plugin_parameter(self):
        self.assertFalse(self._plugin().init_request())

    def test_active_with_the_plugin_parameter(self):
        self.assertTrue(self._plugin({"plugin": "xnotification"}).init_request())

    def test_it_can_be_switched_off(self):
        plugin = self._plugin({"plugin": "xnotification"}, notification_active=False)
        self.assertFalse(plugin.init_request())

    def test_a_write_method_is_refused(self):
        """Read-only by construction: the feed is reachable by query parameter.

        A POST reaching the serializer would be a write path nobody reviewed.
        """
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                plugin = self._plugin({"plugin": "xnotification"}, method=method)
                with self.assertRaises(PermissionDenied):
                    plugin.init_request()

    def test_safe_methods_pass(self):
        for method in ("get", "options", "head"):
            with self.subTest(method=method):
                self.assertTrue(
                    self._plugin({"plugin": "xnotification"}, method=method).init_request()
                )

    def test_the_serializer_is_bound_to_the_view_s_model(self):
        # The packaged serializer declares no model; the plugin subclasses it per request.
        serializer_class = self._plugin().get_serializer_class(None)
        self.assertIs(serializer_class.Meta.model, Notification)

    def test_the_feed_shows_only_the_user_s_unread_notifications(self):
        other = User.objects.create(username="other", is_staff=True)
        notification.notify(self.user, message="Mine")
        read = notification.notify(self.user, message="Already read")
        Notification.objects.filter(pk=read.pk).update(is_read=True)
        notification.notify(other, message="Theirs")

        queryset = self._plugin().filter_queryset(Notification.objects.all())
        self.assertEqual([n.message for n in queryset], ["Mine"])

    def test_the_feed_is_capped(self):
        for index in range(30):
            notification.notify(self.user, message="n{0}".format(index))
        self.assertEqual(len(self._plugin().filter_queryset(Notification.objects.all())), 25)

    def test_the_cap_can_be_lifted(self):
        for index in range(30):
            notification.notify(self.user, message="n{0}".format(index))
        plugin = self._plugin(notification_unlimited=True)
        self.assertEqual(len(plugin.filter_queryset(Notification.objects.all())), 30)

    def test_the_permissions_are_instantiated(self):
        from xplugin_notification.rest.permission import HasNotificationPermission

        permissions = self._plugin().get_permissions(None)
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], HasNotificationPermission)


class DetailPluginTests(TestCase):
    """Opening a notification's detail page marks it read."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(username="user", is_staff=True)
        cls.other = User.objects.create(username="other", is_staff=True)

    def _plugin(self, active=True, user=None):
        plugin = NotificationDetailPlugin(make_view(ModelAdminView, user or self.user))
        plugin.notification_detail_active = active
        return plugin

    def test_it_is_off_unless_the_admin_turns_it_on(self):
        self.assertFalse(self._plugin(active=False).init_request())
        self.assertTrue(self._plugin().init_request())

    def test_opening_your_own_notification_marks_it_read(self):
        obj = notification.notify(self.user, message="Hello")
        self.assertFalse(obj.is_read)
        self._plugin().get_context({"object": obj})
        obj.refresh_from_db()
        self.assertTrue(obj.is_read)
        self.assertIsNotNone(obj.read_datetime)

    def test_opening_someone_else_s_does_not(self):
        # A superuser can open any notification from the changelist; that must not
        # consume another person's unread marker.
        obj = notification.notify(self.other, message="Hello")
        self._plugin().get_context({"object": obj})
        obj.refresh_from_db()
        self.assertFalse(obj.is_read)

    def test_an_already_read_notification_is_left_alone(self):
        from django.utils import timezone

        stamp = timezone.now()
        obj = notification.notify(self.user, message="Hello")
        Notification.objects.filter(pk=obj.pk).update(is_read=True, read_datetime=stamp)
        obj.refresh_from_db()
        self._plugin().get_context({"object": obj})
        obj.refresh_from_db()
        self.assertEqual(obj.read_datetime, stamp)

    def test_a_context_without_an_object_is_tolerated(self):
        self._plugin().get_context({})

    def test_the_message_field_is_allowed_to_render_html(self):
        # The message is authored by the sending app, and the detail view is where it is
        # meant to render as markup.
        class Result:
            allow_tags = False

        self.assertTrue(self._plugin().get_field_result(Result(), "message").allow_tags)
        self.assertFalse(self._plugin().get_field_result(Result(), "url").allow_tags)


class GuardianPluginTests(TestCase):
    """The changelist is filtered by per-object permission, not by recipient."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(username="user", is_staff=True)
        cls.other = User.objects.create(username="other", is_staff=True)

    def _plugin(self, user, protected=True):
        view = make_view(ModelAdminView, user)
        view.get_model_perms = lambda: {"view": True, "change": True}
        plugin = GuardianAdminPlugin(view)
        plugin.notification_guardian_protected = protected
        return plugin

    def test_it_is_off_unless_the_admin_turns_it_on(self):
        self.assertFalse(self._plugin(self.user, protected=False).init_request())
        self.assertTrue(self._plugin(self.user).init_request())

    def test_a_user_sees_only_the_notifications_granted_to_them(self):
        mine = notification.notify(self.user, message="Mine")
        notification.notify(self.other, message="Theirs")
        queryset = self._plugin(self.user).queryset(None)
        self.assertEqual([n.pk for n in queryset], [mine.pk])

    def test_a_user_with_no_grants_sees_nothing(self):
        notification.notify(self.other, message="Theirs")
        stranger = User.objects.create(username="stranger", is_staff=True)
        self.assertEqual(list(self._plugin(stranger).queryset(None)), [])
