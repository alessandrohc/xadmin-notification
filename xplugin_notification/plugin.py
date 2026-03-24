from django.contrib.auth import get_permission_codename
from django.forms import Media
from django.utils.translation import gettext as _
from django.template.loader import render_to_string
from guardian.shortcuts import get_objects_for_user
from rest_framework.exceptions import PermissionDenied
from xadmin.plugins.utils import get_context_dict
from xadmin.views import BaseAdminPlugin

from xplugin_notification.models import Notification
from xplugin_notification.rest.permisstion import HasNotificationPermission
from xplugin_notification.rest.serializers import NotificationSerializer


class NotificationMenuPlugin(BaseAdminPlugin):
	"""Plugin that loads the menu and messages"""
	notification_model = Notification
	notification_menu_title = _('Notifications')

	def init_request(self, *args, **kwargs):
		...

	def _get_notifications(self):
		return self.notification_model.objects.filter(recipient=self.user)

	def _get_notifications_menu_title(self) -> str:
		return self.notification_menu_title

	def get_media(self, media):
		return media + Media(js=['xplugin_notification/js/notifications.js'])

	def block_extrabody(self, context, nodes):
		"""Insert the message template"""
		context = get_context_dict(context)
		nodes.append(render_to_string('xplugin_notification/notification_message.html', context))

	def block_top_navmenu(self, context, nodes):
		"""Enter the notifications menu"""
		context = get_context_dict(context)
		queryset = self._get_notifications()
		# O dropdown exibe apenas notificações não lidas
		unread_qs = queryset.filter(is_read=False)
		if not unread_qs.exists():
			return
		context["notification_admin"] = {
			"title": self._get_notifications_menu_title(),
			"count": unread_qs.count(),
			"items": unread_qs,
			"url": self.get_model_url(self.notification_model, "changelist"),
			"list_url": self.get_model_url(self.notification_model, "rest"),
		}
		nodes.append(render_to_string(
			"xplugin_notification/notification_menu.html",
			context=context,
			request=self.request
		))
		nodes.extend([
			render_to_string(
				"xplugin_notification/notification_loading.html",
				context=context,
				request=self.request
			),
			render_to_string(
				"xplugin_notification/notification_retry.html",
				context=context,
				request=self.request
			)
		])


class NotificationAdminPlugin(BaseAdminPlugin):
	"""Plugin that filters the content and returns it in rest style"""
	notification_serializer_class = NotificationSerializer
	notification_permissions = [HasNotificationPermission]
	notification_request_param = "xnotification"
	notification_unlimited = False
	# Limits the maximum number of notifications visible to the user to number.
	notification_max_num = 25
	notification_active = True

	def init_request(self, *args, **kwargs):
		is_active = bool(self.notification_active and self.request.GET.get('plugin') == self.notification_request_param)
		# The plugin is read-only because the permissions have been rewritten.
		if is_active and self.admin_view.request_method not in ['get', 'options', 'head']:
			raise PermissionDenied('read only')
		return is_active

	def get_permissions(self, __):
		"""Validates only list permissions"""
		return [permission() for permission in self.notification_permissions]

	def get_serializer_class(self, __):
		serializer_class = self.notification_serializer_class
		meta = serializer_class.Meta
		serializer_class = type(serializer_class.__name__, (serializer_class,), {
			'Meta': type("Meta", (meta,), {'model': self.model})
		})
		return serializer_class

	def filter_queryset(self, queryset, *args, **kwargs):
		queryset = queryset.filter(recipient=self.user, is_read=False)
		if not self.notification_unlimited and self.notification_max_num:
			queryset = queryset[:self.notification_max_num]
		return queryset


class GuardianAdminPlugin(BaseAdminPlugin):
	"""Protects the view by allowing access only to objects for which the user has permission"""
	notification_guardian_protected = False
	notification_guardian_objects_with_superuser = True

	def init_request(self, *args, **kwargs):
		return self.notification_guardian_protected

	def queryset(self, __):
		model_perms = self.admin_view.get_model_perms()
		model_perms = [get_permission_codename(name, self.opts)
		               for name in model_perms if model_perms[name]]
		queryset = get_objects_for_user(
			self.user,
			model_perms,
			klass=self.model,
			any_perm=True,
			with_superuser=self.notification_guardian_objects_with_superuser,
			accept_global_perms=False)
		return queryset
