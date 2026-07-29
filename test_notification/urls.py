# coding=utf-8
"""URLs for the suite: xadmin's site, which carries the package's two views."""
import xadmin
from django.urls import path

urlpatterns = [
    # site.urls is the (patterns, app_name, namespace) triple, which path() unpacks on
    # its own; include() refuses a 3-tuple.
    path('admin/', xadmin.site.urls),
]
