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
from django.shortcuts import render_to_response

import xlrd

from batchimport.utils import ModelImportInfo
from batchimport.forms import UploadImportFileForm
from batchimport.forms import ImportOptionsForm
from batchimport.batchimport_settings import *
from batchimport.parser import _do_batch_import

def handle_uploaded_file(f,target):
    with open(target, 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)

class ImportUploadView(FormView):
    template_name = "batchimport/upload.html"
    form_class = UploadImportFileForm
    options_url = "batchimport_options"

    def form_valid(self,form):
        handle_uploaded_file(self.request.FILES['import_file'],
                             join(BATCHIMPORT_TEMPDIR,
                                  self.request.FILES['import_file'].name))
        
        self.request.session['batchimport_file_name'] = str(self.request.FILES['import_file'].name)
        self.request.session['batchimport_model'] = str(form.cleaned_data['model_for_import'])

        return HttpResponseRedirect(reverse(self.options_url))

class ImportOptionsView(FormView):
    template_name = "batchimport/options.html"
    processing_template_name = "batchimport/processing.html"
    form_class = ImportOptionsForm
    upload_url = "batchimport_upload"
    
    def dispatch(self, request, *args, **kwargs):
        try:
            self.import_file_name = request.session['batchimport_file_name']
            self.import_model = request.session['batchimport_model']
        except KeyError:
            return HttpResponseRedirect(reverse(self.upload_url))
        return super(ImportOptionsView, self).dispatch(request, *args, **kwargs)
        
    def get_context_data(self, **kwargs):
        context = super(ImportOptionsView, self).get_context_data(**kwargs)
        context['model_for_import'] = self.import_model
        return context

    def get_form(self, form_class):
        return form_class(self.import_model,
                          self.import_file_name,
                          **self.get_form_kwargs())


    def form_valid(self, form):
        self.request.session['batchimport_options'] = {}
        for option in form.get_process_options_dict().keys():
            self.request.session['batchimport_options'][option] = form.cleaned_data[option]

        model_field_value_dict = {}
        for field in form.model_field_names:
            model_field_value_dict[field] = form.cleaned_data[field]
                
        model_import_info = ModelImportInfo(self.import_model,
                                            model_field_value_dict,
                                            form.relation_info_dict)
        
        self.request.session['batchimport_info'] = model_import_info
        
        return render_to_response(self.processing_template_name)

class ImportRunView(TemplateView):
    template_name = "batchimport/run.html"
    upload_url = "batchimport_upload"

    def dispatch(self, request, *args, **kwargs):
        try:
            self.import_file_name = request.session['batchimport_file_name']
            self.import_model = request.session['batchimport_model']
            self.import_options = request.session['batchimport_options']
            self.import_info = request.session['batchimport_info']

            self.init_status_dict()
        except KeyError, e:
            return HttpResponseRedirect(reverse(self.upload_url))

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
        status_dict['processed_count'] = 0
        
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
            self.status_dict['row_count'] = sheet.nrows

            # Determine the last row of the spreadsheet to be processed.
            if self.import_options['end_row'] == -1:
                self.import_options['end_row'] = sheet.nrows
                self.status_dict['end_row'] = self.import_options['end_row']

            if self.import_info.import_mode == ModelImportInfo.OBJECT_IMPORT:
                self.status_dict = _do_batch_import(self.request,
                                                    self.import_info,
                                                    book,
                                                    sheet,
                                                    self.import_options,
                                                    self.status_dict)
            else:
                self.status_dict = _do_relation_import(self.request,
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
