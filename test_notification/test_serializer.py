# coding=utf-8
"""The REST serializer that feeds the notification dropdown."""
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from xadmin.views import ModelAdminView

from test_notification.test_plugin import FakeAdminSite
from xplugin_notification.models import Notification
from xplugin_notification.register import notification
from xplugin_notification.rest.serializers import NotificationSerializer

User = get_user_model()


def bound_serializer(instance, view):
    serializer_class = type(
        "Bound",
        (NotificationSerializer,),
        {"Meta": type("Meta", (NotificationSerializer.Meta,), {"model": Notification})},
    )
    return serializer_class(instance, context={"view": view})


class SerializerTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(username="user", is_staff=True)
        cls.sender = User.objects.create(
            username="sender", first_name="Ana", is_staff=True
        )

    def setUp(self):
        view = ModelAdminView.__new__(ModelAdminView)
        view.request = RequestFactory().get("/admin/")
        view.request.user = self.user
        view.admin_site = FakeAdminSite()
        view.model = Notification
        view.opts = Notification._meta
        view.get_admin_url = lambda name, **kwargs: "/admin/{0}/{1}/".format(
            name, kwargs.get("pk") or kwargs.get("object_id") or ""
        )
        self.view = view

    def _data(self, **kwargs):
        obj = notification.notify(self.user, message=kwargs.pop("message", "Hi"), **kwargs)
        return bound_serializer(obj, self.view).data

    def test_it_exposes_exactly_the_declared_fields(self):
        self.assertEqual(
            set(self._data()),
            {
                "id",
                "user_name",
                "user_url",
                "user_photo_url",
                "message",
                "url",
                "is_read",
                "mark_as_read_url",
                "read_datetime",
                "created",
            },
        )

    def test_a_system_notification_has_no_sender_fields(self):
        # source is nullable: a notification raised by the system has no human behind it.
        data = self._data()
        self.assertEqual(data["user_name"], "")
        self.assertEqual(data["user_url"], "")
        self.assertEqual(data["user_photo_url"], "")

    def test_a_sender_is_described(self):
        data = self._data(source=self.sender)
        self.assertEqual(data["user_name"], "sender")
        self.assertTrue(data["user_url"])
        self.assertIn("sender", data["user_photo_url"])

    def test_the_url_defaults_to_the_read_and_redirect_view(self):
        # With no target of its own, clicking the notification still marks it read.
        self.assertIn("notification_admin_read", self._data()["url"])

    def test_an_explicit_target_url_is_used_as_is(self):
        self.assertEqual(self._data(url="/somewhere/")["url"], "/somewhere/")

    def test_the_mark_as_read_endpoint_is_published_per_notification(self):
        self.assertIn("xplugin_notification_mark_as_read", self._data()["mark_as_read_url"])

    def test_the_created_date_is_formatted_for_display(self):
        # Not an ISO timestamp: the dropdown prints it verbatim.
        self.assertNotIn("T", self._data()["created"])

    def test_the_message_is_serialised_as_is(self):
        """No escaping here, on purpose -- and worth knowing.

        The message is authored by the app that sent the notification, and both the
        dropdown template and the detail view render it as HTML. So a caller passing
        user-supplied text is passing it straight through to other users' browsers.
        """
        data = self._data(message="<b>bold</b>")
        self.assertEqual(data["message"], "<b>bold</b>")


class HostUserModelCouplingTests(TestCase):
    """The serializer reads two attributes Django's user model does not have.

    ``source.photo_url`` and ``source.has_photo`` belong to the host project's user
    model. With a stock ``auth.User`` the serializer raises as soon as a notification has
    a source, which makes this package unusable outside a project that provides them.
    Recorded rather than changed: guessing a fallback would paper over a real
    requirement, and the fix (a getattr, or a documented protocol) is a design call.
    """

    def test_the_serializer_requires_the_attributes(self):
        import inspect

        from xplugin_notification.rest import serializers

        source = inspect.getsource(serializers)
        self.assertIn("instance.source.photo_url", source)
        self.assertIn("instance.source.has_photo", source)

    def test_the_suite_s_user_model_provides_them(self):
        # Which is the only reason SerializerTests above can run at all.
        user = User.objects.create(username="u", first_name="Ana", is_staff=True)
        self.assertTrue(hasattr(user, "photo_url"))
        self.assertTrue(hasattr(user, "has_photo"))


class PermissionTests(TestCase):
    """HasNotificationPermission, driven by XADMIN_NOTIFICATION_PERMISSIONS.

    The setting names *actions* ("view", "change"); the class turns each into the
    model's permission codename and requires all of them. An empty setting means the
    REST feed is open to any staff user who can reach the admin.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(username="user", is_staff=True)

    def _check(self, user=None):
        from xplugin_notification.rest.permission import HasNotificationPermission

        class FakeView:
            opts = Notification._meta

        request = RequestFactory().get("/admin/")
        request.user = user or self.user
        return HasNotificationPermission().has_permission(request, FakeView())

    def test_an_empty_setting_means_open(self):
        with self.settings(XADMIN_NOTIFICATION_PERMISSIONS=()):
            self.assertTrue(self._check())

    def test_a_missing_permission_denies(self):
        with self.settings(XADMIN_NOTIFICATION_PERMISSIONS=["view"]):
            self.assertFalse(self._check())

    def test_a_granted_permission_allows(self):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        self.user.user_permissions.add(
            Permission.objects.get(
                content_type=ContentType.objects.get_for_model(Notification),
                codename="view_notification",
            )
        )
        with self.settings(XADMIN_NOTIFICATION_PERMISSIONS=["view"]):
            self.assertTrue(self._check(User.objects.get(pk=self.user.pk)))

    def test_every_named_permission_is_required(self):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        self.user.user_permissions.add(
            Permission.objects.get(
                content_type=ContentType.objects.get_for_model(Notification),
                codename="view_notification",
            )
        )
        with self.settings(XADMIN_NOTIFICATION_PERMISSIONS=["view", "change"]):
            self.assertFalse(self._check(User.objects.get(pk=self.user.pk)))

    def test_the_object_level_check_is_the_same_rule(self):
        from xplugin_notification.rest.permission import HasNotificationPermission

        class FakeView:
            opts = Notification._meta

        obj = notification.notify(self.user, message="Hi")
        request = RequestFactory().get("/admin/")
        request.user = self.user
        with self.settings(XADMIN_NOTIFICATION_PERMISSIONS=()):
            self.assertTrue(
                HasNotificationPermission().has_object_permission(
                    request, FakeView(), obj
                )
            )
