"""
The batchimport_settings.py module initializes itself with defaults but
allows for the values to be overridden via the django project's settings
file. 

NOTE: These values should be considered CONSTANTS even though I'm kind
of cheating and using them as variables to initialize them here.

"""

import settings

def get_setting(setting_name, default):
	"""
	A simple setting retrieval function to pull settings from the 
	main settings.py file.
	
	"""
	setting = default
	print setting_name
	print default
	try:
		setting=getattr(settings, setting_name)
	except (AttributeError, NameError):
		pass
	return setting
	
# INITIALIZE BATCHIMPORT SETTINGS...

BATCH_IMPORT_START_TEMPLATE = get_setting('BATCH_IMPORT_START_TEMPLATE', 'batchimport/start.html')
BATCH_IMPORT_OPTIONS_TEMPLATE = get_setting('BATCH_IMPORT_OPTIONS_TEMPLATE', 'batchimport/options.html')
BATCH_IMPORT_EXECUTE_TEMPLATE = get_setting('BATCH_IMPORT_EXECUTE_TEMPLATE', 'batchimport/processing.html')
BATCH_IMPORT_RESULTS_TEMPLATE = get_setting('BATCH_IMPORT_RESULTS_TEMPLATE', 'batchimport/results.html')

# Specify the list of models in your application which are importable
# in batch. If you do not provide a list, the system will use introspection 
# to get a list of ALL models in your application (via INSTALLED_APPS).
BATCH_IMPORT_IMPORTABLE_MODELS = get_setting('BATCH_IMPORT_IMPORTABLE_MODELS', [])

# Specify where the uploaded Microsoft Excel file will be saved to the
# system.
# NOTE: This must be a absolute path.
# NOTE: Django must have read/write access to this location.
BATCH_IMPORT_TEMPFILE_LOCATION = get_setting('BATCH_IMPORT_TEMPFILE_LOCATION', '/tmp/')

# By default, the system does not allow you to import data for fields 
# that are not EDITABLE (i.e. in their model field declarations, you've
# set editable=False). You can override this behavior here:
BATCH_IMPORT_UNEDITABLE_FIELDS = get_setting('BATCH_IMPORT_UNEDITABLE_FIELDS', False)

# Sometimes you will want to override the value coming in from the XLS
# file with a constant or a dynamically generated value.
# The following setting is a dictionary of values (or callables) per
# each fully specified model field.
# NOTE: You must import the item into your settings file if it is a 
# callable.
BATCH_IMPORT_VALUE_OVERRIDES = get_setting('BATCH_IMPORT_VALUE_OVERRIDES', {})


# The system can show you individual imports, updates, 
# or errors individually using the following boolean options.
# Note that True is assumed for all three if no setting is
# present.
BATCH_IMPORT_SHOW_SUCCESSFUL_IMPORTS = get_setting('BATCH_IMPORT_SHOW_SUCCESSFUL_IMPORTS', True)
BATCH_IMPORT_SHOW_SUCCESSFUL_UPDATES = get_setting('BATCH_IMPORT_SHOW_SUCCESSFUL_UPDATES', True)
BATCH_IMPORT_SHOW_ERRORS = get_setting('BATCH_IMPORT_SHOW_ERRORS', True)

# Whether the system should stop on the first error
# or process the entire uploaded spreadsheet and show
# errors afterwards.
BATCH_IMPORT_STOP_ON_FIRST_ERROR = get_setting('BATCH_IMPORT_STOP_ON_FIRST_ERROR', False)

# Whether or not to update duplicates or simply
# ignore them. Note that duplicates are determined
# based on the user's specification of model fields
# as identification fields. If these are not set, a duplicate
# must match at all column/fields.
BATCH_IMPORT_UPDATE_DUPS = get_setting('BATCH_IMPORT_UPDATE_DUPS', False)

# If no options are set for start/end row, defaults are used that
# assume (1) the spreadsheet has a header row (indicating that data
# starts on row #2 and (2) the entire spreadsheet is to be processed.
BATCH_IMPORT_START_ROW = get_setting('BATCH_IMPORT_START_ROW', 2)
BATCH_IMPORT_END_ROW = get_setting('BATCH_IMPORT_END_ROW', -1)
