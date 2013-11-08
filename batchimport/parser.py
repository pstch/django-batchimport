import sys
from os.path import join, isfile

from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist


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
        status_dict['processed_count'] += 1
        try:
            row_value_list = []
            for cell in sheet.row(row):
                if cell.ctype == 3:
                    date_tuple = xlrd.xldate_as_tuple(cell.value, book.datemode)
                    cell_value = str(date_tuple[0]) + '-' + str(date_tuple[1])  + '-' + str(date_tuple[2])
                else:
                    cell_value = cell.value
                    row_value_list.append(cell_value)
                if cell_value == "TEST123":
                    raise Exception("TEST 123 EXCEPTION")

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

        except Exception, e:
            status_dict['error_messages'].append({'name' : 'Row processing error',
                                                  'critical' : 'No' if not process_option_dict['stop_on_first_error'] else "Yes",
                                                  'description' : '%s' % e,
                                                  'info' : ["Row: %s",
                                                            "Exception : %s" % (row,str(type(e)))]})
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
        status_dict['processed_count'] += 1
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
        except Exception, e:
            status_dict['error_messags'].append({'name' : 'Row processing error',
                                                 'critical' : 'No' if not process_option_dict['stop_on_first_error'] else "Yes",
                                                 'description' : str(sys.exc_info()[1]),
                                                 'info' : 'Row: %s' % row})
            if process_option_dict['stop_on_first_error']:
                break

    return status_dict

