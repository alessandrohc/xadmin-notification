# xadmin-notification

In-admin notifications for staff users: a bell in the navbar with an unread count, a
dropdown that loads messages over AJAX, a changelist, and per-object permissions so a
recipient only ever sees their own.

Another app sends one in a single call:

```python
from xplugin_notification.register import notification

notification.notify(user, message="Your export is ready", url="/admin/exports/12/")
notification.notify_groups((editors,), message="Deploy window at 22:00")
```

| | |
| --- | --- |
| Python | 3.10 – 3.13 |
| Django | 4.2 – 5.2 |
| xadmin | the `fabricadigital` fork, 3.6.25 or newer |

Also required, and declared as of 1.6.0: **djangorestframework** (the dropdown's feed),
**django-guardian** (per-object permissions) and **django-crispy-forms** (the detail
layout). `setup.py` declared *no* dependencies at all, so a clean install raised
`ImportError` during `django.setup()`.

**xadmin is not a declared dependency, on purpose.** Every module here imports it, but
the xadmin this plugin builds on is the fork installed from git (dist name `xadmin`),
while the `xadmin` on PyPI is an unrelated project abandoned at 0.6.1. Declaring it
would make a clean `pip install` resolve to that dead package or fail outright, so the
requirement is stated here and enforced by the test suite, which imports the real fork.

## Install

```shell
pip install git+https://github.com/alessandrohc/xadmin-notification.git@v1.6.0
```

```python
INSTALLED_APPS = [
    # ...
    'rest_framework',
    'guardian',
    'crispy_forms',
    'xplugin_notification',
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
]
```

## What the host project has to provide

Three things this package depends on and does **not** ship. All three are satisfied by
`plus_base`; a different project has to satisfy them too.

- **A `<app>_<model>_rest` model view.** The navbar menu builds its `list_url` with
  `get_model_url(model, "rest")`, and neither this package nor xadmin registers such a
  route — `plus_base/xpublique/adminx/__init__.py` does, pointing it at a DRF viewset.
  Without it the menu raises `NoReverseMatch`.
- **`photo_url` and `has_photo` on the user model.** The serializer reads them off a
  notification's `source`. Neither is a Django attribute, so with a stock `auth.User` the
  feed raises as soon as a notification has a sender.
- **The model-level `view_notification` permission.** `notify()` grants four
  *per-object* permissions through guardian, which is what `GuardianAdminPlugin` filters
  on — but xadmin checks the model permission first, so a recipient who was only ever
  notified gets **403** on "All notifications". The bell and the read-and-redirect link
  are not gated, so they can always read what they were sent; only the full list is.

## Migrations: the package ships none, by design

There is one model and no migration file — only an empty `migrations` package. The host
project points the app at a module it generates per instance:

```python
MIGRATION_MODULES = {'xplugin_notification': 'myproject_config.xplugin_notification.migrations'}
```

A project that does neither gets **no table**: Django reads an empty migrations package
as "fully migrated". Either point `MIGRATION_MODULES` somewhere writable and run
`makemigrations`, or map the app to `None` so the table is built from the model — which
is what this package's own test settings do.

## Sending notifications

`notify(recipient, message, source=None, slug=None, **options)` returns the
`Notification`, or `None` when the recipient is not active staff — notifications are an
admin feature, and the call is silent about it because callers notify in bulk.

**`slug` is an identity, not a label.** Identity is `(slug, recipient, source)`, and the
write is an `update_or_create`, so re-notifying the same slug **updates** the existing
row instead of adding one. That is how a standing notification works ("3 pending
reviews"). Left out, the slug defaults to a fresh `uuid4`, so every call is a new row.

Any extra keyword lands on the model, `url=` being the useful one: it is where clicking
the notification takes the user, and clicking also marks it read.

`notify_groups(groups, ...)` fans out to the active staff members of those groups,
`distinct()`, so a user in two targeted groups is notified once.

## Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| `XNOTIFICATION_SLUG_DEFAULT` | `uuid.uuid4` | Default slug for notifications sent without one. Read when the model class is defined, so it applies per process. |
| `XADMIN_NOTIFICATION_PERMISSIONS` | `()` | Permission *actions* ("view", "change") required to read the REST feed. All of them are required. |
| `NOTIFICATION_ADMIN_OPTS` | `object` | Base class (or its dotted path) for the notification admin, for a project that wants to extend it. |

Per model admin: `notification_active`, `notification_max_num` (25),
`notification_unlimited`, `notification_detail_active`,
`notification_guardian_protected`.

## Compatibility

Every cell below was run against the real xadmin fork — whole suite, no skips:

| | Django 4.2 | Django 5.0 | Django 5.1 | Django 5.2 |
| --- | --- | --- | --- | --- |
| Python 3.10 | pass | pass | pass | pass |
| Python 3.11 | pass | pass | pass | pass |
| Python 3.12 | pass | pass | pass | pass |
| Python 3.13 | n/a | n/a | pass | pass |

`n/a` is Django's own limit: 4.2 and 5.0 do not support 3.13.

Two things needed from the environment on Django 5.x are xadmin's gaps, not this
package's, and the test settings supply both: `ChoiceField._set_choices` (dropped in
5.0, monkeypatched by `xadmin/views/dashboard.py`) and `HttpRequest.is_ajax()` (removed
in 4.0, called by `xadmin/plugins/ajax.py` on every admin view). Neither shim ships.

## Running the tests

```shell
PYTHONPATH=../django-xadmin python runtests.py
PYTHONPATH=../django-xadmin python runtests.py test_notification.test_register
```

With coverage (currently 99%):

```shell
pip install -e ".[test]"
PYTHONPATH=../django-xadmin coverage run runtests.py && coverage report -m
```

The suite declares its own user model, because the serializer needs `photo_url` and
`has_photo`, and registers a stub `rest` model view, because the menu needs that route.
Both stand in for the host project — see "What the host project has to provide".

## Known issues

- **`notify_groups` can return `None` entries.** `notify()` returns `None` for a
  recipient it skips and `notify_groups` appends whatever it returns, so a caller
  counting the result counts skipped users too. In practice its queryset already
  excludes non-staff and inactive users, so the list is currently all real.
- **A freshly created notification holds a `UUID` object in `slug`, not a string.** The
  field default is the `uuid.uuid4` callable; `SlugField.get_prep_value` stringifies it
  on the way to the database, so `obj.slug == "3f2b…"` is False before a reload and True
  after. Harmless, and worth knowing before comparing one.
- **The serializer does not escape `message`.** It is authored by the sending app and
  rendered as HTML by both the dropdown and the detail view, so a caller passing
  user-supplied text passes it straight to other users' browsers. The changelist is
  safe: it renders `str(instance)`, which strips tags.

## 1.6.0

- Packaging moved to `pyproject.toml` (PEP 517/621); `setup.py` is gone. It declared no
  build backend, no `python_requires`, no classifiers and **no dependencies at all**,
  while guardian, DRF and crispy are imported at module level.
- **`xplugin_notification/tests.py` is gone from the wheel — it was broken on Python
  3.12+.** It used `assertEquals` and `assertNotEquals`, which Python 3.12 removed, so
  merely collecting it raised `AttributeError` — inside the distribution, where a
  consumer's test runner could pick it up. Both of its scenarios live on in
  `test_notification/test_register.py`, and `test_compat.py` fails if any removed
  `unittest` alias comes back.
- **`rest/permisstion.py` is now `rest/permission.py`.** The old spelling remains as a
  shim for one release, since the name was public even though only `plugin.py` imported
  it; it will be dropped in the next minor version.
- Catalogue header comment block filled in (its functional fields were already correct).
- Test suite added: 133 tests, 99% coverage, run across 14 Python × Django cells.
