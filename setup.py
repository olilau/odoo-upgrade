from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the relevant file
with open(path.join(here, 'DESCRIPTION.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='odoo-upgrade',
    version='1.0',
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
    ],
    keywords='odoo openerp database upgrade',
    packages=None,
    install_requires=['pycurl', 'pytz'],
    scripts = [
        'odoo-upgrade.py'
    ]
)

