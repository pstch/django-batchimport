import sys
from os.path import join, isfile
import datetime

from django.db import models
from django.db.models import get_model
from django.http import HttpResponse



import xlrd
from xlwt import Workbook, XFStyle

def import_objects_from_excel(import_model, file_contents, override_import_dict=None, request=None):
	import_dict = override_import_dict or import_model.import_dict or None	
	if not import_dict:
		raise Exception('No import dictionary!')
	import_wb = xlrd.open_workbook(file_contents=file_contents)
	import_sheet = import_wb.sheet_by_index(0)
	objects_added = 0
	objects_updated = 0
	objects_not_changed = 0
	objects_not_changed_error = 0
	for rx in range(1, import_sheet.nrows):
		identity_dict = {}		
		#try:
		col_idx = 0
		object_value_dict = {}
		for cx in range(0, import_sheet.ncols):
			cell_value = import_sheet.cell_value(rowx=rx, colx=cx)
			if import_sheet.cell_type(rowx=rx, colx=cx) == xlrd.XL_CELL_DATE:
				date_tuple = xlrd.xldate_as_tuple(cell_value, import_wb.datemode)
				cell_value = datetime.date(date_tuple[0],date_tuple[1],date_tuple[2])
			if col_idx in import_dict['object_colmap']['self_field_cols']:
				prop_name = import_dict['object_colmap']['field_col_mapping'][col_idx]
				object_value_dict[prop_name] = cell_value
				if prop_name in import_dict['object_colmap']['identity_fields']:
					identity_dict[prop_name] = cell_value
			if col_idx in import_dict['object_colmap']['simple_related_cols']:
				prop_name, related_app, related_model, related_field = import_dict['object_colmap']['field_col_mapping'][col_idx]
				try:
					related_model = get_model(related_app, related_model)
					related_object_get_dict = {related_field:cell_value}
					related_object = related_model.objects.get(**related_object_get_dict)
				except related_model.DoesNotExist:
					related_object = None
				object_value_dict[prop_name] = related_object
			col_idx += 1
		try:
			current_object = import_model.objects.get(**identity_dict)
			new_object = False
		except import_model.DoesNotExist:
			current_object = import_model()
			new_object = True
		# Process overrides:
		for override in import_dict['overrides'].keys():
			override_setting = import_dict['overrides'][override]
			override_value = callable(override_setting) and override_setting(request) or override_setting 
			object_value_dict[override] = override_value

		save_changes = False
		for prop_name in object_value_dict.keys():
			#print current_object
			#print prop_name
			#print object_value_dict[prop_name]
			if not save_changes:
				current_value = getattr(current_object, prop_name)
				if current_value != object_value_dict[prop_name]:
					save_changes = True
			setattr(current_object, prop_name, object_value_dict[prop_name])
		if save_changes:				
			current_object.save()
			if new_object:
				objects_added += 1
			else:
				objects_updated += 1	
		else:
			objects_not_changed += 1	
		#except:
		#	objects_not_changed_error += 1
	return objects_added, objects_updated, objects_not_changed, objects_not_changed_error

def import_relationships_from_excel(import_model, field_name, clean, file_contents, override_import_dict=None, request=None):
	import_dict = override_import_dict or import_model.import_dict or None	
	if not import_dict:
		raise Exception('No import dictionary!')
	import_wb = xlrd.open_workbook(file_contents=file_contents)
	import_sheet = import_wb.sheet_by_index(0)
	relation_info_dict = import_dict['relationship_colmap'][field_name]
	already_cleaned_object_list = []
	relationships_added = 0
	relationships_not_added = 0
	relationships_not_added_error = 0

	for rx in range(1, import_sheet.nrows):
		#try:
		src_identity_dict = {}
		trg_identity_dict = {}
		src_identity_col_list = relation_info_dict['src_identity_cols']		
		trg_identity_col_list = relation_info_dict['trg_identity_cols']

		# Get source object for this row.
		for src_identity_col in src_identity_col_list:
			src_identity_field_name = relation_info_dict['src_col_mapping'][src_identity_col]
			cell_value = import_sheet.cell_value(rowx=rx, colx=src_identity_col)
			if import_sheet.cell_type(rowx=rx, colx=src_identity_col) == xlrd.XL_CELL_DATE:
				date_tuple = xlrd.xldate_as_tuple(cell_value, import_wb.datemode)
				cell_value = datetime.date(date_tuple[0],date_tuple[1],date_tuple[2])
			src_identity_dict[src_identity_field_name] = cell_value
		src_object = import_model.objects.get(**src_identity_dict)
		related_objects_set = getattr(src_object, field_name)

		# Clean out related objects property if needed but only if you've
		# not already done so for this particular src object.
		if (not src_object in already_cleaned_object_list) and clean:
			related_objects_set.clear()
			already_cleaned_object_list.append(src_object)

		# Get the target (related) object for this row.
		trg_app_name = relation_info_dict['trg_app']
		trg_model_name = relation_info_dict['trg_model']
		trg_model = get_model(trg_app_name, trg_model_name)
		for trg_identity_col in trg_identity_col_list:
			trg_identity_field_name = relation_info_dict['trg_col_mapping'][trg_identity_col]
			cell_value = import_sheet.cell_value(rowx=rx, colx=trg_identity_col)
			if import_sheet.cell_type(rowx=rx, colx=trg_identity_col) == xlrd.XL_CELL_DATE:
				print cell_value
				date_tuple = xlrd.xldate_as_tuple(cell_value, import_wb.datemode)
				cell_value = datetime.date(date_tuple[0],date_tuple[1],date_tuple[2])
			trg_identity_dict[trg_identity_field_name] = cell_value
		trg_object = trg_model.objects.get(**trg_identity_dict)

		# Add the trg object to the related objects property of the src object.
		if not trg_object in related_objects_set.all():
			related_objects_set.add(trg_object)
			relationships_added += 1
		else:
			relationships_not_added += 1
		#except:
		#	relationships_not_changed_error += 1
	return relationships_added, relationships_not_added, relationships_not_added_error

	

