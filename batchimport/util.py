from os.path import join, isfile

from django.conf import settings
from django.db import models
from django.db.models import get_model, related
from django.db.models.fields import AutoField

import xlrd

import batchimport_settings


def process_import_file(import_file, session):
    """
    Open the uploaded file and save it to the temp file location specified
    in BATCH_IMPORT_TEMPFILE_LOCATION, adding the current session key to
    the file name. Then return the file name so it can be stored in the
    session for the current user.

    **Required arguments**
    
    ``import_file``
        The uploaded file object.
       
    ``session``
        The session object for the current user.
        
    ** Returns**
    
    ``save_file_name``
        The name of the file saved to the temp location.
        
        
    """
    import_file_name = import_file.name
    session_key = session.session_key
    save_file_name = session_key + import_file_name
    destination = open(join(batchimport_settings.BATCH_IMPORT_TEMPFILE_LOCATION, save_file_name), 'wb+')
    for chunk in import_file.chunks():
        destination.write(chunk)
    destination.close()
    return save_file_name

def get_model_list():
    """
    Get a list of models for which the user can batch import information. 
    Start by assuming that the user has specified the list in the
    settings.py file. If not (or it's empty) go through all installed
    apps and get a list of models.
    
    """
    model_list = []
    relation_list = []
    settings_model_list = batchimport_settings.BATCH_IMPORT_IMPORTABLE_MODELS
    if settings_model_list:
        for model in settings_model_list:
            model_list.append((model, model.split('.')[len(model.split('.'))-1]))
    else:
        for app in settings.INSTALLED_APPS:
            if not app == 'batchimport':
                try:
                    mod = __import__(app+'.models')
                    if 'models' in dir(mod):
                        for item in dir(mod.models):
                            if item and (type(getattr(mod.models, item)) == type(models.Model)):
                                if not (app+'.models.'+item, item) in model_list:
                                    # You have to try to instantiate it to rule out any models
                                    # you might find in the app that were simply imported (i.e. not
                                    # REALLY part of that app).
                                    model = get_model(app, item)
                                    if model:
                                        model_list.append(('.'.join([model.__module__, model.__name__]), item))
                                        relationship_list = _get_relation_list(model)
                                        for relationship in relationship_list:
                                            relation_list.append(relationship)
                except ImportError:
                    pass
    model_list.sort()
    relation_list.sort()
    for relation in relation_list:
        model_list.append(relation)
    return model_list

def get_column_choice_list(save_file_name):
    """
    Use xlrd to open the file whose name/path is sent in via ``save_file_name``.
    Once open, retrieve a list of values representing the first value in
    each column of the spreadsheet. Hopefully, this will be a header row
    but if it's not, it will be a list of sample values, one for each column.
    
    **Required arguments**
    
    ``save_file_name``
       The activation key to validate and use for activating the
       ``User``.
        
    ** Returns**
    
    ``column_choice_list``
        A list of choice tuples to be used to get the mapping between a model
        field and a spreadsheet column.

    """
    column_choice_list = []
    column_choice_list.append((-1, 'SELECT COLUMN'))
    filepath = join(batchimport_settings.BATCH_IMPORT_TEMPFILE_LOCATION, save_file_name)
    if not isfile(filepath):
        raise NameError, "%s is not a valid filename" % save_file_name
    book = xlrd.open_workbook(filepath)
    sheet = book.sheet_by_index(0)
    column_index = 0
    for column in range(0,sheet.ncols):
        column_item = sheet.cell_value(rowx=0, colx=column)
        column_choice_list.append((column_index, column_item))
        column_index = column_index + 1
    return column_choice_list

