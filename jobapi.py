# -*- Mode: Python -*-

from google.appengine.ext import endpoints
from google.appengine.ext import ndb
from protorpc import remote
from protorpc import messages

import logging
import datetime

# Data model

class UserPrefs(ndb.Model):
    user_id = ndb.StringProperty(required = True)

class Job(ndb.Model):
    user_id = ndb.StringProperty(required = True)
    command = ndb.TextProperty(required = True)
    host    = ndb.TextProperty(required = True)
    created_date     = ndb.DateTimeProperty(auto_now_add = True)
    last_update_date = ndb.DateTimeProperty(auto_now = True)
    finished_date    = ndb.DateTimeProperty()
    exit_code        = ndb.IntegerProperty()
    output           = ndb.TextProperty(default = "")


# Helper

def get_current_user():
    current_user = endpoints.get_current_user()
    if current_user is None:
        raise endpoints.UnauthorizedException('Invalid token.')
    return current_user

def get_job_by_id(request, job_id):
    job = Job.get_by_id(job_id)
    if job is None:
        raise endpoints.NotFoundException(request)
    return job

# Message and response types

class CreateReqMessage(messages.Message):
    command = messages.StringField(1, required=True)
    host    = messages.StringField(2, required=True)

class CreateRespMessage(messages.Message):
    job_id = messages.IntegerField(1)


class GetReqMessage(messages.Message):
    job_id = messages.IntegerField(1, required=True)

class GetRespMessage(messages.Message):
    command     = messages.StringField(1, required=True)
    last_output = messages.StringField(2, required=True)

class UpdateReqMessage(messages.Message):
    job_id    = messages.IntegerField(1, required=True)
    output    = messages.StringField(2)
    exit_code = messages.IntegerField(3)

class DeleteReqMessage(messages.Message):
    job_id = messages.IntegerField(1, required=True)

class ListReqMessage(messages.Message):
    count = messages.IntegerField(1)

class ListRespMessage(messages.Message):
    job_id = messages.IntegerField(1, repeated=True)

class EmptyRespMessage(messages.Message):
    pass

# The API

PYTHON_CLIENT = '225448041722.apps.googleusercontent.com'

@endpoints.api(name='jobapi', version='v1',
               description='Job API',
               allowed_client_ids=[PYTHON_CLIENT, endpoints.API_EXPLORER_CLIENT_ID])
class JobApi(remote.Service):

    @endpoints.method(CreateReqMessage,
                      CreateRespMessage,
                      path='jobapi/create',
                      http_method='POST')
    def create(self, request):
        user = get_current_user()
        # Happens for users without Google Account
        assert user.user_id() is not None
        job = Job(user_id = user.user_id(),
                  command = request.command,
                  host    = request.host)
        job.put()
        return CreateRespMessage(job_id = job.key.integer_id())

    @endpoints.method(GetReqMessage,
                      GetRespMessage,
                      path='jobapi/get',
                      http_method='GET')
    def get(self, request):
        user = get_current_user()
        job  = get_job_by_id(request, request.job_id)
        return GetRespMessage(command = job.command,
                              last_output = job.output)

    @endpoints.method(UpdateReqMessage,
                      EmptyRespMessage,
                      path='jobapi/update',
                      http_method='POST')
    def update(self, request):
        user = get_current_user()
        job  = get_job_by_id(request, request.job_id)
        if request.output is not None:
            job.output += request.output
            if len(job.output) > (1 << 16):
                job.output = job.output[-(1 << 16):]
        if request.exit_code is not None:
            job.exit_code     = request.exit_code
            job.finished_date = datetime.datetime.now()
        job.put()
        return EmptyRespMessage()

    @endpoints.method(DeleteReqMessage,
                      EmptyRespMessage,
                      path='jobapi/delete',
                      http_method='POST')
    def delete(self, request):
        user = get_current_user()
        job  = get_job_by_id(request, request.job_id)
        job.key.delete()
        return EmptyRespMessage()

    @endpoints.method(ListReqMessage,
                      ListRespMessage,
                      path='jobapi/list',
                      http_method='GET')
    def list(self, request):
        """Returns the `count' newest jobs."""
        user = get_current_user()
        q = Job.query(Job.user_id == user.user_id());
        jobs_keys = q.order(-Job.created_date).fetch(limit     = request.count,
                                                     keys_only = True)

        return ListRespMessage(job_id = [k.integer_id() for k in jobs_keys])

# The Server

application = endpoints.api_server([JobApi],
                                    restricted=False)

# EOF
