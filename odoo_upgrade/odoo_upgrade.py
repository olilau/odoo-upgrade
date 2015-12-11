#!/usr/bin/env python
#-*- encoding: utf8 -*-

"""
A command line tool to upgrade your Odoo database using the Odoo Upgrade API.
Official documentation: http://pythonhosted.org/odoo-upgrade
Upgrade API documentation: https://www.odoo.com/documentation/8.0/reference/upgrade_api.html
"""

import sys
import os
import logging
import httplib
from urllib import urlencode
from io import BytesIO
import json
import functools
import datetime

import pycurl
import pytz


LOG_FMT = '%(message)s'
PROGRESS_INTERVAL = 2

ERROR_HTTP_4xx = 1
ERROR_HTTP_5xx = 2
ERROR_MISSING_ARGUMENT = 3
ERROR_FILE_NOT_FOUND = 4
ERROR_MISSING_ARGUMENT_MSG = (
    "Argument '{}' is mandatory for '{}' action. Aborting")

CURLINFO = """EFFECTIVE_URL RESPONSE_CODE HTTP_CONNECTCODE TOTAL_TIME
NAMELOOKUP_TIME CONNECT_TIME APPCONNECT_TIME PRETRANSFER_TIME
STARTTRANSFER_TIME REDIRECT_TIME REDIRECT_COUNT REDIRECT_URL SIZE_UPLOAD
SIZE_DOWNLOAD SPEED_DOWNLOAD SPEED_UPLOAD HEADER_SIZE REQUEST_SIZE
SSL_VERIFYRESULT SSL_ENGINES CONTENT_LENGTH_DOWNLOAD CONTENT_LENGTH_UPLOAD
CONTENT_TYPE""".split()

TZ_GET = [
    tz for tz
    in sorted(pytz.all_timezones, key=lambda tz: tz
    if not tz.startswith('Etc/') else '_')]


def require(*requires):
    def decorator(method):
        @functools.wraps(method)
        def f(self, *args, **kwargs):
            for arg in requires:
                if not getattr(self.args, arg):
                    logging.error(ERROR_MISSING_ARGUMENT_MSG.format(arg, self.args.action))
                    sys.exit(ERROR_MISSING_ARGUMENT)
            return method(self, *args, **kwargs)
        return f
    return decorator


class CurlConnector(object):
    def __init__(self, insecure=False, debug=False):
        self.insecure = insecure
        self.debug = debug
        self.curl = None

    def __enter__(self):
        self.curl = pycurl.Curl()
        if self.insecure:
            self.curl.setopt(pycurl.SSL_VERIFYPEER, False)
            self.curl.setopt(pycurl.SSL_VERIFYHOST, False)

        if self.debug:
            self.curl.setopt(pycurl.VERBOSE, 1)

        return self.curl

    def __exit__(self, type, value, tb):
        self.curl.close()


