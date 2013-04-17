"""
Views which allow users batch import/update any data for which
a model is present.

"""
import sys
import os
from os.path import join, isfile

from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.core.urlresolvers import reverse
from django.template import RequestContext
from django.core.exceptions import ObjectDoesNotExist

import xlrd

from util import process_import_file, ModelImportInfo
from forms import UploadImportFileForm
from forms import ImportOptionsForm
from batchimport_settings import *


# TODO:
# - Add overrides for forms everywhere.
# - Add overrides for templates too.

def import_start(request, extra_context=None):
	"""
    Start the import process by presenting/accepting a form into
	which the user specifies the model for whom an XLS file is
	being uploaded and the file/path of the file to upload.
	
	The names of the models presented are either from those
	specified in the setting BATCH_IMPORT_IMPORTABLE_MODELS or
	using the installed_apps list for the project.
	
	The names of "relationships" (for the import of many-to-many
	data) are retrieved using reflection of the model's related fields
	and are in the format of
		"Mapping: [Source_Model]-[Target-Model]
	
	For example, suppose you have a model called Student which has
	a many to many relationship to a model called Parent. Then you
	would see the following added to the list of importable models:
		Mapping: Student-Parent
		
	NOTE: The list of mappings is also retrieved from the list of 
	importable models whether that comes from the 
	BATCH_IMPORT_IMPORTABLE_MODELS setting or from installed_apps.
    
    Customize template used by setting the BATCH_IMPORT_START_TEMPLATE
    setting.
    
    **Required arguments**
    
    none.
    
    **Optional arguments**
       
    ``extra_context``
        A dictionary of variables to add to the template context. Any
        callable object in this dictionary will be called to produce
        the end result which appears in the context.    
    
	"""
	if request.method == 'POST':
		form = UploadImportFileForm(request.POST, request.FILES)
		if form.is_valid():
			save_file_name = process_import_file(form.cleaned_data['import_file'], request.session)
			selected_model = form.cleaned_data['model_for_import']
			request.session['save_file_name'] = save_file_name
			request.session['model_for_import'] = selected_model
			return HttpResponseRedirect(reverse('batchimport_import_options'))
	else:
		form = UploadImportFileForm()
	if extra_context is None:
		extra_context = {}

	context = RequestContext(request)
	for key, value in extra_context.items():
		context[key] = callable(value) and value() or value
		
	return render_to_response(BATCH_IMPORT_START_TEMPLATE, 
							  {'form': form},
                              context_instance=context)
	