def get_model_fields(model_name, importing_relations_only=False):
    """
    Use reflection to get the list of fields in the supplied model. If any
    of the fields represented a related field (ForeignKey, OneToOne, etc)
    then the function will get a list of fields for the related model. 
    These fields will be used to prompt the user to map a spreadsheet
    column value to a specific field on the RELATED model for related
    fields.
    
    For example, suppose you had a model for Student that had a field
    for name, a field for date of birth and a foreign key field to teacher.
    The spreadsheet the user uploads may have name, dob, teacher.
    The related model is Teacher which has a bunch of fields too. By
    getting a list of these fields, we can prompt the user later to
    specify WHICH field on the related model we should use to search
    for the specific Teacher we want to relate to a given student (from
    a row in the spreadsheet). This gives the user the flexibility
    of creating a spreadsheet with student_name, student_dob, and
    teacher_id OR teacher_email OR teacher_name, etc. 
    
    **Required arguments**
    
    ``model_name``
       The (full) name of the model for which a batch import is being
       attempted.
        
    ** Returns**
    
    ``field_tuple_list``
        Each entry is a tuple in the form:
            (field_name, [list_of_field_names_for_related_model]) 

    """
    field_tuple_list = []
    app_name = model_name.split(".")[0]
    specific_model_name = model_name.split('.')[-1]
    model = get_model(app_name, specific_model_name)
    opts = model._meta
    field_tuple_list.extend(_get_field_tuple_list(opts.fields, importing_relations_only))
    many_to_many_field_tuples = _get_field_tuple_list(opts.many_to_many, importing_relations_only)
    for field_tuple in many_to_many_field_tuples:
        if not field_tuple in field_tuple_list:
            field_tuple_list.append(field_tuple)
    #field_tuple_list.extend(_get_field_tuple_list(opts.many_to_many, importing_relations_only))
    return field_tuple_list


def _get_field_tuple_list(field_list, importing_relations_only):
    """
    Used by ``get_model_fields`` to retrieve a list of tuples. Each tuple consists of a
    field name and, in the case of a field representing a relationship to another
    model (via ManyToMany, OneToOne, etc), a list of fields on the related model.
    **Required arguments**
    
    ``field_list``
        List of fields to process.
       
    ``importing_relations_only``
        A boolean telling the function whether or not the system is currently just
        importing relationship data as opposed to object data.
       
    ** Returns**
    
    ``field_tuple_list``
        List of tuples.
        
    """
    field_tuple_list = []
    for field in field_list:
        if not importing_relations_only:
            if field.null:
                field_name = field.name
            else:
                field_name = field.name + '*'
        else:
            field_name = field.name
        related_model_field_name_list = []
        # We will skip all '_ptr' and AutoField fields so we don't disrupt
        # django's inner workings.
        related_model_name = None
        related_model_app_name = None
        import_uneditable_flag = field.editable or batchimport_settings.BATCH_IMPORT_UNEDITABLE_FIELDS 
        if import_uneditable_flag and (not field.name[-4:] == '_ptr') and (not field.__class__ == AutoField):
            if issubclass(field.__class__, related.RelatedField):
                related_model_app_name = field.rel.to.__module__.split('.')[0]
                # We'll ignore all django-specific models (such as User, etc).
                if not related_model_app_name == 'django':
                    related_model_name = field.rel.to.__name__
                    related_model = get_model(related_model_app_name, related_model_name)
                    for sub_field in related_model._meta.fields:
                        # For fields representing a relationship to another model
                        # we'll ignore all _ptr fields, AutoFields AND
                        # all related fields.
                        if (not sub_field.name[-4:] == '_ptr') and \
                          (not sub_field.__class__ == AutoField) and \
                          (not issubclass(sub_field.__class__, related.RelatedField)):
                            related_model_field_name_list.append(sub_field.name)
                else:
                    continue
#            field_tuple_list.append((field.name, related_model_app_name, related_model_name, related_model_field_name_list))
            field_tuple_list.append((field_name, related_model_app_name, related_model_name, related_model_field_name_list))
    return field_tuple_list

def _get_relation_list(model):
    full_model_name = '.'.join([model.__module__, model.__name__])
    relation_tuple_list = []
    
    # Iterate over the fields for the provided model
    # and for each "related" type field, get the corresponding model
    # and model class name.
    for field_list in [model._meta.fields, model._meta.many_to_many]:
        for field in field_list:
            related_model_name = None
            related_model_app_name = None
            if (not field.name[-4:] == '_ptr') and (not field.__class__ == AutoField):
                
                if issubclass(field.__class__, related.RelatedField):
                    if not field.__class__ == related.ForeignKey:
                        related_model_app_name = field.rel.to.__module__.split('.')[0]
                        # We'll ignore all django-specific models (such as User, etc).
                        if not related_model_app_name == 'django':
                            related_model_name = field.rel.to.__name__
                            full_related_model_name = '.'.join([field.rel.to.__module__, related_model_name])
                            relation_tuple_list.append((full_model_name+'%relation'+field.name+'%' + full_related_model_name, \
                                                        'Mapping: ' + model.__name__ + '-' + \
                                                        related_model_name))
                    else:
                        continue
    return relation_tuple_list

