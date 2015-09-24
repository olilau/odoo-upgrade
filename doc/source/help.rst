
Help
----

The first thing you'll want to do is obtaining help:

::

  odoo-upgrade --help


Result
------

The 4 actions (create, upload, process, status) return a JSON dictionary with 3 keys:

* ``curl_info``: curl debug info (only filled if `--verbose` is used)
* ``http_status``: the http code result
* ``upgrade_response``: the JSON dictionary described on the `Upgrade API
  <https://www.odoo.com/documentation/8.0/reference/upgrade_api.html>`_ page, in the
  `Sample output` section

Example
+++++++

::

    {
      "curl_info": {},
      "http_status": {
        "code": 200,
        "reason": "OK"
      },
      "upgrade_response": {
        "failures": []
      }
    }

.. _creating-a-request:

Creating a request
------------------

You'll need to create a request before doing anything else.
The purpose is to supply all the required information:

* ``contract``: your contract reference
* ``email``: your email address
* ``target``: the target version of your Odoo database
* ``aim``: the purpose of your request (test or production)
* ``filename``: a name for your dump file

This is the minimum list of required optin for creating a request.

.. _important-keys:

If the action is successful, you'll get back a JSON object.
The most important keys are:

* ``request``: your request id
* ``key``: a private key

You'll need these 2 keys for all the other actions (upload, process, status)

Example:
++++++++

Here is an example of how to create a request:

::

  odoo_upgrade create --contract=M123-abc \
    --email john.doe@example.com --target 8.0 \
    --aim test --filename db.dump

Supplying the timezone
++++++++++++++++++++++

If you current Odoo database is 5.0 or 6.0, you can also supply the
``timezone`` of your server:

.. note::

  In previous versions (prior to 6.1), the odoo server was not using any
  timezone information when storing timestamp values. In version 6.1, the
  odoo server stores all timestamp values in UTC (Coordinated Universal Time)

The ``timezone`` option needs an exact match on an existing timezone. You can
get the list of valid timezones in the `timezones.txt` file.

The `odoo_upgrade` script will also try to display a list of the closest
matching timezones:

::

  odoo_upgrade create --contract=M123-abc \
    --email john.doe@example.com --target 8.0 \
    --aim test --filename db.dump --timezone brus

  Timezone 'brus' is not a valid value. Here is a list of closest
  matches:
  'Europe/Brussels

  odoo_upgrade create --contract=M123-abc \
    --email john.doe@example.com --target 8.0 \
    --aim test --filename db.dump --timezone 'Europe/Brussels'

Uploading a database dump
-------------------------

.. note::

    `As stated earlier <#important-keys>`_, you'll need the request id and the private key to upload your database.
    You'll find them in the JSON object you receive when creating a request (``request`` and ``id`` keys).

Here is an example of how to upload your database dump:

::

    # dump your db:
    pg_dump db_name | gzip > db_name.sql.gz
    # upload the dump file:
    odoo_upgrade upload --key 'aeDp9UThC7A6fwk0dJRszA==' \
      --request 10042 --dbdump db_name.sql.gz

Asking to process your request
------------------------------

.. note::

    `As stated earlier <#important-keys>`_, you'll need the request id and the private key to process your database.
    You'll find them in the JSON object you receive when creating a request (``request`` and ``id`` keys).

Example:

::

    odoo_upgrade process --key 'aeDp9UThC7A6fwk0dJRszA==' \
      --request 10042

Obtaining the status of your request
------------------------------------

.. note::

    `As stated earlier <#important-keys>`_, you'll need the request id and the private key to ask the status of your database.
    You'll find them in the JSON object you receive when creating a request (``request`` and ``id`` keys).

Example:

::

    odoo_upgrade status --key 'aeDp9UThC7A6fwk0dJRszA==' \
      --request 10042

The JSON dictionary you receive is described on the `Upgrade API
<https://www.odoo.com/documentation/8.0/reference/upgrade_api.html>`_ page, in the
`Sample output` section

