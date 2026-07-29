# coding=utf-8
"""Deprecated spelling of :mod:`xplugin_notification.rest.permission`.

The module was named ``permisstion`` until 1.6.0. Nothing outside this package is known
to import it -- the only importer was ``plugin.py`` -- but the name was public, so the
old path keeps working for one release. Import from ``.permission`` instead; this shim
will be removed in the next minor version.
"""
from xplugin_notification.rest.permission import HasNotificationPermission  # noqa: F401

__all__ = ["HasNotificationPermission"]
