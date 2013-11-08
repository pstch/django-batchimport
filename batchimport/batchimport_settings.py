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
	try:
		setting=getattr(settings, setting_name)
	except (AttributeError, NameError):
		pass
	return setting
	
# INITIALIZE BATCHIMPORT SETTINGS...

BATCHIMPORT_TEMPDIR = get_setting('BATCHIMPORT_TEMPDIR', '/tmp/')

# By default, the system does not allow you to import data for fields 
# that are not EDITABLE (i.e. in their model field declarations, you've
# set editable=False). You can override this behavior here:
BATCHIMPORT_UNEDITABLE_FIELDS = get_setting('BATCHIMPORT_UNEDITABLE_FIELDS', False)

# Sometimes you will want to override the value coming in from the XLS
# file with a constant or a dynamically generated value.
# The following setting is a dictionary of values (or callables) per
# each fully specified model field.
# NOTE: You must import the item into your settings file if it is a 
# callable.
BATCHIMPORT_VALUE_OVERRIDES = get_setting('BATCHIMPORT_VALUE_OVERRIDES', {})

BATCHIMPORT_IMPORTABLE_MODELS = get_setting('BATCHIMPORT_IMPORTABLE_MODELS', {})

# The system can show you individual imports, updates individually 
# using the following boolean options.
# Note that True is assumed for all three if no setting is
# present.
BATCHIMPORT_SHOW_SUCCESSFUL_IMPORTS = get_setting('BATCHIMPORT_SHOW_SUCCESSFUL_IMPORTS', True)
BATCHIMPORT_SHOW_SUCCESSFUL_UPDATES = get_setting('BATCHIMPORT_SHOW_SUCCESSFUL_UPDATES', True)


# Whether the system should stop on the first error
# or process the entire uploaded spreadsheet and show
# errors afterwards.
BATCHIMPORT_STOP_ON_FIRST_ERROR = get_setting('BATCHIMPORT_STOP_ON_FIRST_ERROR', False)

# Whether or not to update duplicates or simply
# ignore them. Note that duplicates are determined
# based on the user's specification of model fields
# as identification fields. If these are not set, a duplicate
# must match at all column/fields.
BATCHIMPORT_UPDATE_DUPS = get_setting('BATCHIMPORT_UPDATE_DUPS', False)

# If no options are set for start/end row, defaults are used that
# assume (1) the spreadsheet has a header row (indicating that data
# starts on row #2 and (2) the entire spreadsheet is to be processed.
BATCHIMPORT_START_ROW = get_setting('BATCHIMPORT_START_ROW', 2)
BATCHIMPORT_END_ROW = get_setting('BATCHIMPORT_END_ROW', -1)
