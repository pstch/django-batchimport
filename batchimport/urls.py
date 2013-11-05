"""
URLConf for Django batch import and update.

If the default behavior of the batchimport views is acceptable to
you, simply use a line like this in your root URLConf to set up the
default URLs for batchimport:

    (r'^batchimport/', include('batchimport.urls', namespace = 'batchimport')),

But if you'd like to customize the behavior (e.g., by passing extra
arguments to the various views) or split up the URLs, feel free to set
up your own URL patterns for these views instead.

"""


from django.conf.urls.defaults import *

from batchimport.views import import_start, import_options, import_execute

urlpatterns = patterns('',
                       url(r'^start/$',
                           import_start,
                           name='start'),
                       url(r'^options/$',
                           import_options,
                           name='options'),
                       url(r'^execute/$',
                           import_execute,
                           name='execute'),
)
