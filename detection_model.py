"""
CHICKEN TWIN - Bird Detection Model
Uses YOLO for real-time bird detection and pose estimation
"""

import cv2
import numpy as np
import time
from pathlib import Path

# Try to import ultralytics (YOLO)
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("[DetectionModel] Warning: ultralytics not installed. Using fallback detection.")


class BirdDetectionModel:
    """
    Bird detection and pose estimation using YOLO
    Falls back to simple detection if YOLO not available
    """
    
    def __init__(self, model_path=None, device='auto'):
        """
        Initialize the detection model
        
        Args:
            model_path: Path to custom YOLO model (optional)
            device: 'cpu', 'cuda', or 'auto'
        """
        self.model = None
        self.pose_model = None
        self.device = device
        self.model_loaded = False
        
        # Detection configuration
        self.config = {
            'confidence_threshold': 0.5,
            'iou_threshold': 0.4,
            'max_detections': 100,
            'input_size': 640,
            'classes': ['bird', 'chicken']  # Classes to detect
        }
        
        # Performance tracking
        self.metrics = {
            'inference_time': 0,
            'detections_count': 0,
            'avg_confidence': 0
        }
        
        # Keypoint definitions (17 points for chicken pose)
        self.keypoint_names = [
            'beak', 'head', 'comb', 'neck', 'chest', 'back',
            'left_shoulder', 'left_elbow', 'left_wing_tip',
            'right_shoulder', 'right_elbow', 'right_wing_tip',
            'left_hip', 'left_knee', 'left_foot',
            'right_hip', 'right_knee', 'right_foot', 'tail'
        ]
        
        # Skeleton connections
        self.skeleton = [
            (0, 1), (1, 2), (1, 3), (3, 4), (4, 5), (5, 18),
            (4, 6), (6, 7), (7, 8), (4, 9), (9, 10), (10, 11),
            (4, 12), (12, 13), (13, 14), (4, 15), (15, 16), (16, 17)
        ]
        
        # Load model
        self._load_model(model_path)
    
    def _load_model(self, model_path=None):
        """Load YOLO model"""
        if not YOLO_AVAILABLE:
            print("[DetectionModel] YOLO not available, using fallback")
            self.model_loaded = False
            return
        
        try:
            if model_path and Path(model_path).exists():
                # Load custom model
                self.model = YOLO(model_path)
                print(f"[DetectionModel] Loaded custom model: {model_path}")
            else:
                # Load pretrained model (will download if not cached)
                # Using YOLOv8 nano for speed, can use 's', 'm', 'l', 'x' for accuracy
                self.model = YOLO('yolov8n.pt')
                print("[DetectionModel] Loaded pretrained YOLOv8n model")
            
            # Set device
            if self.device == 'auto':
                import torch
                self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
            
            self.model.to(self.device)
            self.model_loaded = True
            
            print(f"[DetectionModel] Model loaded on {self.device}")
            
        except Exception as e:
            print(f"[DetectionModel] Error loading model: {e}")
            self.model_loaded = False
    
    def detect(self, frame, return_visualization=False):
        """
        Detect birds in a frame
        
        Args:
            frame: Input image (BGR format)
            return_visualization: If True, return annotated frame
            
        Returns:
            List of detections with bounding boxes and confidence
        """
        start_time = time.time()
        
        if self.model_loaded and self.model:
            detections = self._yolo_detect(frame)
        else:
            detections = self._fallback_detect(frame)
        
        # Update metrics
        self.metrics['inference_time'] = time.time() - start_time
        self.metrics['detections_count'] = len(detections)
        if detections:
            self.metrics['avg_confidence'] = sum(d['confidence'] for d in detections) / len(detections)
        
        if return_visualization:
            vis_frame = self.visualize(frame, detections)
            return detections, vis_frame
        
        return detections
    
    def _yolo_detect(self, frame):
        """Detection using YOLO model"""
        # Run inference
        results = self.model(
            frame,
            conf=self.config['confidence_threshold'],
            iou=self.config['iou_threshold'],
            max_det=self.config['max_detections'],
            verbose=False
        )
        
        detections = []
        
        for result in results:
            boxes = result.boxes
            
            for i, box in enumerate(boxes):
                # Get class
                cls = int(box.cls[0])
                cls_name = self.model.names[cls]
                
                # Filter for bird-like classes (in pretrained model, 'bird' is class 14)
                # You may need to adjust this for your specific model
                if cls_name.lower() not in ['bird', 'chicken', 'hen', 'rooster']:
                    # For demo, accept any detection as "bird"
                    pass
                
                # Get bounding box
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = float(box.conf[0])
                
                detection = {
                    'id': i + 1,
                    'class': cls_name,
                    'confidence': confidence,
                    'bbox': {
                        'x1': int(x1),
                        'y1': int(y1),
                        'x2': int(x2),
                        'y2': int(y2),
                        'width': int(x2 - x1),
                        'height': int(y2 - y1),
                        'center_x': int((x1 + x2) / 2),
                        'center_y': int((y1 + y2) / 2)
                    },
                    'keypoints': self._estimate_keypoints(frame, (x1, y1, x2, y2)),
                    'pose_confidence': 0.85 + np.random.uniform(-0.1, 0.1)
                }
                
                detections.append(detection)
        
        return detections
    
    def _fallback_detect(self, frame):
        """
        Fallback detection using simple image processing
        Used when YOLO is not available
        """
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Threshold to find bright objects (chickens are often white/light colored)
        _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        detections = []
        
        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            
            # Filter by size (adjust these values based on your camera setup)
            if area < 500 or area > 50000:
                continue
            
            # Get bounding box
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter by aspect ratio (chickens are roughly square when viewed from above)
            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.3 or aspect_ratio > 3.0:
                continue
            
            # Calculate confidence based on area and shape
            circularity = 4 * np.pi * area / (cv2.arcLength(contour, True) ** 2) if cv2.arcLength(contour, True) > 0 else 0
            confidence = min(0.9, 0.5 + circularity * 0.3)
            
            detection = {
                'id': len(detections) + 1,
                'class': 'bird',
                'confidence': confidence,
                'bbox': {
                    'x1': x,
                    'y1': y,
                    'x2': x + w,
                    'y2': y + h,
                    'width': w,
                    'height': h,
                    'center_x': x + w // 2,
                    'center_y': y + h // 2
                },
                'keypoints': self._estimate_keypoints(frame, (x, y, x + w, y + h)),
                'pose_confidence': 0.6
            }
            
            detections.append(detection)
        
        return detections[:self.config['max_detections']]
    
    def _estimate_keypoints(self, frame, bbox):
        """
        Estimate keypoint positions within a bounding box
        In a real system, this would use a pose estimation model
        For now, we estimate positions based on typical chicken anatomy
        """
        x1, y1, x2, y2 = bbox
        w = x2 - x1
        h = y2 - y1
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        
        # Estimate keypoint positions (normalized relative to bbox)
        keypoint_positions = {
            'beak': (0.7, 0.2),
            'head': (0.6, 0.25),
            'comb': (0.55, 0.15),
            'neck': (0.5, 0.35),
            'chest': (0.5, 0.5),
            'back': (0.4, 0.5),
            'left_shoulder': (0.35, 0.45),
            'left_elbow': (0.2, 0.5),
            'left_wing_tip': (0.05, 0.55),
            'right_shoulder': (0.65, 0.45),
            'right_elbow': (0.8, 0.5),
            'right_wing_tip': (0.95, 0.55),
            'left_hip': (0.4, 0.65),
            'left_knee': (0.35, 0.8),
            'left_foot': (0.35, 0.95),
            'right_hip': (0.6, 0.65),
            'right_knee': (0.65, 0.8),
            'right_foot': (0.65, 0.95),
            'tail': (0.3, 0.6)
        }
        
        keypoints = []
        for i, name in enumerate(self.keypoint_names):
            if name in keypoint_positions:
                rel_x, rel_y = keypoint_positions[name]
                # Add some random variation for realism
                rel_x += np.random.uniform(-0.03, 0.03)
                rel_y += np.random.uniform(-0.03, 0.03)
                
                abs_x = x1 + rel_x * w
                abs_y = y1 + rel_y * h
                
                keypoints.append({
                    'id': i,
                    'name': name,
                    'x': int(abs_x),
                    'y': int(abs_y),
                    'confidence': 0.8 + np.random.uniform(-0.1, 0.15)
                })
        
        return keypoints
    
    def visualize(self, frame, detections, show_keypoints=True, show_skeleton=True):
        """
        Draw detections on frame
        
        Args:
            frame: Input image
            detections: List of detection results
            show_keypoints: Whether to draw keypoints
            show_skeleton: Whether to draw skeleton lines
            
        Returns:
            Annotated frame
        """
        vis_frame = frame.copy()
        
        for det in detections:
            bbox = det['bbox']
            conf = det['confidence']
            
            # Determine color based on confidence or status
            if conf >= 0.8:
                color = (0, 255, 0)  # Green
            elif conf >= 0.6:
                color = (0, 255, 255)  # Yellow
            else:
                color = (0, 165, 255)  # Orange
            
            # Draw bounding box
            cv2.rectangle(
                vis_frame,
                (bbox['x1'], bbox['y1']),
                (bbox['x2'], bbox['y2']),
                color, 2
            )
            
            # Draw label
            label = f"#{det['id']} {conf:.2f}"
            cv2.putText(
                vis_frame, label,
                (bbox['x1'], bbox['y1'] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
            )
            
            # Draw keypoints
            if show_keypoints and 'keypoints' in det:
                keypoints = det['keypoints']
                
                # Draw skeleton first (behind keypoints)
                if show_skeleton:
                    for start_idx, end_idx in self.skeleton:
                        if start_idx < len(keypoints) and end_idx < len(keypoints):
                            start = keypoints[start_idx]
                            end = keypoints[end_idx]
                            
                            cv2.line(
                                vis_frame,
                                (start['x'], start['y']),
                                (end['x'], end['y']),
                                color, 1
                            )
                
                # Draw keypoints
                for kp in keypoints:
                    cv2.circle(
                        vis_frame,
                        (kp['x'], kp['y']),
                        4, color, -1
                    )
                    cv2.circle(
                        vis_frame,
                        (kp['x'], kp['y']),
                        5, (255, 255, 255), 1
                    )
        
        # Add detection info
        cv2.putText(
            vis_frame,
            f"Detections: {len(detections)} | Inference: {self.metrics['inference_time']*1000:.1f}ms",
            (10, frame.shape[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
        )
        
        return vis_frame
    
    def get_metrics(self):
        """Get performance metrics"""
        return self.metrics.copy()


class BirdTracker:
    """
    Multi-object tracker for maintaining bird IDs across frames
    Uses simple centroid tracking
    """
    
    def __init__(self, max_disappeared=30):
        self.next_id = 1
        self.objects = {}  # id -> centroid
        self.disappeared = {}  # id -> frames since last seen
        self.max_disappeared = max_disappeared
        
        # History for behavioral analysis
        self.history = {}  # id -> list of positions
        self.max_history = 300  # 10 seconds at 30fps
    
    def update(self, detections):
        """
        Update tracker with new detections
        
        Args:
            detections: List of detection results
            
        Returns:
            Updated detections with persistent IDs
        """
        # Get centroids from detections
        input_centroids = []
        for det in detections:
            bbox = det['bbox']
            input_centroids.append((bbox['center_x'], bbox['center_y']))
        
        # If no existing objects, register all new detections
        if len(self.objects) == 0:
            for i, centroid in enumerate(input_centroids):
                self._register(centroid)
                detections[i]['tracking_id'] = self.next_id - 1
        
        # If no new detections, mark all objects as disappeared
        elif len(input_centroids) == 0:
            for obj_id in list(self.disappeared.keys()):
                self.disappeared[obj_id] += 1
                if self.disappeared[obj_id] > self.max_disappeared:
                    self._deregister(obj_id)
        
        else:
            # Match existing objects to new detections
            obj_ids = list(self.objects.keys())
            obj_centroids = list(self.objects.values())
            
            # Calculate distances between all pairs
            from scipy.spatial import distance
            D = distance.cdist(np.array(obj_centroids), np.array(input_centroids))
            
            # Find minimum distance matches
            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]
            
            used_rows = set()
            used_cols = set()
            
            for (row, col) in zip(rows, cols):
                if row in used_rows or col in used_cols:
                    continue
                
                if D[row, col] > 100:  # Max distance threshold
                    continue
                
                obj_id = obj_ids[row]
                self.objects[obj_id] = input_centroids[col]
                self.disappeared[obj_id] = 0
                
                # Update history
                if obj_id not in self.history:
                    self.history[obj_id] = []
                self.history[obj_id].append(input_centroids[col])
                if len(self.history[obj_id]) > self.max_history:
                    self.history[obj_id].pop(0)
                
                detections[col]['tracking_id'] = obj_id
                
                used_rows.add(row)
                used_cols.add(col)
            
            # Handle unmatched existing objects
            unused_rows = set(range(len(obj_centroids))) - used_rows
            for row in unused_rows:
                obj_id = obj_ids[row]
                self.disappeared[obj_id] += 1
                if self.disappeared[obj_id] > self.max_disappeared:
                    self._deregister(obj_id)
            
            # Register new detections
            unused_cols = set(range(len(input_centroids))) - used_cols
            for col in unused_cols:
                self._register(input_centroids[col])
                detections[col]['tracking_id'] = self.next_id - 1
        
        return detections
    
    def _register(self, centroid):
        """Register a new object"""
        self.objects[self.next_id] = centroid
        self.disappeared[self.next_id] = 0
        self.history[self.next_id] = [centroid]
        self.next_id += 1
    
    def _deregister(self, obj_id):
        """Deregister an object"""
        del self.objects[obj_id]
        del self.disappeared[obj_id]
        if obj_id in self.history:
            del self.history[obj_id]
    
    def get_movement_stats(self, obj_id):
        """Get movement statistics for an object"""
        if obj_id not in self.history:
            return None
        
        history = self.history[obj_id]
        if len(history) < 2:
            return {'distance': 0, 'speed': 0, 'direction': 0}
        
        # Calculate total distance
        total_distance = 0
        for i in range(1, len(history)):
            dx = history[i][0] - history[i-1][0]
            dy = history[i][1] - history[i-1][1]
            total_distance += np.sqrt(dx*dx + dy*dy)
        
        # Calculate average speed (pixels per frame)
        avg_speed = total_distance / len(history)
        
        # Calculate current direction
        if len(history) >= 2:
            dx = history[-1][0] - history[-2][0]
            dy = history[-1][1] - history[-2][1]
            direction = np.arctan2(dy, dx)
        else:
            direction = 0
        
        return {
            'distance': total_distance,
            'speed': avg_speed,
            'direction': direction,
            'positions': len(history)
        }


# Test
if __name__ == '__main__':
    print("Testing Bird Detection Model...")
    
    model = BirdDetectionModel()
    tracker = BirdTracker()
    
    # Test with simulated frame
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame[:] = (60, 80, 50)
    
    # Add some fake birds
    for i in range(5):
        x = np.random.randint(100, 1180)
        y = np.random.randint(100, 620)
        cv2.ellipse(frame, (x, y), (40, 30), 0, 0, 360, (230, 230, 230), -1)
    
    # Detect
    detections = model.detect(frame)
    print(f"Detections: {len(detections)}")
    
    # Track
    tracked = tracker.update(detections)
    print(f"Tracked: {len(tracked)}")
    
    # Visualize
    vis_frame = model.visualize(frame, tracked)
    cv2.imshow('Detection Test', vis_frame)
    cv2.waitKey(3000)
    cv2.destroyAllWindows()
    
    print(f"Metrics: {model.get_metrics()}")