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
<center><img src="stream.mjpg" width="640" height="480"></center>
</body>
</html>
"""

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
config = configparser.ConfigParser()
config.read(__location__ + '/config.ini')

class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.frame_num = 0
        self.buffer = io.BytesIO()
        self.condition = Condition()
        self.starttime = time.time()
        if (config['DEFAULT'].getint('TimelapseTime') > 0 and config['DEFAULT']['TimelapsePath']):
            try:
                os.mkdir("%s/%s" % (config['DEFAULT']['TimelapsePath'], self.starttime))
                self.output = None
                self.timelapse_time = config['DEFAULT'].getint('TimelapseTime')
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
            if (self.timelapse_time > 0):
                if self.output:
                    self.output.close()

                if (math.floor((time.time() - self.starttime) / self.timelapse_time) > self.frame_num):
                    self.frame_num += 1
                    self.output = io.open('./%s/image%02d.jpg' % (self.starttime, self.frame_num), 'wb')
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

with picamera.PiCamera(resolution='640x480', framerate=24) as camera:
    output = StreamingOutput()
    #Uncomment the next line to change your Pi's Camera rotation (in degrees)
    #camera.rotation = 90
    time.sleep(2)
    camera.iso = 800
    camera.shutter_speed = camera.exposure_speed
    camera.exposure_mode = 'off'
    camera.awb_mode = 'fluorescent'
    camera.start_recording(output, format='mjpeg')
    try:
        port = config['DEFAULT'].getint('Port')
        address = ('', port)
        server = StreamingServer(address, StreamingHandler)
        server.serve_forever()
    except Exception as err:
        syslog.syslog(syslog.LOG_ERR, 'Error in server creation: %s' % err)
    finally:
        camera.stop_recording()
