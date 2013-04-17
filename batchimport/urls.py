from django.conf.urls.defaults import *
from batchimport.views import start, import_object, import_relation, export

urlpatterns = patterns('',
                        url(r'^start/$',
                        	start,
                        	name='excel_start'),
                        url(r'^import_object/$',
                        	import_object,
                        	name='excel_import_object'),
                        url(r'^import_relation/$',
                        	import_relation,
                        	name='excel_import_relation'),
                        url(r'^export/(?P<app_name>\w+)/(?P<model_name>\w+)/$',
                        	export,
                        	name='excel_export_objects'),
                        url(r'^export/(?P<app_name>\w+)/(?P<model_name>\w+)/(?P<field_name>\w+)/$',
                        	export,
                        	name='excel_export_relations'),
                       )

