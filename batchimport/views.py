"""
Views which allow users batch import/update any data for which
a model is present.

"""
import sys
import os

from os.path import join, isfile

from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist
from django.views.generic import TemplateView
from django.views.generic.edit import FormView

import xlrd

from batchimport.utils import process_import_file, ModelImportInfo
from batchimport.forms import UploadImportFileForm
from batchimport.forms import ImportOptionsForm
from batchimport.batchimport_settings import *

def handle_uploaded_file(f,target):
    with open(target, 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)

class ImportUploadView(FormView):
        template_name = "batchimport/upload.html"
        form_class = UploadImportFileForm

        def form_valid(self,form):
                handle_uploaded_file(self.request.FILES['import_file'],
                                     join(BATCHIMPORT_TEMPDIR,
                                          self.request.FILES['import_file'].name))
                                                                          
                self.request.session['batchimport_file_name'] = self.request.FILES['import_file'].name
                self.request.session['batchimport_model'] = form.cleaned_data['model_for_import']
                return HttpResponseRedirect("batchimport:options")

class ImportOptionsView(FormView):
        template_name = "batchimport/options.html"
        processing_template_name = "batchimport/processing.html"

        form_class = ImportOptionsForm
	
        def dispatch(self, request, *args, **kwargs):
                try:
                        self.import_file_name = request.session['batchimport_file_name']
                        self.import_model = request.session['batchimport_model']
                except KeyError:
                        return HttpResponseRedirect("batchimport:upload")
                return super(ImportOptionsView, self).dispatch(request, *args, **kwargs)

        def get_context_data(self, **kwargs):
                context = super(ImportOptionsView, self).get_context_data(**kwargs)
                context['model_for_import'] = self.import_model
                return context

        def form_valid(self, form):
                request.session['batchimport_options'] = {}
                for option in form.get_process_options_dict().keys():
                        request.session['process_options'][option] = form.cleaned_data[option]

                model_field_value_dict = {}
                for field in form.model_field_names:
                        model_field_value_dict[field] = form.cleaned_data[field]

                model_import_info = ModelImportInfo(self.import_model,
                                                    model_field_value_dict,
                                                    form.relation_info_dict)
                request.session['batchimport_info'] = model_import_info

                self.template_name = self.processing_template_name

class ImportRunView(TemplateView):
        template_name = "batchimport/run.html"


        def dispatch(self, request, *args, **kwargs):
                try:
                        self.import_file_name = request.session['batchimport_file_name']
                        self.import_model = request.session['batchimport_model']
                        self.import_options = request.session['batchimport_options']
                        self.import_info = request.session['batchimport_info']

                        self.init_status_dict()
                except KeyError:
                        return HttpResponseRedirect("batchimport:upload")
                return super(ImportRunView, self).dispatch(request, *args, **kwargs)

        def get_context_data(self, **kwargs):
                context = super(ImportRunView, self).get_context_data(**kwargs)

                self.run_import()

                for key, value in self.status_dict.items():
                        context[key] = value

                return context

        def init_status_dict(self):
                status_dict = {}

                status_dict['start_row'] = self.import_options['start_row']
                status_dict['end_row'] = self.import_options['end_row']

                status_dict['row_count'] = 0
                status_dict['processed_row_count'] = 0

                status_dict['imported_count'] = 0
                status_dict['updated_count'] = 0

                status_dict['combined_messages'] = []
                status_dict['import_messages'] = []
                status_dict['update_messages'] = []
                status_dict['error_messages'] = []

                self.status_dict = status_dict

        def run_import(self):
                # Open Excel file
                filepath = join(BATCHIMPORT_TEMPDIR, self.import_file_name)

                try:
                        book = xlrd.open_workbook(filepath)
                        sheet = book.sheet_by_index(0)
                        status_dict['row_count'] = sheet.nrows

                        # Determine the last row of the spreadsheet to be processed.
                        if self.import_options['end_row'] == -1:
                                self.import_options['end_row'] = sheet.nrows
                                self.status_dict['end_row'] = self.import_options['end_row']

                        if self.import_info.import_mode == ModelImportInfo.OBJECT_IMPORT:
                                self.status_dict = _do_batch_import(request,
                                                                    self.import_info,
                                                                    book,
                                                                    sheet,
                                                                    self.import_options,
                                                                    self.status_dict)
                        else:
                                self.status_dict = _do_relation_import(request,
                                                                       self.import_info,
                                                                       book,
                                                                       sheet,
                                                                       self.import_options,
                                                                       self.status_dict)

                except Exception, e:
                        # Report error
                        self.status_dict['error_messages'].append({ 'name' : 'Import Error',
                                                                    'critical' : 'Yes',
                                                                    'message' : '%s' % e,
                                                                    'info' : 'File: %s' % filepath})
                        return


