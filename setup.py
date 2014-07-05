#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    :copyright: Copyright 2012 by Łukasz Mierzwa
    :contact: l.mierzwa@gmail.com
"""


from setuptools import setup


setup(
    name='django-batchimport',
    version='0.1.3-cbv',
    description='Django XLS batch processing',
    long_description="pistache's fork of Łukasz Mierzwa's project. Django template tags used to generate breadcrumbs html using twitter bootstrap css classes",
    author='Hugo Geoffroy',
    author_email='batchimport@pstch.net',
    install_requires = ['xlrd==0.9.3'],
    packages = ['batchimport'],
    package_data = {
        'batchimport': ['templates/batchimport/*.html'],
    },
    classifiers=[
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    platforms=['any'],
)
