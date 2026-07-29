# coding=utf-8
"""Registrations the suite needs, discovered by xadmin's autodiscover.

**A `<app>_<model>_rest` model view.** ``NotificationMenuPlugin`` builds its
``list_url`` with ``get_model_url(model, "rest")``, and neither this package nor xadmin
registers such a route -- the host project does, in
``plus_base/xpublique/adminx/__init__.py``, pointing it at a DRF viewset. So the menu
cannot render in a project that does not provide it, and the suite has to stand in for
that project. The stub below only has to make the name reversible; what it returns is
the host's business.

The user model is also registered so the changelist's ``recipient``/``source`` filters
have an admin to resolve against.
"""
from xadmin.sites import AdminPath, site
from xadmin.views import BaseAdminView

from test_notification.models import StaffUser


class RestStub(BaseAdminView):
    """Stands in for the host project's per-model REST viewset."""

    def get(self, request, *args, **kwargs):
        from django.http import JsonResponse

        return JsonResponse({"results": []})


class StaffUserAdmin:
    list_display = ("username", "is_staff", "is_active")
    search_fields = ("username",)


site.register(StaffUser, StaffUserAdmin)
site.register_modelview(AdminPath("rest/", RestStub, name="%s_%s_rest"))
