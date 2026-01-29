# 🐔 CHICKEN TWIN - Technical Manual & Simulation Engine

> Built by **Instaflect AI** for the Surge X Lablab.ai Hackathon.

## 🔭 Project Overview
CHICKEN TWIN is an industrial-grade **Digital Twin** designed for high-precision avian behavioral analysis and autonomous robotic intervention. It creates a 1:1 virtual floor-space where AI agents monitor livestock health at a "particle level," detecting microscopic symptoms and executing physically accurate robotic responses.

---

## 🏗️ Technical Architecture

### **1. Simulation Logic (Particle-Level Detail)**
The simulation runs on a high-frequency loop (60Hz) using a **state-update-render** cycle.
- **Entity Mobility**: Every bird is an object instance with independent vectors for `position`, `velocity`, and `acceleration`.
- **The "Boids" Influence**: Bird movement uses a simplified flocking algorithm containing three forces:
  1. **Cohesion**: Steering toward the average position of the flock.
  2. **Separation**: Steering to avoid crowding (collision avoidance).
  3. **Wander**: A Perlin-noise based "random walk" that simulates natural curiosity.
- **Disease Vectors**: Diseases are non-linear state machines. Once a bird is `infected`, its `internalTemperature` rises at 0.05°C per minute, and its `mobilityFactor` decays, leading to perceptible lethargy.

### **2. AI Vision & Detection Agent**
The **Green AI View** is not just a shader; it's a visualization of the underlying detection matrix.
- **Keypoint Skeleton**: The AI tracks 18 distinct anatomical joints. By calculating the **inverse kinematics (IK)** between wings and body, it detects "Wing Droop" (a precursor to H5N1).
- **Behavioral Fingerprinting**: The AI monitors **Gait Asymmetry**. If the step-length of the left leg vs right leg differs by > 15%, the bird is flagged for "Limping."
- **Trace Analysis**: The system renders dynamic "traces" (Feces). 
  - **Red Tracer**: High mortality indicators (Bloody feces).
  - **White Tracer**: Hydration issues.

### **3. Robotic Engineering (ROBO-SM)**
The robot uses a **Telescoping Brother-Node Hierarchy** for the arm.
- **Physics Constraint**: Unlike simple scaling, the segments are individually addressed meshes that maintain their diameter while extending, ensuring visual stability.
- **Interpolation**: Movement uses `ease-in-out` quintic interpolation to simulate the mass and momentum of industrial servos.
- **Mission Sequence**:
  - `SCAN` → `INTERCEPT` → `DESCEND` → `SECURE` → `RETRACT` → `DEPOSIT`.

### **4. Backend Juggernaut (`monitor.py`)**
The Python backend acts as the "Cognitive Core."
- **WebSocket Telemetry**: It broadcasts a serialized JSON stream containing every bird's coordinate and risk score.
- **Persistent Memory**: Saves session data to a local server-side database, allowing for high-speed replay with 100% frame fidelity.
- **Safety Net**: The **Fallback AI** (browser-side) takes over if the Python core loses heartbeat, ensuring 100% uptime for live demos.

---

## 🛠️ Stack Summary
- **Visuals**: Three.js (WebGL), Canvas API.
- **Brain**: Flask (Python), WebSockets (Socket.IO).
- **Interface**: Glassmorphism CSS, Inter/Space Grotesk Typography.
- **Infrastructure**: Session Persistence via LocalStorage API & Python OS File System.

---

## 🚀 Vision by Instaflect AI
Instaflect AI specializes in "Insight through Autonomy." This project demonstrates how digital twins can solve the most difficult agricultural challenges by replacing human error with robotic precision.


# 🐔 CHICKEN TWIN - Full System Architecture & Logic

This document provides a "down to the particle" explanation of the Chicken Twin simulation, the AI logic, the web stack, and the robotic autonomous behaviors.

---

## 🌍 1. The Core Vision
**Chicken Twin** is a high-fidelity Digital Twin simulation designed to bridge the gap between AI behavioral analysis and physical robotic intervention in poultry farming. It solves the "human bottleneck" in disease management by autonomously identifying and isolating sick birds before an outbreak occurs.

