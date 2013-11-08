# django-batchimport

Allows for batch import of django model data via uploaded Microsoft Excel files, saved as XLS files (Excel Binary file format). 
Of course, you can also use OpenOffice or CSV files, but you will have to convert them to the XLS format beforehand.

**This experimental forks uses "class-based views" to provide more flexibility**

# Settings

 - `BATCHIMPORT_TEMPDIR` : Directory when temporary XLS data will be stored (default: `/tmp/`)

# Views

 - `ImportUploadView` : FormView with fields `model_to_import` and `import_file`
   - Options :
     - `template_name` : template used to render the view (default: `batchimport/upload.html`)
	 - `options_url` : name of the URL pattern pointing to the ImportOptionsView (default: `batchimport_options`)

 - `ImportOptionsView` : FormView that asks the user information about the data processing.
   - Options :
     - `template_name` : template used to render the view (default: `batchimport/options.html`)
	 - `processing_template_name` : template displayed while batchimport is processing the data (default: `batchimport/processing.html`)
	 - `upload_url` : name of the URL pattern pointing to the ImportUploadFile, in case we need to go back (default: `batchimport_upload`)

 - `ImportRunView` : TemplateView that runs the import and displays the rsults
   - Options :
     - `template_name` : template used to render the view (default: `batchimport/options.html`)
	 - `upload_url` : name of the URL pattern pointing to the ImportUploadFile, in case we need to go back (default: `batchimport_upload`)
   - Context :
     - `start_row` : first row to be imported
	 - `end_row` : last row to be imported
	 - `row_count` : row count
	 - `processed_count` : processed rows count
	 - `imported_count` : imported (created in database) objects count
	 - `updated_count` : updated objects count
	 - `combined_messages` : combined import and update results
	 - `import_messages` : imports results
	 - `update_messages` : updates results
	 - `error_messages` : errors

# Session data


django-batchimport uses the following session variables to store data between its views n:
 - `batchimport_file_name` (set by `ImportUploadView`)
 - `batchimport_model` (set by `ImportUploadView`)
 - `batchimport_options` (set by `ImportOptionsView`)
 - `batchimport_info` (set by `ImportOptionsView`)

These variables are erased at the end of the import operation (in `ImportRunView.run_import()`)

**WARNING:** Because the `batchimport_info` is a `ModelImportInfo` object (django-batchimport specific class), and `ModelImportInfo` is not JSON-serializable, it is not possible to use JSON serialization to store your session data.

# Installation

`pip install git+git://github.com/pstch/django-batchimport.git`

Or clone `http://github.com/pstch/django-batchimport.git` and install package yourself using `setup.py`.

# Configuration

Add `batchimport` to `INSTALLED_APPS` in `settings.py`

## Generic URL config

If you want to use django-batchimport's own URL config :

Add the following URL pattern in `urls.py` :
`(r'^batchimport/', include('batchimport.urls')),`

## Subclassing django-batchimport views

But you can also subclass the three views `ImportUploadView`, `ImportOptionsView` and `ImportRunView` in order to set your own settings and also your own URL patterns.

Just remember that whenever you change a URL pattern's name, you have to change it accordingly in the `upload_url` and `options_url` view attributes, and in the templates.
