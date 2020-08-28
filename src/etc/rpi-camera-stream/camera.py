# Web streaming example
# Source code from the official PiCamera package
# http://picamera.readthedocs.io/en/latest/recipes2.html#web-streaming

import io
import picamera
import logging
import socketserver
import configparser
import os
import time
import math
import syslog
from threading import Condition
from http import server

PAGE="""\
<html>
<head>
<title>Raspberry Pi - Surveillance Camera</title>
</head>
<body>
<center><h1>Raspberry Pi - Surveillance Camera</h1></center>
<center><img src="stream.mjpg" style="max-width: 100%; max-height: 100%;" /></center>
</body>
</html>
"""

def isint(value):
    try:
        int(value)
        return True
    except ValueError:
        return False

def isfloat(value):
    try:
        float(value)
        return True
    except ValueError:
        return False

class Config():
    def __init__(self):
        __location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
        config = configparser.ConfigParser()
        config.read(__location__ + '/config.ini')

        # Server
        self.server = config._sections['SERVER']
        self.server['port'] = int(self.server['port']) or 8000

        # Timelapse
        self.timelapse = config._sections['TIMELAPSE']
        self.timelapse['interval'] = int(self.timelapse['interval']) or 0
        self.timelapse['path'] = self.timelapse['path'] or '/'

        # Camera
        self.camera = config._sections['CAMERA']
        for c in self.camera:
            if isint(self.camera[c]):
                self.camera[c] = int(self.camera[c])
                continue
            if isfloat(self.camera[c]):
                self.camera[c] = float(self.camera[c])
                continue

config = Config()

class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.frame_num = 0
        self.buffer = io.BytesIO()
        self.condition = Condition()
        self.starttime = time.time()
        self.timelapse_interval = config.timelapse['interval']
        self.output = None

        if (self.timelapse_interval > 0 and config.timelapse['path']):
            try:
                os.mkdir("%s/%s" % (config.timelapse['path'], self.starttime))
            except Exception as err:
                syslog.syslog(syslog.LOG_ERR, 'Error in timelapse init: %s' % err)

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)

            # save image every x seconds
            if (self.timelapse_interval > 0):
                if self.output:
                    self.output.close()

                if (math.floor((time.time() - self.starttime) / self.timelapse_interval) > self.frame_num):
                    self.frame_num += 1
                    self.output = io.open('%s/%s/image%02d.jpg' % (config.timelapse.path, self.starttime, self.frame_num), 'wb')
                    self.output.write(buf)

        return self.buffer.write(buf)

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

with picamera.PiCamera() as camera:
    output = StreamingOutput()
    for c in config.camera:
        setattr(camera, c, config.camera[c])

    camera.start_recording(output, format='mjpeg')
    try:
        port = config.server['port']
        address = ('', port)
        server = StreamingServer(address, StreamingHandler)
        server.serve_forever()
    except Exception as err:
        syslog.syslog(syslog.LOG_ERR, 'Error in server creation: %s' % err)
    finally:
        camera.stop_recording()