def import_options(request, extra_context={}):
	"""
	This view allows the user to specify options for how the system should
	attempt to import the data in the uploaded Excel spreadsheet.
	
	There are two types of options: those that govern the process as a whole
	(whether to stop on errors, whether to update duplicates, etc) and options
	for mapping a given model field to a given spreadsheet column (as well as
	some other items about that model field.
	
	For Import of Object Data:
	In the case of a straight data import (of new objects as opposed to
	an import of relationship mapping information -- see below) the 
	following options are available to the user for each field in the model:
	
		field_name: This is a simple label showing the name of the specific
			model field. If it has an asterisk, that field is required in 
			the underlying model.
		
		Spreadsheet Column: This is a drop-down list of columns from the 
			spreadsheet. If no column headers are present, then each option
			shows the value in that column's cell.
		
		Is Identity: This allows the user to specify this specific spreadsheet
			value as being part of potentially multi-part "key" to identify
			whether or not this row in the spreadsheet refers to an object
			already in the database.
			
		Default Value: This is the value to use if the spreadsheet contains
			no data for that specific field.
			
		Mapping Field: For those fields that represent a related model, this
			item represents a list of fields on THAT (related) model. The
			user will select from these fields and the system will use that
			selection in trying to grab the appropriate object from the
			database using the value in the spreadsheet.
    
	For Import of Relationship/Mapping Data:
	In the case of the user uploading relationship data between models, the
	following options are presented to the user for each field in each 
	(source and target) model.
	
		model_name: This is a simple label showing the name of the source or
			target model.
			
		field_name: This is a simple label showing the name of the specific
			model field.
		
		Spreadsheet Column: This is a drop-down list of columns from the 
			spreadsheet. If no column headers are present, then each option
			shows the value in that column's cell.
		
		Is Identity: This allows the user to specify this specific spreadsheet
			value as being part of potentially multi-part "key" to identify
			whether or not this row in the spreadsheet refers to an object
			already in the database.
			
    Customize template used by setting the BATCH_IMPORT_OPTIONS_TEMPLATE
    setting.
    
    **Required arguments**
    
    none.
    
    **Optional arguments**
       
    ``extra_context``
        A dictionary of variables to add to the template context. Any
        callable object in this dictionary will be called to produce
        the end result which appears in the context.    
    
	"""
	try:
		save_file_name = request.session['save_file_name']
		model_for_import = request.session['model_for_import']
	except KeyError:
		# Either we don't have a file or we don't know what we're importing.
		# So restart the process with a blank form (which will show the
		# model list).
		form = UploadImportFileForm()
		context = RequestContext(request)
		for key, value in extra_context.items():
			context[key] = callable(value) and value() or value
		return render_to_response(BATCH_IMPORT_START_TEMPLATE, 
								  {'form': form},
		                          context_instance=context)

	# Process the request.
	if request.method == 'POST':
		# Add the various options to the session for use during execution.
		form = ImportOptionsForm(model_for_import, save_file_name, request.POST, request.FILES)
		if form.is_valid():
			# Put the list of models and the various user-specified options in the session 
			# for use during execution.
			request.session['process_options'] = {}
			for option in form.get_process_options_dict().keys():
				request.session['process_options'][option] = form.cleaned_data[option]
			model_field_value_dict = {}
			for field_name in form.model_field_names:
				model_field_value_dict[field_name] = form.cleaned_data[field_name]
			model_import_info = ModelImportInfo(model_for_import, model_field_value_dict, form.relation_info_dict)
			request.session['model_import_info'] = model_import_info
		else:
			context = RequestContext(request)
			for key, value in extra_context.items():
				context[key] = callable(value) and value() or value
			return render_to_response(BATCH_IMPORT_OPTIONS_TEMPLATE, {'form': form, 'model_for_import':model_for_import},
		                          context_instance=context)

		# Redirect to the Processing template which displays a "processing,
		# please wait" notice and immediately fires off execution of the import.
		context = RequestContext(request)
		for key, value in extra_context.items():
			context[key] = callable(value) and value() or value
		return render_to_response(BATCH_IMPORT_EXECUTE_TEMPLATE, {}, context_instance=context)
	else:
		form = ImportOptionsForm(model_for_import, save_file_name)
		context = RequestContext(request)
		for key, value in extra_context.items():
			context[key] = callable(value) and value() or value
		return render_to_response(BATCH_IMPORT_OPTIONS_TEMPLATE, {'form': form, 'model_for_import':model_for_import},
	                          context_instance=context)
	
