"""
CHICKEN TWIN - Camera Service
Handles real camera feed processing with OpenCV
"""

import cv2
import numpy as np
import threading
import time
import base64
from queue import Queue
from datetime import datetime

class CameraService:
    """
    Manages camera feeds and frame processing
    Supports multiple cameras and various input sources
    """
    
    def __init__(self):
        self.cameras = {}
        self.frame_queues = {}
        self.running = False
        self.frame_callbacks = []
        self.recording = False
        self.video_writers = {}
        
        # Configuration
        self.config = {
            'default_resolution': (1920, 1080),
            'default_fps': 30,
            'jpeg_quality': 85,
            'buffer_size': 10
        }
        
        # Performance metrics
        self.metrics = {
            'frames_processed': 0,
            'avg_processing_time': 0,
            'dropped_frames': 0,
            'last_frame_time': 0
        }
    
    def add_camera(self, camera_id, source, name=None):
        """
        Add a camera source
        
        Args:
            camera_id: Unique identifier for the camera
            source: Can be:
                - Integer (0, 1, 2...) for USB cameras
                - String path for video file
                - RTSP URL for IP cameras
                - 'simulation' for simulated feed
            name: Human-readable name
        """
        try:
            if source == 'simulation':
                cap = SimulatedCamera(self.config['default_resolution'])
            else:
                cap = cv2.VideoCapture(source)
                
                if not cap.isOpened():
                    raise Exception(f"Failed to open camera: {source}")
                
                # Set resolution
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config['default_resolution'][0])
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config['default_resolution'][1])
                cap.set(cv2.CAP_PROP_FPS, self.config['default_fps'])
            
            self.cameras[camera_id] = {
                'capture': cap,
                'name': name or f'Camera {camera_id}',
                'source': source,
                'active': True,
                'last_frame': None,
                'fps': 0,
                'resolution': self.config['default_resolution']
            }
            
            self.frame_queues[camera_id] = Queue(maxsize=self.config['buffer_size'])
            
            print(f"[CameraService] Added camera: {camera_id} ({name})")
            return True
            
        except Exception as e:
            print(f"[CameraService] Error adding camera {camera_id}: {e}")
            return False
    
    def remove_camera(self, camera_id):
        """Remove a camera"""
        if camera_id in self.cameras:
            self.cameras[camera_id]['capture'].release()
            del self.cameras[camera_id]
            del self.frame_queues[camera_id]
            print(f"[CameraService] Removed camera: {camera_id}")
    
    def start(self):
        """Start capturing from all cameras"""
        self.running = True
        
        for camera_id in self.cameras:
            thread = threading.Thread(
                target=self._capture_loop,
                args=(camera_id,),
                daemon=True
            )
            thread.start()
        
        print("[CameraService] Started capturing")
    
    def stop(self):
        """Stop all camera captures"""
        self.running = False
        time.sleep(0.5)  # Allow threads to finish
        
        for camera_id, cam_data in self.cameras.items():
            cam_data['capture'].release()
            if camera_id in self.video_writers:
                self.video_writers[camera_id].release()
        
        print("[CameraService] Stopped capturing")
    
    def _capture_loop(self, camera_id):
        """Main capture loop for a camera"""
        cam_data = self.cameras[camera_id]
        cap = cam_data['capture']
        
        frame_count = 0
        start_time = time.time()
        
        while self.running and cam_data['active']:
            ret, frame = cap.read()
            
            if not ret:
                print(f"[CameraService] Failed to read from {camera_id}")
                time.sleep(0.1)
                continue
            
            # Calculate FPS
            frame_count += 1
            elapsed = time.time() - start_time
            if elapsed >= 1.0:
                cam_data['fps'] = frame_count / elapsed
                frame_count = 0
                start_time = time.time()
            
            # Store last frame
            cam_data['last_frame'] = frame
            cam_data['resolution'] = (frame.shape[1], frame.shape[0])
            
            # Add to queue (drop oldest if full)
            if self.frame_queues[camera_id].full():
                try:
                    self.frame_queues[camera_id].get_nowait()
                    self.metrics['dropped_frames'] += 1
                except:
                    pass
            
            self.frame_queues[camera_id].put({
                'camera_id': camera_id,
                'frame': frame,
                'timestamp': datetime.now().isoformat(),
                'frame_number': self.metrics['frames_processed']
            })
            
            self.metrics['frames_processed'] += 1
            self.metrics['last_frame_time'] = time.time()
            
            # Call registered callbacks
            for callback in self.frame_callbacks:
                try:
                    callback(camera_id, frame)
                except Exception as e:
                    print(f"[CameraService] Callback error: {e}")
            
            # Recording
            if self.recording and camera_id in self.video_writers:
                self.video_writers[camera_id].write(frame)
    
    def get_frame(self, camera_id, encode=False):
        """
        Get the latest frame from a camera
        
        Args:
            camera_id: Camera identifier
            encode: If True, return base64 encoded JPEG
        """
        if camera_id not in self.cameras:
            return None
        
        frame = self.cameras[camera_id]['last_frame']
        if frame is None:
            return None
        
        if encode:
            return self.encode_frame(frame)
        
        return frame
    
    def get_frame_from_queue(self, camera_id, timeout=1.0):
        """Get next frame from queue (blocking)"""
        if camera_id not in self.frame_queues:
            return None
        
        try:
            return self.frame_queues[camera_id].get(timeout=timeout)
        except:
            return None
    
    def encode_frame(self, frame, quality=None):
        """Encode frame to base64 JPEG"""
        quality = quality or self.config['jpeg_quality']
        
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return base64.b64encode(buffer).decode('utf-8')
    
    def decode_frame(self, base64_data):
        """Decode base64 JPEG to frame"""
        buffer = base64.b64decode(base64_data)
        nparr = np.frombuffer(buffer, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    def start_recording(self, output_dir='recordings'):
        """Start recording all camera feeds"""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for camera_id, cam_data in self.cameras.items():
            filepath = os.path.join(output_dir, f"{camera_id}_{timestamp}.mp4")
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            
            self.video_writers[camera_id] = cv2.VideoWriter(
                filepath,
                fourcc,
                self.config['default_fps'],
                cam_data['resolution']
            )
        
        self.recording = True
        print(f"[CameraService] Started recording to {output_dir}")
    
    def stop_recording(self):
        """Stop recording"""
        self.recording = False
        
        for camera_id, writer in self.video_writers.items():
            writer.release()
        
        self.video_writers = {}
        print("[CameraService] Stopped recording")
    
    def register_callback(self, callback):
        """Register a callback for new frames"""
        self.frame_callbacks.append(callback)
    
    def get_camera_info(self, camera_id=None):
        """Get information about cameras"""
        if camera_id:
            if camera_id in self.cameras:
                cam = self.cameras[camera_id]
                return {
                    'id': camera_id,
                    'name': cam['name'],
                    'active': cam['active'],
                    'fps': cam['fps'],
                    'resolution': cam['resolution']
                }
            return None
        
        return [
            {
                'id': cid,
                'name': cam['name'],
                'active': cam['active'],
                'fps': cam['fps'],
                'resolution': cam['resolution']
            }
            for cid, cam in self.cameras.items()
        ]
    
    def get_metrics(self):
        """Get performance metrics"""
        return self.metrics.copy()


class SimulatedCamera:
    """
    Simulated camera for testing without real hardware
    Generates frames with animated chickens
    """
    
    def __init__(self, resolution=(1920, 1080)):
        self.resolution = resolution
        self.frame_count = 0
        self.chickens = self._init_chickens(25)
    
    def _init_chickens(self, count):
        """Initialize simulated chickens"""
        chickens = []
        for i in range(count):
            chickens.append({
                'id': i + 1,
                'x': np.random.randint(100, self.resolution[0] - 100),
                'y': np.random.randint(100, self.resolution[1] - 100),
                'vx': np.random.uniform(-2, 2),
                'vy': np.random.uniform(-2, 2),
                'size': np.random.randint(30, 50),
                'status': np.random.choice(['healthy', 'warning', 'critical'], p=[0.8, 0.15, 0.05])
            })
        return chickens
    
    def read(self):
        """Generate a simulated frame"""
        # Create background
        frame = np.zeros((self.resolution[1], self.resolution[0], 3), dtype=np.uint8)
        
        # Farm floor color
        frame[:, :] = (60, 80, 50)  # Greenish-brown
        
        # Draw grid
        for x in range(0, self.resolution[0], 100):
            cv2.line(frame, (x, 0), (x, self.resolution[1]), (70, 90, 60), 1)
        for y in range(0, self.resolution[1], 100):
            cv2.line(frame, (0, y), (self.resolution[0], y), (70, 90, 60), 1)
        
        # Update and draw chickens
        for chicken in self.chickens:
            # Update position
            chicken['x'] += chicken['vx']
            chicken['y'] += chicken['vy']
            
            # Bounce off walls
            if chicken['x'] < 50 or chicken['x'] > self.resolution[0] - 50:
                chicken['vx'] *= -1
            if chicken['y'] < 50 or chicken['y'] > self.resolution[1] - 50:
                chicken['vy'] *= -1
            
            # Random direction changes
            if np.random.random() < 0.02:
                chicken['vx'] = np.random.uniform(-2, 2)
                chicken['vy'] = np.random.uniform(-2, 2)
            
            # Draw chicken
            x, y = int(chicken['x']), int(chicken['y'])
            size = chicken['size']
            
            # Color based on status
            if chicken['status'] == 'critical':
                color = (60, 60, 220)  # Red
            elif chicken['status'] == 'warning':
                color = (50, 180, 230)  # Yellow
            else:
                color = (230, 230, 230)  # White
            
            # Body
            cv2.ellipse(frame, (x, y), (size, int(size * 0.7)), 0, 0, 360, color, -1)
            
            # Head
            head_x = x + int(size * 0.6 * np.sign(chicken['vx']))
            cv2.circle(frame, (head_x, y - int(size * 0.3)), int(size * 0.3), color, -1)
            
            # Beak
            cv2.circle(frame, (head_x + int(size * 0.2 * np.sign(chicken['vx'])), y - int(size * 0.3)), 
                      int(size * 0.1), (50, 150, 230), -1)
            
            # ID label
            cv2.putText(frame, f"#{chicken['id']}", (x - 15, y - size - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # Add timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        cv2.putText(frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Add frame counter
        cv2.putText(frame, f"Frame: {self.frame_count}", (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        
        self.frame_count += 1
        
        return True, frame
    
    def release(self):
        """Release resources"""
        pass
    
    def isOpened(self):
        return True
    
    def set(self, prop, value):
        pass


# ═══════════════════════════════════════════════════════════════
# CAMERA API ENDPOINTS (Add to server.py)
# ═══════════════════════════════════════════════════════════════

camera_service = None

def init_camera_service():
    """Initialize camera service"""
    global camera_service
    camera_service = CameraService()
    
    # Add simulated camera by default
    camera_service.add_camera('cam_main', 'simulation', 'Main Farm Camera')
    
    return camera_service


def get_camera_service():
    """Get or create camera service"""
    global camera_service
    if camera_service is None:
        camera_service = init_camera_service()
    return camera_service


# Test
if __name__ == '__main__':
    print("Testing Camera Service...")
    
    service = CameraService()
    service.add_camera('test', 'simulation', 'Test Camera')
    service.start()
    
    # Display frames for 10 seconds
    start = time.time()
    while time.time() - start < 10:
        frame = service.get_frame('test')
        if frame is not None:
            cv2.imshow('Test', frame)
            if cv2.waitKey(30) & 0xFF == ord('q'):
                break
    
    service.stop()
    cv2.destroyAllWindows()
    
    print(f"Metrics: {service.get_metrics()}")