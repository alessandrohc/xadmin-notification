# coding=utf-8
"""Minimal settings for the xadmin-notification suite.

Three things here are load-bearing.

**guardian.** ``register.notify`` assigns four per-object permissions with
``assign_perm``, and ``GuardianAdminPlugin`` filters a changelist with
``get_objects_for_user``. Both need the app and its authentication backend.

**MIGRATION_MODULES maps the app to None.** The package ships an empty ``migrations``
package by design: the host project points MIGRATION_MODULES at a module it generates
per instance. Mapping to None here tells Django the app has no migrations, so the
runner creates its table from the model.

**The suite's own user model.** ``rest/serializers.py`` reads ``source.photo_url`` and
``source.has_photo`` -- attributes of the *host project's* user model, not Django's. The
model below provides them, which is what lets the serializer be tested at all; the
coupling itself is recorded in test_serializer.py.
"""
from pathlib import Path

from django import forms

# ---------------------------------------------------------------------------
# Django >= 5.0 compat shim for xadmin -- test-only, on purpose. See #7093.
# xadmin/views/dashboard.py builds property(_get_choices,
# forms.ChoiceField._set_choices); Django 5.0 dropped that pair, so importing
# xadmin.views raises AttributeError and django.setup() never finishes.
# ---------------------------------------------------------------------------
if not hasattr(forms.ChoiceField, '_set_choices'):
    forms.ChoiceField._set_choices = forms.ChoiceField.choices.fset

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'xadmin-notification-test-only-not-a-secret'
DEBUG = False
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',

    'crispy_forms',
    'crispy_bootstrap4',
    'reversion',
    'import_export',
    'formtools',
    'rest_framework',
    'guardian',

    'xadmin',
    'xplugin_notification',
    'test_notification',
]

AUTH_USER_MODEL = 'test_notification.StaffUser'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
]

# guardian would otherwise create a database row for the anonymous user on migrate.
ANONYMOUS_USER_NAME = None

MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # Restores HttpRequest.is_ajax() for xadmin's benefit, not this package's.
    'test_notification.middleware.RequestToolsMiddleware',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

ROOT_URLCONF = 'test_notification.urls'

STATIC_URL = '/static/'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CRISPY_TEMPLATE_PACK = 'bootstrap4'
CRISPY_ALLOWED_TEMPLATE_PACKS = ('bootstrap4',)

# See the module docstring: the package ships no migration by design.
MIGRATION_MODULES = {'xplugin_notification': None}