def export_objects_to_excel(export_model, export_object_list, override_export_dict=None, request=None):
	export_dict = override_export_dict or export_model.export_dict or None
	if not export_dict:
		file_name = 'ERROR.XLS'
		col_title_list = ['ERROR','OCCURRED']
		data_row_list = []
	else:
		filename = export_model.__name__ + '_data_' + datetime.datetime.now().strftime('%y%m%d%m%s') + '.xls'
		col_title_list = export_dict['object_export'][:]
		data_row_list = []
		for export_object in export_object_list:
			row_items_list = []
			for field_name in export_dict['object_export']:
				current_value = getattr(export_object, field_name)
				try:
					if field_name in export_dict['overrides']:
						override_setting = import_dict['overrides'][field_name]
						current_value = callable(override_setting) and override_setting(request, current_value) or override_setting 
				except KeyError:
					pass
				row_items_list.append(current_value)
			data_row_list.append(row_items_list)
	return render_excel(filename, col_title_list, data_row_list)	


def export_relationships_to_excel(export_model, relation_field_name, export_object_list, override_export_dict=None, request=None):
	export_dict = override_export_dict or export_model.export_dict or None
	if not export_dict:
		file_name = 'ERROR.XLS'
		col_title_list = ['ERROR','OCCURRED']
		data_row_list = []
	else:
		relation_export_dict = export_dict['relationship_export'][relation_field_name]
		filename = export_model.__name__ + '_' + relation_field_name + '_relationships_' + datetime.datetime.now().strftime('%y%m%d%m%s') + '.xls'
		src_col_title_list = relation_export_dict['self_fields'][:]
		src_col_title_list = [export_model.__name__ + '.' + title for title in src_col_title_list]
		trg_col_title_list = relation_export_dict['related_fields'][:]
		trg_col_title_list = [relation_field_name + '.' + title for title in trg_col_title_list]
		col_title_list = src_col_title_list
		col_title_list.extend(trg_col_title_list)
		data_row_list = []
		for export_object in export_object_list:
			related_object_field_value = getattr(export_object, relation_field_name)
			if related_object_field_value:
				related_object_list = related_object_field_value.all()
				for related_object in related_object_list:
					row_items_list = []
					for field_name in relation_export_dict['self_fields']:
						row_items_list.append(getattr(export_object, field_name))
					for field_name in relation_export_dict['related_fields']:
						row_items_list.append(getattr(related_object, field_name))
					data_row_list.append(row_items_list)
	return render_excel(filename, col_title_list, data_row_list)



def render_excel(filename, col_title_list, data_row_list):
	import StringIO
	output = StringIO.StringIO()
	export_wb = Workbook()
	export_sheet = export_wb.add_sheet('Export')
	col_idx = 0
	for col_title in col_title_list:
		export_sheet.write(0, col_idx, col_title)
		col_idx += 1
	row_idx = 1
	for row_item_list in data_row_list:
		col_idx = 0
		for current_value in row_item_list:
			if current_value:
				current_value_is_date = False
				if isinstance(current_value, datetime.datetime):
					current_value = xlrd.xldate.xldate_from_datetime_tuple((current_value.year, current_value.month, \
													current_value.day, current_value.hour, current_value.minute, \
													current_value.second), 0)
					current_value_is_date = True
				elif isinstance(current_value, datetime.date):
					current_value = xlrd.xldate.xldate_from_date_tuple((current_value.year, current_value.month, \
													current_value.day), 0)
					current_value_is_date = True
				elif isinstance(current_value, datetime.time):
					current_value = xlrd.xldate.xldate_from_time_tuple((current_value.hour, current_value.minute, \
													current_value.second))
					current_value_is_date = True
				elif isinstance(current_value, models.Model):
					current_value = str(current_value)
				if current_value_is_date:
					s = XFStyle()
					s.num_format_str = 'M/D/YY'
					export_sheet.write(row_idx, col_idx, current_value, s)
				else:
					export_sheet.write(row_idx, col_idx, current_value)
			col_idx += 1
		row_idx += 1
	export_wb.save(output)
	output.seek(0)
	response = HttpResponse(output.getvalue())
	response['Content-Type'] = 'application/vnd.ms-excel'
	response['Content-Disposition'] = 'attachment; filename='+filename
	return response

