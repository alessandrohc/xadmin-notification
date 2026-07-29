# coding=utf-8
"""The pt_BR catalogue: shipped, compiled, in sync, and actually used."""
import gettext
import pathlib
import shutil
import subprocess
import tempfile
import unittest

from django.test import SimpleTestCase
from django.utils import translation

LOCALE = (
    pathlib.Path(__file__).resolve().parent.parent
    / "xplugin_notification"
    / "locale"
    / "pt_BR"
    / "LC_MESSAGES"
)


def catalog(path):
    with open(path, "rb") as handle:
        return gettext.GNUTranslations(handle)


class ShippedCatalogTests(SimpleTestCase):

    def test_the_source_and_the_compiled_catalogue_are_present(self):
        self.assertTrue((LOCALE / "django.po").is_file())
        self.assertTrue((LOCALE / "django.mo").is_file())

    def test_it_declares_its_language(self):
        self.assertEqual(catalog(LOCALE / "django.mo").info().get("language"), "pt_BR")

    def test_every_message_is_translated(self):
        untranslated = [
            msgid
            for msgid, msgstr in catalog(LOCALE / "django.mo")._catalog.items()
            if msgid and not msgstr
        ]
        self.assertEqual(untranslated, [])

    def test_no_entry_is_left_fuzzy(self):
        # msgfmt drops fuzzy entries, so a fuzzy string silently shows in English.
        lines = (LOCALE / "django.po").read_text(encoding="utf-8").splitlines()
        fuzzy = [
            index
            for index, line in enumerate(lines, 1)
            if line.startswith("#,") and "fuzzy" in line
        ]
        self.assertEqual(fuzzy, [])


@unittest.skipIf(shutil.which("msgfmt") is None, "gettext tools not installed")
class CompiledInSyncTests(SimpleTestCase):
    """Compared message by message, never byte by byte.

    msgfmt writes its own headers and strips POT-Creation-Date, so two correct builds
    differ as files.
    """

    def test_the_committed_mo_matches_a_fresh_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            fresh = pathlib.Path(tmp) / "fresh.mo"
            subprocess.run(
                ["msgfmt", "--check", "-o", str(fresh), str(LOCALE / "django.po")],
                check=True,
            )
            committed = catalog(LOCALE / "django.mo")._catalog
            rebuilt = catalog(fresh)._catalog
        self.assertEqual(set(committed), set(rebuilt))
        differing = {
            key: (committed[key], rebuilt[key])
            for key in set(committed) & set(rebuilt)
            if key and committed[key] != rebuilt[key]
        }
        self.assertEqual(differing, {})


class ActiveTranslationTests(SimpleTestCase):

    def test_the_app_label_is_translated(self):
        from django.apps import apps

        config = apps.get_app_config("xplugin_notification")
        with translation.override("pt-br"):
            self.assertEqual(str(config.verbose_name), "Notificações Administrativas")

    def test_english_is_the_source_language(self):
        from django.apps import apps

        config = apps.get_app_config("xplugin_notification")
        with translation.override("en"):
            self.assertEqual(str(config.verbose_name), "Administrative Notifications")

    def test_the_model_metadata_is_translated(self):
        from xplugin_notification.models import Notification

        with translation.override("pt-br"):
            self.assertEqual(
                str(Notification._meta.verbose_name), "Notificação Administrativa"
            )
