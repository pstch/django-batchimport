from django.db.models import get_model
from django.shortcuts import render_to_response
from django.template import RequestContext

from batchimport.utils import import_objects_from_excel, import_relationships_from_excel, \
							  export_objects_to_excel, export_relationships_to_excel, \
							  render_excel

def start(request, template="start.html", extra_context=None):
	if extra_context is None:
		extra_context = {}
	context = get_context(request, extra_context)
	return render_to_response(template, {}, \
									  context_instance=context)

def import_object(request, template="import_object.html", extra_context=None, \
					   return_action=start):
	if extra_context is None:
		extra_context = {}
	if request.method == 'POST':
		upload_file = request.FILES['upload_file']
		file_contents = upload_file.read()	
		app_name = request.POST.get('app', None)	
		model_name = request.POST.get('model', None)
		model_for_import = get_model(app_name, model_name)
		if model_for_import and file_contents:
			objects_added, objects_updated, objects_not_changed, objects_not_changed_error = \
						import_objects_from_excel(model_for_import, file_contents, request=request)
		extra_context['objects_added'] = objects_added
		extra_context['objects_updated'] = objects_updated
		extra_context['objects_not_changed'] = objects_not_changed
		extra_context['objects_not_changed_error'] = objects_not_changed_error
		context = get_context(request, extra_context)
		return render_to_response(template, {}, \
                                context_instance=context)
	else:
		return return_action(request)

def import_relation(request, template="import_relation.html", extra_context=None, \
					   return_action=start):
	if extra_context is None:
		extra_context = {}
	if request.method == 'POST':
		upload_file = request.FILES['upload_file']
		file_contents = upload_file.read()	
		app_name = request.POST.get('app', None)	
		model_name = request.POST.get('model', None)
		field_name = request.POST.get('field', None)
		clean = request.POST.get('clean', '0')
		clean = int(clean)
		model_for_import = get_model(app_name, model_name)
		if model_for_import and file_contents:
			relationships_added, relationships_not_added, relationships_not_added_error = \
						import_relationships_from_excel(model_for_import, field_name, clean, file_contents, request=request)
		extra_context['relationships_added'] = relationships_added
		extra_context['relationships_not_added'] = relationships_not_added
		extra_context['relationships_not_added_error'] = relationships_not_added_error
		extra_context['clean'] = clean
		context = get_context(request, extra_context)
		return render_to_response(template, {}, \
                                context_instance=context)
	else:
		return return_action(request)


def export(request, app_name, model_name, field_name=None, extra_context=None):
	if extra_context is None:
		extra_context = {}
	export_model = get_model(app_name, model_name)
	export_object_list = export_model.objects.all()
	if not field_name:
		return export_objects_to_excel(export_model, export_object_list, request=request)
	else:
		return export_relationships_to_excel(export_model, field_name, \
														 export_object_list, request=request)
def get_context(request, extra_context=None):
    if not extra_context:
        extra_context={}
    context = RequestContext(request)
    for key, value in extra_context.items():
        context[key] = callable(value) and value() or value
    return context
