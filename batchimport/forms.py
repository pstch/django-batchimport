from django import forms
from batchimport.util import get_model_list, get_column_choice_list, get_model_fields
import batchimport.batchimport_settings


import_model_list = get_model_list()

class UploadImportFileForm(forms.Form):
	model_for_import = forms.ChoiceField(import_model_list, label='What are you importing?')
	import_file = forms.FileField(label='Select your XLS file:')

class ImportOptionsForm(forms.Form):
	show_successful_imports = forms.BooleanField(initial=batchimport.batchimport_settings.BATCH_IMPORT_SHOW_SUCCESSFUL_IMPORTS, required=False)
	show_successful_updates = forms.BooleanField(initial=batchimport.batchimport_settings.BATCH_IMPORT_SHOW_SUCCESSFUL_UPDATES, required=False)
	show_errors = forms.BooleanField(initial=batchimport.batchimport_settings.BATCH_IMPORT_SHOW_ERRORS, required=False)
	stop_on_first_error = forms.BooleanField(initial=batchimport.batchimport_settings.BATCH_IMPORT_STOP_ON_FIRST_ERROR, required=False)
	update_dupes = forms.BooleanField(initial=batchimport.batchimport_settings.BATCH_IMPORT_UPDATE_DUPS, required=False)
	start_row = forms.IntegerField(initial=batchimport.batchimport_settings.BATCH_IMPORT_START_ROW, required=False)
	end_row = forms.IntegerField(initial=batchimport.batchimport_settings.BATCH_IMPORT_END_ROW, required=False)
	def __init__(self, model_for_import, save_file_name, *args, **kwargs):
		super(ImportOptionsForm, self).__init__(*args, **kwargs)
		self.process_options = {}
		
		# Initialize several lists to be used later...
		self.model_field_names = []
		self.relation_info_dict = {}
		
		# Get a list of columns from the uploaded spreadsheet.
		# This will be either a list of example values or a list
		# of column headers.
		xls_column_option_list = get_column_choice_list(save_file_name)
		
		# Get a list of field names from the selected model
		# for import.
		self.mapping_only = False
		
		model_list = []
		if 'relation' in model_for_import:
			import_model_info_list = model_for_import.split('%')
			model_list.append(import_model_info_list[0])
			if len(import_model_info_list) > 1:
				model_list.append(import_model_info_list[2])
			self.mapping_only = True
		else:
			model_list = [model_for_import]
		
		for model_name in model_list:

			# In this field_tuple_list is the following for each field in the current model:
			# - field.name: The name of the field.
			# - related_model_app_name: Name of the app for any 
			#		related model name (if there is one).
			# - related_model_name: Name of the related model
			#		itself (again, if there is one).
			# - related_model_field_name_list: List of fields on the
			#		related model (for mapping the current model's 
			#		field to the related model).
			model_field_tuple_list = get_model_fields(model_name, self.mapping_only)
			
			# Iterate over this field_tuple_list and create a form field 
			# for each of the following FOR EACH FIELD in the model:
			#		- xls_columns_available (list of columns from the spreadsheet)
			#		- default_value_field (default value if none is in the spreadsheet)
			#		- related_field_mapping (list of fields on the related model)
			#		- id_field (to specify whether this field is in the group of
			#			fields for this model that together can be used to uniquely
			#			identify an instance of the model.
			for field_tuple in model_field_tuple_list:
				base_field_name = field_tuple[0]
				full_field_name = model_name + '.' + base_field_name
				
				# XLS column name list for this field.
				xls_column_field_name = full_field_name + '-xls_column'
				self.model_field_names.append(xls_column_field_name)
				initial_value = self._get_initial_value(xls_column_option_list, base_field_name)
				self.fields[xls_column_field_name] = forms.ChoiceField(xls_column_option_list, label='Spreadsheet column:', required=False, initial=initial_value)

				# ID selection checkmark (see template for example)
				is_id_field_name = full_field_name + '-is_id_field'
				self.model_field_names.append(is_id_field_name)
				if not self.mapping_only:
					self.fields[is_id_field_name] = forms.BooleanField(required=False,initial=True)
				else:
					self.fields[is_id_field_name] = forms.BooleanField(required=False,initial=False)
				
				if not self.mapping_only:
					related_model_app_name = field_tuple[1]
					related_model_name = field_tuple[2]
					field_mapping_list = field_tuple[3]
					
					# Get list of fields on the related model as needed.
					related_field_choice_list = []
					if field_mapping_list:
						for related_field_name in field_mapping_list:
							related_field_choice_list.append((related_field_name, related_field_name))
					self.relation_info_dict[full_field_name] = (related_model_app_name, 
															    related_model_name,
															    related_field_choice_list)
		
					# Default value form field.
					default_value_field_name = full_field_name + '-default_value'
					self.model_field_names.append(default_value_field_name)
					self.fields[default_value_field_name] = forms.CharField(label="Default value", max_length=100, required=False)
					
					# List of fields on the related model on which to map this field.
					mapping_choice_field_name = full_field_name + '-mapping_choice'
					self.model_field_names.append(mapping_choice_field_name)
					self.fields[mapping_choice_field_name] = forms.ChoiceField(related_field_choice_list, label='Related model field mapping', required=False)
			self.import_info_dict = self.get_import_info_dict()
			
	def get_import_info_dict(self):
		import_info_dict = {}
		for field_name in self.model_field_names:
			field_name_parts = field_name.split('.')
			model_name = field_name_parts[-2]
			base_field_name = field_name_parts[-1].split('-')[0]
			if not model_name in import_info_dict.keys():
				import_info_dict[model_name] = {}
			model_field_dict = import_info_dict[model_name]
			if not base_field_name in model_field_dict.keys():
				model_field_dict[base_field_name] = []
			field_list = model_field_dict[base_field_name]
			field_list.append(self[field_name])
		return import_info_dict
	
	def get_process_options_dict(self):
		if not self.process_options:
			process_options = {}
			process_options['show_successful_imports'] = self['show_successful_imports']
			process_options['show_successful_updates'] = self['show_successful_updates']
			process_options['show_errors'] = self['show_errors']
			process_options['stop_on_first_error'] = self['stop_on_first_error']
			process_options['update_dupes'] = self['update_dupes']
			process_options['start_row'] = self['start_row']
			process_options['end_row'] = self['end_row']
			self.process_options = process_options
		return self.process_options
		
	def _get_initial_value(self, xls_column_option_list, field_name):
		if field_name[-1] == '*':
			field_name = ''.join(field_name[:-1])
		choice_index = -1
		for item in xls_column_option_list:
			choice = item[1]
			if field_name.lower() == choice.lower():
				choice_index = item[0]
				break
		return str(choice_index)