---

## 💻 2. The Technology Stack

### **Frontend (The Interface & Physics)**
- **Language**: Vanilla JavaScript (ES6+).
- **3D Engine**: **Three.js** (WebGL).
- **Math & Physics**: Custom-built vector math for collision detection and autonomous pathing.
- **Styling**: Modern CSS3 with high-end glassmorphism, HSL-tailored colors, and Space Grotesk typography.
- **Storage**: `localStorage` and `sessionStorage` for cross-page persistence of real-time farm states.

### **Backend (The Infrastructure)**
- **Language**: Python 3.
- **Server**: Flask/HTTP server for handling REST API requests (saving sessions, serving files).
- **Communication**: **WebSockets** for real-time broadcasting of AI telemetry between the monitor and the browser.
- **AI Brain**: `monitor.py` (The Juggernaut) - A background agent that processes flock data using high-frequency polling.

---

## 🧠 3. Artificial Intelligence Deep-Dive

The AI in Chicken Twin operates on multiple layers:

### **A. Keypoint Monitoring (Vision)**
In the "AI View," the system generates a skeletal overlay for every bird.
- **Detection Particles**: 12 keypoints per bird (Beak, Head, Wing-tips, Feet, Tail).
- **Behavioral Synthesis**:
  - **Wing Droop**: Calculated by comparing wing-tip Z-height to body center.
  - **Limping**: Calculated by evaluating the gait cycle rhythm and step-length asymmetry.
  - **Lethargy**: Measured by stagnant coordinate changes over a sliding 10-second window.

### **B. Risk Scoring Algorithm**
Every bird has a dynamic `riskScore` (0.0 to 1.0).
- **Temperature Spike**: Any bird > 42°C increases risk by 0.3 instantly.
- **Isolation**: If a bird moves more than 5 meters away from the group, the `isolation` symptom increases.
- **Feces Analysis**: The AI detects trace particles (feces). 
  - **Red**: Bloody diarrhea (Immediate Critical / 1.0 Risk).
  - **Green/Watery**: Early infection signals (0.4 Risk).
---

## 🦾 4. Robotic State Machine (ROBO-SM)

The robotic arm follows a strict linear state sequence to ensure precision:

1.  **IDLE**: Robot hangs at (0,0,0) in a compact telescoped position.
2.  **MOVING_TO_CHICKEN**: Linear interpolation (Lerp) toward the target bird's X/Z coordinates.
3.  **EXTENDING_ARM**: Telescoping segments extend downward along the Y-axis.
4.  **INJECTING / PICKING_UP**:
    - If the bird is treatable, the syringe (needle mesh) becomes visible and applies a 0.3 reduction in disease.
    - If the bird is highly contagious, the "Secured" status is triggered.
5.  **RETRACTING_WITH_BIRD**: Arm pulls back, lifting the chicken mesh.
6.  **QUARANTINE_DROP**: Robot moves to the red boundary box and updates the bird's `inQuarantine` flag.

---

## 📊 5. Data Persistence & Real-time Sync

### **The Dashboard Loop**
1.  `demo.html` saves a snapshot of all bird positions, temperatures, and robot status into `localStorage` every 500ms.
2.  `dashboard.html` reads this snapshot and updates the Chart.js graphs.
3.  This ensures that when you switch tabs, the dashboard "instantly" knows exactly what the farm looks like without reloading data from the server.

### **Session Management**
- Every session is uniquely ID'd with a timestamp (e.g., `session_17382220...`).
- Full telemetry is serialized into JSON and saved to the `/sessions` folder.
- Replays use a "Playback Engine" that reconstructs the 3D scene from this historical JSON data.

---

## 🛡️ 6. The Brand Experience
Created by **Instaflect AI**, the project represents the pinnacle of "Physics-to-Insight" technology. Every particle, from the falling feces to the telescoping arm segments, is designed to provide a 1:1 digital representation of a functional robotic poultry farm.

