#!/usr/bin/python
#-*- encoding: utf8 -*-

from fabric.api import run, env, get, put, sudo, cd, lcd, local, settings


# doc:
def all_doc():
    """clean the doc build, then build the doc, then zip the doc"""
    clean_doc()
    build_doc()
    zip_doc()

def build_doc():
    """build the documentation"""
    with lcd('doc'):
        local('make html')

def zip_doc():
    """zip the documentation for pythonhosted.org"""
    with lcd('doc/build/html'):
        local("zip -r ../../doc.zip .")

def clean_doc():
    """clean the documentation builds"""
    with lcd('doc'):
        local('make clean')
        local("rm -f doc.zip")

# egg:
def upload_egg():
    """upload the generated tar.gz file to pypi"""
    with lcd("dist"):
        local("twine2 upload *")

def build_egg():
    """lay an egg"""
    local("python setup.py sdist")

def clean_egg():
    """clean egg builds"""
    local("rm -rf odoo_upgrade.egg-info")
    local("rm -rf build")
    with lcd("dist"):
        local("rm -rf *.tar.gz")
        local("rm -rf *.egg")

def clean_all():
    """clean doc builds and egg builds"""
    clean_doc()
    clean_egg()