class ModelImportInfo(object):
    """
    The ModelImportInfo class handles all the management of the model
    information and which values from which spreadsheet cells go to
    which field values -- and a whole lot more. Basically it's a
    collection of assorted dictionaries of information allowing the
    import code to be a lot cleaner...
    
    """
    IMPORT_COLUMN = 0
    IS_IDENTITY = 1
    DEFAULT_VALUE = 2
    MAPPING_CHOICES = 3
    OBJECT_IMPORT = 1
    RELATIONSHIP_IMPORT = 2
    def __init__(self, import_model_name, field_value_dict, relation_info_dict):
        self.import_model_name = import_model_name
        self.field_value_dict = field_value_dict
        self.relation_info_dict = relation_info_dict
        
        # Figure out import_mode from incoming model_for_import.
        self.import_mode = ModelImportInfo.OBJECT_IMPORT
        self.model_name_list = []
        self.mapping_field_name = None
        import_model_info_list = import_model_name.split('%')
        self.model_name_list.append(import_model_info_list[0])
        if len(import_model_info_list) > 1:
            self.model_name_list.append(import_model_info_list[2])
            self.mapping_field_name = import_model_info_list[1].split('relation')[1]
            self.import_mode = ModelImportInfo.RELATIONSHIP_IMPORT
        # Get model objects for each model.
        self.model_list = []
        for full_model_name in self.model_name_list:
            app_name = full_model_name.split('.')[0]
            model_name = full_model_name.split('.')[-1]
            model = get_model(app_name, model_name)
            self.model_list.append(model)
        self.model_for_import = self.model_list[0]
        if self.import_mode == ModelImportInfo.RELATIONSHIP_IMPORT:
            self.source_model = self.model_list[0]
            self.target_model = self.model_list[1]
        else:
            self.source_model = None
            self.target_model = None
            
        # Populate the various dictionaries we'll need later...
        self.base_field_names_by_model = {self.model_for_import.__name__: []}
        self.field_name_by_col_dict = {self.model_for_import.__name__: {}}
        self.default_by_field_name_dict = {self.model_for_import.__name__: {}}
        self.id_field_names_by_model_dict = {self.model_for_import.__name__: []}
        self.related_model_info_by_field_name_dict = {self.model_for_import.__name__: {}}
        self.field_value_override_dict = {self.model_for_import.__name__: {}}
        
        if self.import_mode == ModelImportInfo.RELATIONSHIP_IMPORT:
            self.base_field_names_by_model[self.target_model.__name__] = []
            self.field_name_by_col_dict[self.target_model.__name__] = {}
            self.default_by_field_name_dict[self.target_model.__name__] = {}
            self.id_field_names_by_model_dict[self.target_model.__name__] = []
            self.related_model_info_by_field_name_dict[self.target_model.__name__] = {}
            self.field_value_override_dict[self.target_model.__name__] = {}
            
        for field_name in self.field_value_dict.keys():
            field_value = self.field_value_dict[field_name]
            full_field_name = field_name.split('-')[0]
            full_model_name = '.'.join(field_name.split('-')[0].split('.')[:-1])
            field_name = ''.join(field_name.split('*'))            
            field_name_parts = field_name.split('.')
            model_name = field_name_parts[-2]
            base_field_name, field_type = field_name_parts[-1].split('-')
            if not base_field_name in self.base_field_names_by_model[model_name]:
                self.base_field_names_by_model[model_name].append(base_field_name)
            if field_type == 'xls_column' and field_value > -1:
                self.field_name_by_col_dict[model_name][field_value] = base_field_name
            elif field_type == 'is_id_field' and field_value == 1:
                self.id_field_names_by_model_dict[model_name].append(base_field_name)
            elif field_type == 'default_value':
                self.default_by_field_name_dict[model_name][base_field_name] = field_value
            elif field_type == 'mapping_choice' and field_value:
                relation_info_tuple = self.relation_info_dict[full_field_name]
                self.related_model_info_by_field_name_dict[model_name][str(base_field_name)] = [relation_info_tuple[0],
                                                                                relation_info_tuple[1],
                                                                                str(field_value)]
            if batchimport_settings.BATCH_IMPORT_VALUE_OVERRIDES:
                print 'in override code ' + full_model_name + ' ' + base_field_name 
                try:
                    override_value = batchimport_settings.BATCH_IMPORT_VALUE_OVERRIDES[full_model_name][base_field_name]
                    self.field_value_override_dict[model_name][base_field_name] = override_value
                    print override_value
                except:
                    pass
    
    def get_import_object_dicts(self, request, row_list):
        """Generate a dictionary of name:value entries in a dictionary
        that can be used later for obtaining an object from a manager."""
        return self._get_object_dicts(request, row_list, self.model_for_import.__name__)

    def get_relationship_source_id_dict(self, request, row_list):
        """Generate a dictionary of name:value entries in a dictionary
        that can be used later for obtaining an object from a manager."""
        return self._get_object_dicts(request, row_list, self.source_model.__name__)[1]

    def get_relationship_target_id_dict(self, request, row_list):
        """Generate a dictionary of name:value entries in a dictionary
        that can be used later for obtaining an object from a manager."""
        return self._get_object_dicts(request, row_list, self.target_model.__name__)[1]


    def _get_object_dicts(self, request, row_list, model_name):
        """Generate a dictionary of name:value entries in a dictionary
        that can be used later for obtaining an object from a manager."""
        import_object_dict = {}
        import_object_id_dict = {}
        total_field_list = []
        total_field_list.extend(self.base_field_names_by_model[model_name])
        # Get values for all the fields we can from the spreadsheet row...
        for index, cell_value in enumerate(row_list):
            if str(index) in self.field_name_by_col_dict[model_name].keys():
                base_field_name = self.field_name_by_col_dict[model_name][str(index)]
                total_field_list.remove(base_field_name)
                field_value = self.get_field_value(request, base_field_name, model_name, cell_value)
                if field_value:
                    import_object_dict[str(base_field_name)] = field_value
                    if base_field_name in self.id_field_names_by_model_dict[model_name]:
                        import_object_id_dict[str(base_field_name)] = field_value
            
        # Now process the leftovers (fields for the current model whose value
        # we can't get from the spreadsheet).
        for base_field_name in total_field_list:
            field_value = self.get_field_value(request, base_field_name, model_name, None)
            if field_value:
                import_object_dict[str(base_field_name)] = field_value
                if base_field_name in self.id_field_names_by_model_dict[model_name]:
                    import_object_id_dict[str(base_field_name)] = field_value
            
        if not import_object_id_dict:
            import_object_id_dict = import_object_dict
        return import_object_dict, import_object_id_dict


    def get_field_value(self, request, base_field_name, model_name, start_value=None):
        field_value = None
        if self.import_mode == ModelImportInfo.OBJECT_IMPORT:
            default_value = self.default_by_field_name_dict[model_name][base_field_name]
        else:
            default_value = None
        field_value = start_value or default_value
        if field_value and base_field_name in self.related_model_info_by_field_name_dict[model_name].keys():
            related_app_name, related_model_name, mapping_field_name = self.related_model_info_by_field_name_dict[model_name][base_field_name]
            related_object_keyword_dict = {}
            related_object_keyword_dict[str(mapping_field_name+'__iexact')] = str(field_value)
            related_model_class = get_model(related_app_name, related_model_name)
            try:
                related_object = related_model_class.objects.get(**related_object_keyword_dict)
                field_value = related_object
            except:
                field_value = None
        # Check for override field value and substitute it if available.
        try:
            field_value = self.field_value_override_dict[model_name][base_field_name]
            # Check to see if this references a function and if so, call it.
            override_items = field_value.split('.')
            if len(override_items) > 1:
                override_value_function_name = override_items[-1]
                override_value_module_name = '.'.join(override_items[:-1])
                override_value_module = __import__(override_value_module_name, fromlist=[override_value_function_name])
                override_value_function=getattr(override_value_module, override_value_function_name)
                field_value = override_value_function(request, start_value) 
        except:
            pass
        return field_value
        