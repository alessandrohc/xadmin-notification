# coding=utf-8
"""A user model with the two attributes the serializer expects.

``rest/serializers.py`` reads ``source.photo_url`` and ``source.has_photo``. Neither is
a Django attribute -- they belong to the host project's user model -- so a stock
``auth.User`` makes that serializer raise as soon as a notification has a source. The
model here provides them, and ``test_serializer.py`` records the coupling.
"""
from django.contrib.auth.models import AbstractUser
from django.urls import reverse


class StaffUser(AbstractUser):
    photo = models_photo = None

    @property
    def has_photo(self):
        return bool(self.first_name)

    @property
    def photo_url(self):
        return '/media/photos/{0}.png'.format(self.username) if self.has_photo else ''

    def get_absolute_url(self):
        return reverse('xadmin:index')
