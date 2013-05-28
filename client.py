#!/usr/bin/env python2

from __future__ import print_function

import sys
import os
import platform
import httplib2
import subprocess
import multiprocessing

from apiclient.discovery import build
from oauth2client.file   import Storage
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.tools  import run

# Config

# We get the discovery document from this URL. The apiclient.discovery
# module will do the magic of generating a client backend for us.
service_discovery_url = "https://cmdlinenotify.appspot.com/_ah/api/discovery/v1/apis/jobapi/v1/rest"

# From the API console.
client_id     = '225448041722.apps.googleusercontent.com'
client_secret = '7BnZ33Ilov5KaX6r_L2DYVFS'

# The rights we request when we try to obtain a token.
#scope         = 'openid email'
scope         =  "https://www.googleapis.com/auth/userinfo.email"

# We store the acquired token in this file.
user_credentials_file_name = os.path.expanduser('~/.cmdlinenotify.token')


def log(msg):
    print(';;; %s' % msg, file=sys.stderr)

def get_authenticated_service():
    log('Asking the cloud for guidance.')

    storage = Storage(user_credentials_file_name)
    credentials = storage.get()

    if credentials is None or credentials.invalid:
        flow = OAuth2WebServerFlow(client_id, client_secret, scope)
        credentials = run(flow, storage)

    http = httplib2.Http()
    http = credentials.authorize(http)
    service = build("JobApi", "v1", http=http,
                    discoveryServiceUrl=(service_discovery_url))
    return service

def main():
    # Do the oauth dance.
    service = get_authenticated_service()

    try:

        cmdline = ' '.join(sys.argv[1:])

        # Create job on server
        response = service.create(body = { 'command' : cmdline,
                                           'host'    : platform.node()}).execute()
        job_id = response['job_id']

        # Use multiprocessing magic to fork our command in another
        # process. Communicate events via a queue back to our main
        # process.

        def queue_worker(queue, cmdline):
            log('Starting your command.')
            proc = subprocess.Popen(cmdline, shell=True, bufsize = 1,
                                    stdout = subprocess.PIPE,
                                    stderr = subprocess.STDOUT)

            while True:
                line = proc.stdout.readline()
                sys.stdout.write(line)
                sys.stdout.flush()
                queue.put(line)
                if proc.poll() is not None and len(line) == 0:
                    break
            qsize = queue.qsize()
            log('Flushing output to the cloud. %s line%s have accumulated.' % (qsize, "" if qsize == 1 else "s"))
            queue.put(proc.returncode)
            queue.close()


        q = multiprocessing.Queue()
        p = multiprocessing.Process(target=queue_worker, args=(q, cmdline))
        p.start()

        buffer = ''
        while True:
            needs_push = False
            try:
                event = q.get(timeout = 5)
                if isinstance(event, (int, long)):
                    service.update(body = { 'job_id' : job_id,
                                            'exit_code': event,
                                            'output' : buffer}).execute()
                    break
                else:
                    buffer += event
            except multiprocessing.Queue.Empty:
                needs_push = True


            if (needs_push or len(buffer) > (1 << 16)):
                service.update(body = { 'job_id' : job_id,
                                        'output' : buffer}).execute()
                buffer = ''

        q.close()
        q.join_thread()

    except AccessTokenRefreshError:
        # The AccessTokenRefreshError exception is raised if the credentials
        # have been revoked by the user or they have expired.
        print ('The credentials have been revoked or expired, please re-run'
               'the application to re-authorize')

if __name__ == '__main__':
  main()
