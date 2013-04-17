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

from batchimport.views import import_start, import_options, import_execute

urlpatterns = patterns('',
                       # Activation keys get matched by \w+ instead of the more specific
                       # [a-fA-F0-9]{40} because a bad activation key should still get to the view;
                       # that way it can return a sensible "invalid key" message instead of a
                       # confusing 404.
						url(r'^import_start/$',
							import_start,
							name='batchimport_import_start'),
						url(r'^import_options/$',
                           import_options,
                           name='batchimport_import_options'),
                       url(r'^import_execute/$',
                           import_execute,
                           name='batchimport_import_execute'),
                       )
