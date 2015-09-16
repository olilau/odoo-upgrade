#!/usr/bin/env python
# -*- encoding: utf8 -*-

import sys
import os
import argparse
import logging
import pycurl
import httplib
from urllib import urlencode
from io import BytesIO
import json
import functools
import pytz


LOG_FMT = '%(message)s'
DEFAULT_URL = "https://upgrade.odoo.com"
TARGETS = "6.0 6.1 7.0 8.0".split()

ERROR_HTTP_4xx = 1
ERROR_HTTP_5xx = 2
ERROR_MISSING_ARGUMENT = 3
ERROR_FILE_NOT_FOUND = 4
ERROR_MISSING_ARGUMENT_MSG = (
    "Argument '{}' is mandatory for 'create' action. Aborting")

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


parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument(
    'action', choices=['create', 'upload', 'process', 'status'],
    help="Action to perform. Choices: %(choices)s", action='store',
    metavar='ACTION')
verb = parser.add_mutually_exclusive_group()
verb.add_argument(
    '-q', '--quiet', help="Quiet output", dest="verbose", default=[1],
    action='store_const', const=[])
verb.add_argument(
    '-v', '--verbose', dest="verbose", default=[],
    action='append_const', const=1,
    help=("Verbose output.\n"
          "Use -q, --quiet to make it quiet"))

request_group = parser.add_argument_group("Request arguments")
request_group.add_argument(
    '--contract', action='store', metavar='CONTRACT',
    help="Your Enterprise contarct reference")
request_group.add_argument(
    '--email', action='store', metavar='ADDRESS',
    help="Your email address")
request_group.add_argument(
    '--target', choices=TARGETS, action='store',
    metavar='VERSION',
    help="Odoo target version\nChoices: %(choices)s")
request_group.add_argument(
    '--filename', action='store',
    help="Name of your dump file. Purely informative")
request_group.add_argument(
    '--aim', choices=['test', 'production'],
    action='store', metavar='AIM',
    help=("Purpose of your request. Upgrade for test or\n"
          "upgrade for production use.\nChoices: %(choices)s"))
request_group.add_argument(
    '--timezone', default=False,
    action='store', metavar='TZ',
    help="Server timezone (for Odoo <6.1)")
request_group.add_argument(
    '--key', action='store', metavar='PRIVATE_KEY',
    help=("Your request private key.\n"
          "Use the 'status' action if you want to retrieve this information.\n"
          "Query the 'key' parameter"))
request_group.add_argument(
    '--request', action='store', metavar='ID',
    help=("Your request id.\n"
          "Use the 'status' action if you want to retrieve this information.\n"
          "Query the 'id' parameter"))
request_group.add_argument(
    '--dbdump', action='store', metavar='PATH',
    help=("The path to your database dump file"))

obscure_group = parser.add_argument_group(
    "Obscure arguments that you should not use")
obscure_group.add_argument(
    '--insecure', default=False,
    action='store_true',
    help=("This option explicitly allows performing \"insecure\" SSL\n"
          "connections and transfers. By default, all SSL connections\n"
          "are attempted to be made secure by using the CA certificate\n"
          "bundle installed"))
obscure_group.add_argument(
    '--url', default=DEFAULT_URL,
    help="Upgrade platform URL (default: %(default)s)", action='store',
    metavar='URL')
obscure_group.add_argument(
    '--debug', default=False,
    help="Debug", action='store_true',)


def require(*requires):
    def decorator(method):
        @functools.wraps(method)
        def f(self, *args, **kwargs):
            for arg in requires:
                if not getattr(self.args, arg):
                    logging.error(ERROR_MISSING_ARGUMENT_MSG.format(arg))
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
        elif self.args.action == 'status':
            status = self.status()

        sys.exit(status if status else 0)

    @require('contract', 'email', 'target', 'aim', 'filename')
    def create(self):
        API_PATH = "/database/v1/create"
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

            upgrade_response = json.loads(data.getvalue())
            self.output['upgrade_response'] = upgrade_response

            # output display:
            logging.info(self.format_json(self.output))

            if http_status >= 400:
                return ERROR_HTTP_4xx if http_status < 500 else ERROR_HTTP_5xx

    @require('key', 'request', 'dbdump')
    def upload(self):
        API_PATH = "/database/v1/upload"
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

    def init_output(self):
        return {
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


def _main():
    args = parser.parse_args()
    app = UpgradeManager(args)
    app.run()

if __name__ == '__main__':
    _main()

