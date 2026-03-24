from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from xadmin.views import BaseAdminView

from xplugin_notification.models import Notification


class NotificationReadAdminView(BaseAdminView):
	"""Update notifications as read."""
	model = Notification

	def init_request(self, *args, **kwargs):
		self.url = self.get_model_url(self.model, "changelist")

	def get(self, request, object_id, **kwargs):
		obj = get_object_or_404(self.model, pk=object_id, recipient=self.user)

		if not obj.is_read:
			obj.is_read = True
			obj.read_datetime = timezone.now()
			obj.save()

		return redirect(obj.url or self.url)


class MarkAsReadView(BaseAdminView):
	"""Mark a single notification as read via AJAX POST."""
	model = Notification

	def post(self, request, pk, *args, **kwargs):
		obj = get_object_or_404(
			self.model, pk=pk, recipient=self.user, is_read=False
		)
		obj.is_read = True
		obj.read_datetime = timezone.now()
		obj.save(update_fields=['is_read', 'read_datetime', 'updated_at'])

		from xadmin.auditlog import AuditLog
		AuditLog.update(request, obj, fields=['is_read'])

		return JsonResponse({'success': True})
