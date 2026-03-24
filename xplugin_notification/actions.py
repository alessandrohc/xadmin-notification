from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.utils.translation import gettext as _
from django.contrib.admin.utils import model_ngettext
from xadmin.plugins.actions import BaseActionView
from xadmin.views import filter_hook


class MarkAsReadAction(BaseActionView):
	action_name = "read_selected"
	description = _('Mark read selected %(verbose_name_plural)s')
	model_perm = 'change'

	@filter_hook
	def do_action(self, queryset):
		# check for change permission
		if not self.has_change_permission():
			raise PermissionDenied

		n = queryset.filter(is_read=False).update(is_read=True, read_datetime=timezone.now())
		from xadmin.auditlog import AuditLog
		AuditLog.bulk_update(self.request, queryset, fields=['is_read'])
		self.message_user(
			_("Successfully marked %(count)d %(items)s as read.") % {
				"count": n, "items": model_ngettext(self.opts, n)
			}, 'success'
		)
