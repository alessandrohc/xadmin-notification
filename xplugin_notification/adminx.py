from django.conf import settings
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.utils.module_loading import import_string
from crispy_forms.layout import HTML
from xadmin.layout import Main, Side, Fieldset, Row
from xadmin.sites import site
from xadmin.views import ModelAdminView, CommAdminView, ListAdminView, DetailAdminView
import xadmin.sites

from xplugin_notification.actions import MarkAsReadAction
from xplugin_notification.models import Notification
from xplugin_notification.plugin import (
	NotificationAdminPlugin, NotificationMenuPlugin, GuardianAdminPlugin,
	NotificationDetailPlugin
)
from xplugin_notification.views import NotificationReadAdminView, MarkAsReadView

site.register_plugin(NotificationAdminPlugin, ModelAdminView)
site.register_plugin(NotificationMenuPlugin, CommAdminView)
site.register_plugin(GuardianAdminPlugin, ListAdminView)
site.register_plugin(NotificationDetailPlugin, DetailAdminView)


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

	# plugin NotificationDetailPlugin
	notification_detail_active = True

	detail_show_all = False
	detail_layout = (
		Main(
			HTML('''
			<div class="card shadow-sm mb-4">
				<div class="card-header d-flex align-items-center justify-content-between">
					<span>
						{% if object.is_read %}
							<i class="fa fa-check text-muted mr-1"></i>
							<span class="text-muted">''' + str(_("Read")) + '''</span>
						{% else %}
							<i class="fa fa-circle text-primary mr-1"></i>
							<span class="text-primary font-weight-bold">''' + str(_("Unread")) + '''</span>
						{% endif %}
					</span>
					<small class="text-muted">
						<i class="far fa-clock mr-1"></i>{{ object.created_at }}
					</small>
				</div>
				<div class="card-body">
					<div style="word-break: break-word;">{{ object.message|safe }}</div>
				</div>
				{% if object.url %}
				<div class="card-footer">
					<a href="{{ object.url }}" class="btn btn-outline-primary btn-sm" target="_blank" rel="noopener">
						<i class="fa fa-external-link-alt mr-1"></i> ''' + str(_("Open link")) + '''
					</a>
				</div>
				{% endif %}
			</div>
			'''),
		),
		Side(
			HTML('''
			<div class="card shadow-sm mb-4">
				<div class="card-header"><strong>''' + str(_("Details")) + '''</strong></div>
				<ul class="list-group list-group-flush">
					<li class="list-group-item d-flex justify-content-between">
						<span class="text-muted">''' + str(_("Recipient")) + '''</span>
						<span>{{ object.recipient }}</span>
					</li>
					{% if object.source %}
					<li class="list-group-item d-flex justify-content-between">
						<span class="text-muted">''' + str(_("Source")) + '''</span>
						<span>{{ object.source }}</span>
					</li>
					{% endif %}
					<li class="list-group-item d-flex justify-content-between">
						<span class="text-muted">''' + str(_("Created at")) + '''</span>
						<span>{{ object.created_at }}</span>
					</li>
					{% if object.read_datetime %}
					<li class="list-group-item d-flex justify-content-between">
						<span class="text-muted">''' + str(_("Read date")) + '''</span>
						<span>{{ object.read_datetime }}</span>
					</li>
					{% endif %}
				</ul>
			</div>
			'''),
		),
	)

	@property
	def list_filter(self):
		# superuser can filter by recipient and source; others only by is_read
		if self.request.user.is_superuser:
			return ("is_read", "recipient", "source")
		return ("is_read", "source")

	search_fields = (
		"message",
		"url"
	)

	list_display = ("status_display", "message_display", "source", "read_datetime", "created_at")
	list_display_links = ("message_display",)
	list_display_links_details = True

	def get_list_display(self):
		# call super to ensure base_list_display is created
		display = super().get_list_display()
		if self.request.user.is_superuser and "recipient" not in display:
			display.insert(3, "recipient")
		return display

	def queryset(self):
		# superuser sees all notifications; others see only their own
		qs = super().queryset()
		if not self.request.user.is_superuser:
			qs = qs.filter(recipient=self.request.user)
		return qs

	def status_display(self, instance):
		"""Visual read/unread indicator"""
		if instance.is_read:
			return mark_safe('<i class="fa fa-check text-muted" title="{}"></i>'.format(escape(_("Read"))))
		return mark_safe('<i class="fa fa-circle text-primary" title="{}"></i>'.format(escape(_("Unread"))))

	status_display.short_description = ""
	status_display.admin_order_field = "is_read"
	status_display.is_column = True
	status_display.allow_tags = True

	def message_display(self, instance):
		"""Truncated message"""
		msg = str(instance)
		if len(msg) > 200:
			return mark_safe('<span title="{}">{}&hellip;</span>'.format(escape(msg), msg[:200]))
		return mark_safe(msg)

	message_display.short_description = _("Message")
	message_display.admin_order_field = "message"
	message_display.is_column = True
	message_display.allow_tags = True
