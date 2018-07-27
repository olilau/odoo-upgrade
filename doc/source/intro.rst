
Introduction
------------

A command line tool to upgrade your `Odoo <https://www.odoo.com>`_ database
using the `Upgrade API <https://www.odoo.com/documentation/11.0/webservices/upgrade.html>`_
documented on the `official Odoo documentation <https://www.odoo.com/documentation>`_ (`v11.0 page
<https://www.odoo.com/documentation/11.0/webservices/upgrade.html>`_)

.. note:: You'll need an Odoo Enterprise Subscription.

It's the equivalent of filling the form on the `Upgrade platform <https://upgrade.odoo.com>`_ page.

It allows to:

* create a database upgrade request
* upload a database dump
* ask to process it
* obtain the current status of your request

Documentation
-------------

https://odoo-upgrade.readthedocs.io

Requires
--------

* python with:

  - pycurl
  - pytz

