from threading import Thread
from werkzeug.serving import make_server

class FlaskAppWrapper(Thread):

    def __init__(self, app, **kwargs):
        Thread.__init__(self, **kwargs)
        self.srv = make_server('0.0.0.0', 6767, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        self.srv.serve_forever()

    def join(self, timeout=None):
        self.srv.shutdown()
        super(FlaskAppWrapper, self).join(timeout)
