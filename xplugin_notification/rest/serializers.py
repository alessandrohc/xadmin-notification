# coding=utf-8
from django.utils.formats import date_format
from rest_framework import serializers


class NotificationSerializer(serializers.ModelSerializer):
	id = serializers.IntegerField(source="pk")
	user_name = serializers.SerializerMethodField("get_user_name")
	user_url = serializers.SerializerMethodField("get_user_url")
	user_photo_url = serializers.SerializerMethodField("get_user_photo_url")
	message = serializers.SerializerMethodField('get_message')
	url = serializers.SerializerMethodField("get_absolute_url", read_only=True)
	mark_as_read_url = serializers.SerializerMethodField("get_mark_as_read_url", read_only=True)
	created = serializers.SerializerMethodField("get_created", read_only=True)

	def get_user_name(self, instance):
		return str(instance.source) if instance.source else ''

	def get_user_url(self, instance):
		return str(instance.source.get_absolute_url()) if instance.source else ''

	def get_user_photo_url(self, instance):
		return str(instance.source.photo_url) if instance.source and instance.source.has_photo else ''

	def get_absolute_url(self, instance):
		# Retorna a URL de destino direta; o mark-as-read é tratado separadamente via AJAX
		return instance.url or self.context['view'].get_admin_url("notification_admin_read", object_id=instance.pk)

	def get_mark_as_read_url(self, instance):
		return self.context['view'].get_admin_url("xplugin_notification_mark_as_read", pk=instance.pk)

	def get_message(self, instance):
		return str(instance.message)

	def get_created(self, instance):
		return date_format(instance.created_at, format="DATETIME_FORMAT")

	class Meta:
		fields = (
			'id',
			'user_name',
			'user_url',
			'user_photo_url',
			'message',
			'url',
			'is_read',
			'mark_as_read_url',
			'read_datetime',
			'created'
		)