class UpgradeManager(object):
    def __init__(self, args):
        self.args = args
        self.verbose = len(self.args.verbose)
        self._set_logging()
        self.output = self.init_output()

        # check timezone:
        self._check_tz()

    def _check_tz(self):
        tz = self.args.timezone
        if tz and tz not in TZ_GET:
            msg = "Timezone '{}' is not a valid value.".format(tz)
            matches = ', '.join(["'{}'".format(
                name) for name in TZ_GET if name.lower().find(tz) > -1])
            if matches:
                msg += " Here is a list of closest matches:\n{}".format(
                    matches)
            logging.error(msg)
            sys.exit(3)

    def run(self):
        status = None
        if self.args.action == 'create':
            status = self.create()
        elif self.args.action == 'upload':
            status = self.upload()
        elif self.args.action == 'process':
            status = self.process()
        elif self.args.action == 'all':
            status = self.do_all()
        elif self.args.action == 'status':
            status = self.status()

        sys.exit(status if status else 0)

    @require('contract', 'email', 'target', 'aim', 'filename')
    def create(self):
        API_PATH = "/database/v1/create"
        self.output['operation'] = 'create'
        fields = dict(filter(None, [
            ('contract', self.args.contract),
            ('email', self.args.email),
            ('target', self.args.target),
            ('aim', self.args.aim),
            ('filename', self.args.filename),
            ('timezone', self.args.timezone) if self.args.timezone else None,
        ]))
        postfields = urlencode(fields)

        with CurlConnector(self.args.insecure, self.args.debug) as curl:
            headers = {}
            curl.setopt(
                pycurl.HTTPHEADER,
                ['%s: %s' % (k, headers[k]) for k in headers])
            curl.setopt(pycurl.URL, self.args.url+API_PATH)
            curl.setopt(curl.POSTFIELDS, postfields)
            data = BytesIO()
            curl.setopt(curl.WRITEFUNCTION, data.write)
            curl.perform()
            http_status = curl.getinfo(pycurl.HTTP_CODE)
            self.output['http_status'] = dict(
                code=http_status,
                reason=httplib.responses[http_status])

            if self.verbose > 1:
                self.output['curl_info'].update({
                    info: curl.getinfo(getattr(pycurl, info))
                    for info
                    in CURLINFO})

            self.upgrade_response = json.loads(data.getvalue())
            self.output['upgrade_response'] = self.upgrade_response

            # output display:
            logging.info(self.format_json(self.output))

            if http_status >= 400:
                return ERROR_HTTP_4xx if http_status < 500 else ERROR_HTTP_5xx

    @require('key', 'request', 'dbdump')
    def upload(self):
        API_PATH = "/database/v1/upload"
        self.output['operation'] = 'upload'
        fields = dict([
            ('key', self.args.key),
            ('request', self.args.request),
        ])
        postfields = urlencode(fields)

        # check the exitence of the dump file:
        dbdump = os.path.expandvars(os.path.expanduser(self.args.dbdump))

        if not os.path.isfile(dbdump):
            sys.stderr.write("Dump file '{}' not found\n".format(dbdump))
            return ERROR_FILE_NOT_FOUND

        with CurlConnector(self.args.insecure, self.args.debug) as curl:
            curl.setopt(pycurl.URL, self.args.url+API_PATH+'?'+postfields)
            curl.setopt(pycurl.POST, 1)
            data = BytesIO()
            curl.setopt(curl.WRITEFUNCTION, data.write)

            filesize = os.path.getsize(self.args.dbdump)
            curl.setopt(pycurl.POSTFIELDSIZE, filesize)
            fp = open(self.args.dbdump, 'rb')
            curl.setopt(pycurl.READFUNCTION, fp.read)
            headers = {"Content-Type": "application/octet-stream"}
            curl.setopt(
                pycurl.HTTPHEADER,
                ['%s: %s' % (k, headers[k]) for k in headers])

            self.t1 = datetime.datetime.now()
            self.t0 = self.t1

            if self.verbose > 0:
                def progress(to_download, downloaded, to_upload, uploaded):
                    def display_delta(delta):
                        hours, remainder = divmod(delta.total_seconds(), 3600)
                        minutes, seconds = divmod(remainder, 60)
                        return '{:0>2}:{:0>2}:{:0>2}'.format(
                            int(hours), int(minutes), int(seconds))

                    self.t2 = datetime.datetime.now()
                    if uploaded and (self.t2 - self.t1).total_seconds() > PROGRESS_INTERVAL:
                        eta = datetime.timedelta(
                            seconds=((self.t2 - self.t0).total_seconds()
                                * to_upload / uploaded))
                        s = ("{}/{} bytes uploaded ({:.2%}) in {} "
                             "(TOTAL estimated time: {})").format(
                                int(uploaded), int(to_upload),
                                (uploaded / to_upload),
                                display_delta(self.t2 - self.t0),
                                display_delta(eta))
                        sys.stderr.write(s+'\r')
                        sys.stderr.flush()
                        self.t1 = datetime.datetime.now()

                curl.setopt(curl.NOPROGRESS, 0)
                curl.setopt(curl.PROGRESSFUNCTION, progress)

            curl.perform()
            http_status = curl.getinfo(pycurl.HTTP_CODE)

            self.output['http_status'] = dict(
                code=http_status,
                reason=httplib.responses[http_status])

            if self.verbose > 1:
                self.output['curl_info'].update({
                    info: curl.getinfo(getattr(pycurl, info))
                    for info
                    in CURLINFO})

            upgrade_response = json.loads(data.getvalue())
            self.output['upgrade_response'] = upgrade_response

            # output display:
            logging.info(self.format_json(self.output))

            if http_status >= 400:
                return ERROR_HTTP_4xx if http_status < 500 else ERROR_HTTP_5xx

    @require('key', 'request')
    def process(self):
        API_PATH = "/database/v1/process"
        self.output['operation'] = 'process'
        fields = dict([
            ('key', self.args.key),
            ('request', self.args.request),
        ])
        postfields = urlencode(fields)

        with CurlConnector(self.args.insecure, self.args.debug) as curl:
            headers = {}
            curl.setopt(
                pycurl.HTTPHEADER,
                ['%s: %s' % (k, headers[k]) for k in headers])
            curl.setopt(pycurl.URL, self.args.url+API_PATH)
            curl.setopt(curl.POSTFIELDS, postfields)
            data = BytesIO()
            curl.setopt(curl.WRITEFUNCTION, data.write)
            curl.perform()
            http_status = curl.getinfo(pycurl.HTTP_CODE)
            self.output['http_status'] = dict(
                code=http_status,
                reason=httplib.responses[http_status])

            if self.verbose > 1:
                self.output['curl_info'].update({
                    info: curl.getinfo(getattr(pycurl, info))
                    for info
                    in CURLINFO})

            upgrade_response = json.loads(data.getvalue())
            self.output['upgrade_response'] = upgrade_response

            # output display:
            logging.info(self.format_json(self.output))

            if http_status >= 400:
                return ERROR_HTTP_4xx if http_status < 500 else ERROR_HTTP_5xx

    @require('key', 'request')
    def status(self):
        API_PATH = "/database/v1/status"
        self.output['operation'] = 'status'
        fields = dict([
            ('key', self.args.key),
            ('request', self.args.request),
        ])
        postfields = urlencode(fields)

        with CurlConnector(self.args.insecure, self.args.debug) as curl:
            headers = {}
            curl.setopt(
                pycurl.HTTPHEADER,
                ['%s: %s' % (k, headers[k]) for k in headers])
            curl.setopt(pycurl.URL, self.args.url+API_PATH)
            curl.setopt(curl.POSTFIELDS, postfields)
            data = BytesIO()
            curl.setopt(curl.WRITEFUNCTION, data.write)
            curl.perform()
            http_status = curl.getinfo(pycurl.HTTP_CODE)
            self.output['http_status'] = dict(
                code=http_status,
                reason=httplib.responses[http_status])
            if self.verbose > 1:
                self.output['curl_info'].update({
                    info: curl.getinfo(getattr(pycurl, info))
                    for info
                    in CURLINFO})

            upgrade_response = json.loads(data.getvalue())
            self.output['upgrade_response'] = upgrade_response

            # output display:
            logging.info(self.format_json(self.output))

            if http_status >= 400:
                return ERROR_HTTP_4xx if http_status < 500 else ERROR_HTTP_5xx

    @require('contract', 'email', 'target', 'aim', 'filename', 'dbdump')
    def do_all(self):
        self.create()
        if self.output['upgrade_response']:
            self.args.key = self.output['upgrade_response']['request']['key']
            self.args.request = self.output['upgrade_response']['request']['id']

        self.upload()
        self.process()
        self.status()

    def init_output(self):
        return {
            'operation': '',
            'curl_info': {},
            'http_status': {
            },
            'upgrade_response': [],
        }

    def format_json(self, obj, indent=2, sort_keys=True):
        return json.dumps(obj, indent=indent, sort_keys=sort_keys)

    def _set_logging(self):
        if not self.args.verbose:
            loglevel = logging.ERROR
        elif len(self.args.verbose) == 1:
            loglevel = logging.INFO
        else:
            loglevel = logging.DEBUG
        logging.basicConfig(level=loglevel, format=LOG_FMT)

