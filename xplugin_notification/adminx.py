from django.conf import settings
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _
from django.utils.module_loading import import_string
from xadmin.sites import site
from xadmin.views import ModelAdminView, CommAdminView, ListAdminView
import xadmin.sites

from xplugin_notification.actions import MarkAsReadAction
from xplugin_notification.models import Notification
from xplugin_notification.plugin import NotificationAdminPlugin, NotificationMenuPlugin, GuardianAdminPlugin
from xplugin_notification.views import NotificationReadAdminView, MarkAsReadView

site.register_plugin(NotificationAdminPlugin, ModelAdminView)
site.register_plugin(NotificationMenuPlugin, CommAdminView)
site.register_plugin(GuardianAdminPlugin, ListAdminView)


site.register_view(r"notification/admin/(?P<object_id>\d+)/read", NotificationReadAdminView, 'notification_admin_read')
site.register_view(r"notification/(?P<pk>\d+)/mark-as-read", MarkAsReadView, 'xplugin_notification_mark_as_read')

NotificationAdminOpts = getattr(settings, "NOTIFICATION_ADMIN_OPTS", object)
if isinstance(NotificationAdminOpts, str):
	NotificationAdminOpts = import_string(NotificationAdminOpts)


@xadmin.sites.register(Notification)
class NotificationAdmin(NotificationAdminOpts):
	actions = (MarkAsReadAction,)

	# plugin NotificationAdminPlugin
	notification_active = True

	# plugin GuardianAdminPlugin
	notification_guardian_protected = True

	list_filter = (
		"recipient",
		"source",
		"is_read",
	)

	search_fields = (
		"message",
		"url"
	)

	list_display = (
		"status_display",
		"recipient",
		"message_display",
		"source",
		"url_display",
		"created_at",
		"read_datetime",
	)

	def url_display(self, instance):
		"""Link icon if URL exists"""
		if instance.url:
			return '<a href="{}" title="{}"><i class="fa fa-external-link"></i></a>'.format(
				escape(instance.url), escape(instance.url)
			)
		return ""

	url_display.short_description = _("URL")
	url_display.admin_order_field = "url"
	url_display.is_column = True
	url_display.allow_tags = True

	def status_display(self, instance):
		"""Visual read/unread indicator"""
		if instance.is_read:
			return '<i class="fa fa-check text-muted" title="{}"></i>'.format(escape(_("Read")))
		return '<i class="fa fa-circle text-primary" title="{}"></i>'.format(escape(_("Unread")))

	status_display.short_description = ""
	status_display.admin_order_field = "is_read"
	status_display.is_column = True
	status_display.allow_tags = True

	def message_display(self, instance):
		"""Truncated message with tooltip"""
		msg = str(instance)
		if len(msg) > 80:
			return '<span title="{}">{}&hellip;</span>'.format(escape(msg), escape(msg[:80]))
		return escape(msg)

	message_display.short_description = _("Message")
	message_display.admin_order_field = "message"
	message_display.is_column = True
	message_display.allow_tags = True
