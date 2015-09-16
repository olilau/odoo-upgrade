from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

long_description="""\
A command line tool to upgrade your `Odoo <https://www.odoo.com>`_ database
using the `Upgrade API <https://www.odoo.com/documentation/8.0/reference/upgrade_api.html>`_
documented on the `official Odoo documentation <https://www.odoo.com/documentation>`_ (`v8.0 page
<https://www.odoo.com/documentation/8.0/reference/upgrade_api.html>`_)

.. note:: You'll need an Odoo Enterprise Contract.

It's the equivalent of filling the form on the `Upgrade platform <https://upgrade.odoo.com>`_ page.

It allows to:

* create a database upgrade request
* upload a database dump
* ask to process it
* obtain the current status of your request
"""

setup(
    name='odoo-upgrade',
    version='1.0.3',
    description='Command line tool to upgrade your Odoo database',
    long_description=long_description,
    url='https://github.com/olilau/odoo-upgrade',
    author='olivier Laurent',
    author_email='olilau@gmail.com',
    license='GPLv2',
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Information Technology',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Environment :: Console',
        'Topic :: Database',
        'Programming Language :: Python :: 2.7',
        'Operating System :: POSIX',
    ],
    keywords='odoo openerp database upgrade',
    packages=None,
    install_requires=['pycurl', 'pytz'],
    scripts = [
        'odoo-upgrade.py'
    ],
    package_data = {
        '': ['*.rst'],
    },
)

