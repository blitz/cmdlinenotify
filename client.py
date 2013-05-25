#!/usr/bin/env python2

import webbrowser
import urllib
import os
import sys
import ConfigParser
import oauth2 as oauth
import urlparse
import subprocess

app_id = 'cmdlinenotify'
url    = 'http://%s.appspot.com' % app_id

consumer_key    = '%s.appspot.com' % app_id
consumer_secret = 'O9gnGgaiIW3LXov9veAHAKFf'

request_token_url   = "https://%s.appspot.com/_ah/OAuthGetRequestToken" % app_id
authorize_url       = "https://%s.appspot.com/_ah/OAuthAuthorizeToken" % app_id
access_token_url    = "https://%s.appspot.com/_ah/OAuthGetAccessToken" % app_id
 
consumer = oauth.Consumer(consumer_key, consumer_secret)

config = ConfigParser.RawConfigParser()
user_config_file_name = os.path.expanduser('~/.cmdlinenotify')

def write_config():
    config.write(open(user_config_file_name, "w+"))


config.read([user_config_file_name, '/usr/local/etc/cmdlinenotify.rc',
             '/etc/cmdlinenotify.rc'])

need_oauth = not config.has_section("oauth") or not config.has_option("oauth", "token")

if need_oauth:
    print "You need to give me access to the cloud. Stand by..."

    client = oauth.Client(consumer)
 
    # Step 1: Get a request token. This is a temporary token that is used for 
    # having the user authorize an access token and to sign the request to obtain 
    # said access token.
 
    resp, content = client.request(request_token_url, "GET")
    if resp['status'] != '200':
        raise Exception("Invalid response %s." % resp['status'])
 
    request_token = dict(urlparse.parse_qsl(content))
 
    print "Go to the following link in your browser:"
    print "%s?oauth_token=%s" % (authorize_url, request_token['oauth_token'])
    print

    # After the user has granted access to you, the consumer, the provider will
    # redirect you to whatever URL you have told them to redirect to. You can 
    # usually define this in the oauth_callback argument as well.
    accepted = 'n'
    while accepted.lower() == 'n':
            accepted = raw_input('Have you authorized me? (y/n) ')
 
 
    # Step 3: Once the consumer has redirected the user back to the oauth_callback
    # URL you can request the access token the user has approved. You use the 
    # request token to sign this request. After this is done you throw away the
    # request token and use the access token returned. You should store this 
    # access token somewhere safe, like a database, for future use.
    token = oauth.Token(request_token['oauth_token'],
                request_token['oauth_token_secret'])
    client = oauth.Client(consumer, token)
 
    resp, content = client.request(access_token_url, "POST")
    access_token = dict(urlparse.parse_qsl(content))
 
    token = oauth.Token(access_token['oauth_token'],
                        access_token['oauth_token_secret'])

    if not config.has_section("oauth"):
        config.add_section("oauth")
    config.set("oauth", "token", token.to_string())
    write_config()    


access_token = oauth.Token.from_string(config.get("oauth", "token"))

# Create new job

command = " ".join(sys.argv[1:])
client = oauth.Client(consumer, access_token)

#import httplib2
#httplib2.debuglevel = 10

resp, content = client.request(url + "/new-job", "POST",
                               body = urllib.urlencode({"command" : command}))

if resp['status'] != "200":
    print "Creating job failed. Bye."

jobid = content

proc = subprocess.Popen('"' + '" "'.join(sys.argv[1:]) + '"', shell=True, bufsize = -1,
                        stdout = subprocess.PIPE,
                        stderr = subprocess.STDOUT)


# XXX Read line by line and update when too much data accumulated or
# too much time passed
while True:
    data = proc.stdout.read(1 << 16)
    sys.stdout.write(data)
    client.request('%s/job/%s' % (url, jobid), "POST",
                   body = urllib.urlencode({"action" : "update",
                                            "output" : data}))
    if proc.poll() is not None and len(data) == 0:
        break

client.request('%s/job/%s' % (url, jobid), "POST",
               body = urllib.urlencode({"action" : "update",
                                        "finished" : 1,
                                        "exit_code" : proc.returncode}))

#print config.get("oauth", "accesstoken")