def _do_batch_import(request, model_import_info, book, sheet, process_option_dict, status_dict):
	"""
	This function actually processes the incoming spreadsheet for object
	import. While it can handle relationships, especially simple foreign
	key relationships, etc, it is best to actually use the relationship
	import below to import relationship data...
	
	Basically, it goes row by row in the spreadsheet, matches up the cell
	value for each column to an appropriate field in the model into which
	we're importing. Then it uses the identity columns to see if the current
	row represents an object already in the database. If so, it updates
	that object (if the settings say to do so. If not, then it creates it.  
	
    **Required arguments**
    
    ``request``
    	Current HTTP request. This is used in case your override function needs
    	current session information.
    	
	``model_import_info``
		This is the ModelImportInfo class (from batchimport.util) that holds 
		all the various mapping information for the models and their fields.
		
	``book``
		Current Excel workbook being processed.
		
	``sheet``
		The current worksheet in the workbook being processed.
		
	``process_option_dict``
		This is a dictionary specifying the various mechanics options for 
		the process (whether to stop on error, whether to update dupes, etc)
		
	``status_dict``
		This is the status information dictionary that will be used to display
		results to the user after completion of the process.
    
    **Optional arguments**
       
    none.    
    
	"""
	import_object_dict = {}
	import_object_id_dict = {}

	for row in range(process_option_dict['start_row']-1,process_option_dict['end_row']):
		status_dict['imported_count'] += 1
		try:
			row_value_list = []
			for cell in sheet.row(row):
				if cell.ctype == 3:
					date_tuple = xlrd.xldate_as_tuple(cell.value, book.datemode)
					cell_value = str(date_tuple[0]) + '-' + str(date_tuple[1])  + '-' + str(date_tuple[2])
				else:
					cell_value = cell.value
				row_value_list.append(cell_value)

			import_object_dict, import_object_id_dict = model_import_info.get_import_object_dicts(request, row_value_list)
	
			try:
				# See if the current row represents a dupe.
				dupe_in_db = model_import_info.model_for_import.objects.get(**import_object_id_dict)
				if process_option_dict['update_dupes']: 
					for key in import_object_dict.keys():
						setattr(dupe_in_db, key, import_object_dict[key])
					dupe_in_db.save()

					status_msg = 'Updated : #%d' % str(row)
					status_dict['updated_count'] += 1
					if process_option_dict['show_successful_updates']:
						status_dict['combined_messages'].append(status_msg)
					status_dict['update_messages'].append(status_msg)
					
			except ObjectDoesNotExist:
				# The object doesn't exist. Go ahead and add it.
				new_object = model_import_info.model_for_import(**import_object_dict)
				new_object.save()

				status_msg = 'Imported : #%d'  %row 
				status_dict['imported_count'] += 1
				if process_option_dict['show_successful_imports']:
					status_dict['combined_messages'].append(status_msg)
				status_dict['import_messages'].append(status_msg)
		except:
                        status_dict['error_messags'].append({'name' : 'Row processing error',
                                                             'critical' : 'No' if not process_option_dict['stop_on_first_error'] else "Yes",
                                                             'description' : str(sys.exc_info()[1]),
                                                             'info' : 'Row: %s' % row})
			if process_option_dict['stop_on_first_error']:
				break
	return status_dict


def _do_relation_import(request, model_import_info, book, sheet, process_option_dict, status_dict):
	"""
	This function processes the incoming spreadsheet for relationship data.
	It is assumed that each row in the spreadsheet has enough data to 
	find two objects: a source object and a target object. This function
	then simply finds both object, maps the target object to the source
	object and saves the source object. 
	
    **Required arguments**
    
    ``request``
    	Current HTTP request. This is used in case your override function needs
    	current session information.
    	
	``model_import_info``
		This is the ModelImportInfo class (from batchimport.util) that holds 
		all the various mapping information for the models and their fields.
		
	``book``
		Current Excel workbook being processed.
		
	``sheet``
		The current worksheet in the workbook being processed.
		
	``process_option_dict``
		This is a dictionary specifying the various mechanics options for 
		the process (whether to stop on error, whether to update dupes, etc)
		
	``status_dict``
		This is the status information dictionary that will be used to display
		results to the user after completion of the process.
    
    **Optional arguments**
       
    none.    
    
	"""
	relationship_source_id_dict = {}
	relationship_target_id_dict = {}
	for row in range(process_option_dict['start_row']-1,process_option_dict['end_row']):
		status_dict['imported_count'] += 1
		try:
			row_value_list = []
			for cell in sheet.row(row):
				if cell.ctype == 3:
					date_tuple = xlrd.xldate_as_tuple(cell.value, book.datemode)
					cell_value = str(date_tuple[0]) + '-' + str(date_tuple[1])  + '-' + str(date_tuple[2])
				else:
					cell_value = cell.value
				row_value_list.append(cell_value)

			relationship_source_id_dict = model_import_info.get_relationship_source_id_dict(request, row_value_list)
			relationship_target_id_dict = model_import_info.get_relationship_target_id_dict(request, row_value_list)

			source_object = model_import_info.source_model.objects.get(**relationship_source_id_dict)
			target_object = model_import_info.target_model.objects.get(**relationship_target_id_dict)

			related_field_collection = getattr(source_object, model_import_info.mapping_field_name)
			related_field_collection.add(target_object)

			source_object.save()

			status_msg = 'Updated : #%d' % str(row)
			status_dict['updated_count'] += 1
			if process_option_dict['show_successful_updates']:
				status_dict['combined_messages'].append(status_msg)
			status_dict['update_messages'].append(status_msg)
		except:
                        status_dict['error_messags'].append({'name' : 'Row processing error',
                                                             'critical' : 'No' if not process_option_dict['stop_on_first_error'] else "Yes",
                                                             'description' : str(sys.exc_info()[1]),
                                                             'info' : 'Row: %s' % row})
			if process_option_dict['stop_on_first_error']:
				break
	return status_dict