def import_execute(request, extra_context={}):
	"""
	This is the view that actually processed the import based on the options
	set by the user in import_options (above).
	
	In addition to calling the appropriate import function (see below) this
	view also prepares the status information dictionary that will be used
	by those import functions and later used to render the results.
	
	The actual template used just immediately reloads the page to the
	results template.
			
    Customize template used by setting the BATCH_IMPORT_EXECUTE_TEMPLATE
    setting.
    
    **Required arguments**
    
    none.
    
    **Optional arguments**
       
    ``extra_context``
        A dictionary of variables to add to the template context. Any
        callable object in this dictionary will be called to produce
        the end result which appears in the context.    
    
	"""

	# Get the name of the uploaded Excel file for processing and the model
	# for which we're trying to import. If either are missing, send the user
	# back to the beginning of the process.
	try:
		model_import_info = request.session['model_import_info']
		save_file_name = request.session['save_file_name']
	except KeyError:
		# Either we don't have a file or we don't know what we're importing.
		# So restart the process with a blank form (which will show the
		# model list).
		form = UploadImportFileForm()
		context = RequestContext(request)
		for key, value in extra_context.items():
			context[key] = callable(value) and value() or value
		return render_to_response(BATCH_IMPORT_START_TEMPLATE, 
								  {'form': form},
		                          context_instance=context)

	# Retrieve the "import mechanics options". These will be set from the
	# user-specified options or from the settings-based defaults.
	process_option_dict = request.session['process_options']
	
	# Prepare the context to be sent to the template so we can load it
	# as we go along.
	status_dict = {}
	
	# Prepare for the results processing.
	status_dict['start_row'] = process_option_dict['start_row']
	status_dict['end_row'] = process_option_dict['end_row']
	status_dict['num_rows_in_spreadsheet'] = 0
	status_dict['num_rows_processed'] = 0
	status_dict['num_items_imported'] = 0
	status_dict['num_items_updated'] = 0
	status_dict['num_errors'] = 0
	status_dict['combined_results_messages'] = []
	status_dict['import_results_messages'] = []
	status_dict['update_results_messages'] = []
	status_dict['error_results_messages'] = []

	# Open the uploaded Excel file and iterate over each of its rows starting
	# start_row and ending at end_row.
	filepath = join(BATCH_IMPORT_TEMPFILE_LOCATION, save_file_name)
	if not isfile(filepath):
		status_dict['error_results_messages'].append('Error opening file. Uploaded file was either not found or corrupt.')
		return _render_results_response(request, status_dict, extra_context)
	
	# Try to open the uploaded Excel file. If it fails, bomb out.
	try:
		book = xlrd.open_workbook(filepath)
		sheet = book.sheet_by_index(0)
		status_dict['num_rows_in_spreadsheet'] = sheet.nrows
	except:
		status_dict['error_results_messages'].append('Error opening Excel file: '+ `sys.exc_info()[1]`)
		return _render_results_response(request, status_dict, extra_context)
	
	# Determine the last row of the spreadsheet to be processed.
	if process_option_dict['end_row'] == -1:
		process_option_dict['end_row'] = sheet.nrows
		status_dict['end_row'] = process_option_dict['end_row']

	if model_import_info.import_mode == ModelImportInfo.OBJECT_IMPORT:
		status_dict = _do_batch_import(request, model_import_info, book, sheet, process_option_dict, status_dict)
	else:
		status_dict = _do_relation_import(request, model_import_info, book, sheet, process_option_dict, status_dict)

	# Clean up...
	del request.session['save_file_name']
	del request.session['model_for_import']
	del request.session['process_options']
	del request.session['model_import_info']
	filepath = join(BATCH_IMPORT_TEMPFILE_LOCATION, save_file_name)
	if isfile(filepath):
		os.remove(filepath)

	# Render the response.
	return _render_results_response(request, status_dict, extra_context)


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
		status_dict['num_rows_processed'] = status_dict['num_rows_processed'] + 1
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
					status_msg = 'spreadsheet row#' + str(row)+' successfully updated.'
					status_dict['num_items_updated'] = status_dict['num_items_updated'] + 1
					if process_option_dict['show_successful_updates']:
						status_dict['combined_results_messages'].append(status_msg)
					status_dict['update_results_messages'].append(status_msg)
					
			except ObjectDoesNotExist:
				# The object doesn't exist. Go ahead and add it.
				new_object = model_import_info.model_for_import(**import_object_dict)
				new_object.save()
				status_msg = 'spreadsheet row#' + str(row)+' successfully imported.'
				status_dict['num_items_imported'] = status_dict['num_items_imported'] + 1
				if process_option_dict['show_successful_imports']:
					status_dict['combined_results_messages'].append(status_msg)
				status_dict['import_results_messages'].append(status_msg)
		except:
			status_dict['num_errors'] = status_dict['num_errors'] + 1
			status_msg = 'spreadsheet row#' + str(row)+' ERROR: ' + `sys.exc_info()[1]`
			if process_option_dict['show_errors']:
				status_dict['combined_results_messages'].append(status_msg)
			status_dict['error_results_messages'].append(status_msg)
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
		status_dict['num_rows_processed'] = status_dict['num_rows_processed'] + 1
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
			status_msg = 'spreadsheet row#' + str(row)+' successfully updated.'
			status_dict['num_items_updated'] = status_dict['num_items_updated'] + 1
			if process_option_dict['show_successful_updates']:
				status_dict['combined_results_messages'].append(status_msg)
			status_dict['update_results_messages'].append(status_msg)
		except:
			status_dict['num_errors'] = status_dict['num_errors'] + 1
			status_msg = 'spreadsheet row#' + str(row)+' ERROR: ' + `sys.exc_info()[1]`
			if process_option_dict['show_errors']:
				status_dict['combined_results_messages'].append(status_msg)
			status_dict['error_results_messages'].append(status_msg)
			if process_option_dict['stop_on_first_error']:
				break
	return status_dict

def _render_results_response(request, status_dict, extra_context):
	"""
	Laziness function. I got tired of typing this every time... 
    
	"""	
	if extra_context is None:
		extra_context = {}

	context = RequestContext(request)
	for key, value in extra_context.items():
		context[key] = callable(value) and value() or value

	return render_to_response(BATCH_IMPORT_RESULTS_TEMPLATE, status_dict, context_instance=context)
	