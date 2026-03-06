import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
	slug = models.SlugField(
		default=getattr(settings, 'XNOTIFICATION_SLUG_DEFAULT', uuid.uuid4),
		editable=False
	)
	source = models.ForeignKey(settings.AUTH_USER_MODEL,
	                           verbose_name=_("User source"),
	                           on_delete=models.CASCADE, blank=True, null=True,
	                           related_name="notification_admin_source")

	recipient = models.ForeignKey(settings.AUTH_USER_MODEL,
	                              verbose_name=_("User recipient"),
	                              on_delete=models.CASCADE,
	                              related_name="notification_admin_recipient")

	message = models.TextField(_("Message"))

	url = models.CharField(_("URL"), blank=True, max_length=1024)

	is_read = models.BooleanField(_("Read"), default=False)
	read_datetime = models.DateTimeField(_("Read date"), blank=True, null=True)

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return str(self.message)

	class Meta:
		verbose_name = _("Administrative Notification")
		verbose_name_plural = _("Administrative Notifications")
		ordering = ['-created_at', 'is_read']
