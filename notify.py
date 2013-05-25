import webapp2
from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.api import oauth
from google.appengine.ext.webapp import template
import datetime
import os
import logging

# Data

class UserPrefs(db.Model):
    user_id = db.StringProperty(required = True)

class Job(db.Model):
    user_id = db.StringProperty(required = True)
    created_date = db.DateTimeProperty(auto_now_add = True)
    finished_date = db.DateTimeProperty()
    command = db.TextProperty(required = True)
    exit_code = db.IntegerProperty()
    output = db.TextProperty(default = "")

# Code

class NewJobHandler(webapp2.RequestHandler):
    def post(self):
        user = oauth.get_current_user()
        job = Job(user_id = user.user_id(),
                  command = self.request.get("command"))
        job.put()
        logging.info("Created new job %s" % job.key())
        self.response.write(job.key())

def job_from_key(key):
        try:
            return db.get(key)
        except db.Error as e:
            return None

class JobHandler(webapp2.RequestHandler):
    def get_user_job(self, job_id, post):
        user = users.get_current_user() or oauth.get_current_user()
        if not user:
            if post:
                self.abort(403)
            else:
                self.redirect(users.create_login_url(), abort = True)

        job = job_from_key(job_id)
        if not job:
            self.abort(404)

        if (user.user_id() != job.user_id):
            self.abort(403)
        return user, job

    def post(self, job_id):
        user, job = self.get_user_job(job_id, True)
        action = self.request.get("action", default_value = None)
        if not action:
            self.abort(404)
        if action == "delete":
            job.delete()
            self.redirect_to("main")
        elif action == "update":
            if self.request.get("finished", default_value = False):
                job.finished_date = datetime.datetime.now()
            output = self.request.get("output", default_value = "")
            job.output += output
            if len(job.output) > (1 << 16):
                job.output = job.output[-(1 << 16):]
                logging.info("Trimmed output to %u bytes" % len(job.output))
            exit_code = self.request.get("exit_code", default_value = None)
            if exit_code != None:
                job.exit_code = int(exit_code)
            job.put()

    def get(self, job_id):
        user, job = self.get_user_job(job_id, False)
        self.response.out.write("user = %s job = %s" % (user.user_id(), job.key()))

class LoginHandler(webapp2.RequestHandler):
    def get(self):
        template_values = {
            'logouturl': users.create_logout_url("/login"),
            'loginurl':  users.create_login_url(),
        }
        path = os.path.join(os.path.dirname(__file__), 'template/login.html')
        self.response.out.write(template.render(path, template_values))

class MainPage(webapp2.RequestHandler):

    def get(self):
        user = users.get_current_user()
        if not user:
            self.redirect_to("login", _abort = True)

        q = UserPrefs.all()
        q.filter("user_id =", user.user_id())
        userprefs = q.get()

        q = Job.all()
        q.filter("user_id =", user.user_id())
        q.order("-created_date")

        template_values = {
            'logouturl': users.create_logout_url("/login"),
            'firsttime': False,
            'nick' : user.nickname(),
            'jobs' : q.fetch(limit = 50),
        }

        if not userprefs:
            template_values['firsttime'] = True
            userprefs = UserPrefs(user_id = user.user_id())
            userprefs.put()

        path = os.path.join(os.path.dirname(__file__), 'template/main.html')
        self.response.out.write(template.render(path, template_values))


application = webapp2.WSGIApplication([
        webapp2.Route(r'/', handler=MainPage, name='main'),
        webapp2.Route(r'/login', handler=LoginHandler, name='login'),
        webapp2.Route(r'/new-job', handler=NewJobHandler, name='new-job'),
        webapp2.Route(r'/job/<job_id:[^/]+>', handler=JobHandler, name='job'),

        ], debug=True)
