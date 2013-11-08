"""
URLConf for Django batch import and update.

If the default behavior of the batchimport views is acceptable to
you, simply use a line like this in your root URLConf to set up the
default URLs for batchimport:

    (r'^batchimport/', include('batchimport.urls')),

But if you'd like to customize the behavior (e.g., by passing extra
arguments to the various views) or split up the URLs, feel free to set
up your own URL patterns for these views instead.

"""


from django.conf.urls.defaults import *

from views import ImportUploadView, ImportOptionsView, ImportRunView

urlpatterns = patterns('',
                       url(r'^upload/$',
                           ImportUploadView.as_view(),
                           name='batchimport_upload'),
                       url(r'^options/$',
                           ImportOptionsView.as_view(),
                           name='batchimport_options'),
                       url(r'^run/$',
                           ImportRunView.as_view(),
                           name='batchimport_run'),
)
