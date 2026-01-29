"""
CHICKEN TWIN - Robot AI Agent
Controls the robot behavior and interacts with OpenAI
"""

import os
import json
import time
import openai
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

class ChickenTwinRobot:
    def __init__(self):
        self.position = {'x': 0, 'y': 0, 'z': 0}
        self.carrying_chicken = None
        self.status = 'idle'
        self.quarantine_chickens = []
        self.quarantine_temp = 28.0
        self.movement_speed = 2.0
        
    def analyze_chicken(self, chicken_data):
        """Use AI to analyze a chicken's health status"""
        try:
            prompt = f"""
            Analyze this chicken's health data:
            
            Chicken ID: #{chicken_data.get('id')}
            Body Temperature: {chicken_data.get('temperature', 0):.2f}°C
            Current Status: {chicken_data.get('status', 'unknown')}
            
            Reference Values:
            - Normal body temp: 40.6°C - 41.7°C
            - Slight fever: 41.7°C - 42.5°C  
            - High fever: > 42.5°C
            - Hypothermia: < 39°C
            
            Provide analysis as JSON:
            {{
                "health_status": "healthy/warning/critical",
                "needs_quarantine": true/false,
                "urgency": 1-10,
                "diagnosis": "brief diagnosis",
                "treatment": "recommended action"
            }}
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a poultry veterinary AI. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.2
            )
            
            return json.loads(response.choices[0].message.content.strip())
            
        except Exception as e:
            print(f"AI Analysis Error: {e}")
            return {
                "health_status": "unknown",
                "needs_quarantine": chicken_data.get('temperature', 40) > 42 or chicken_data.get('temperature', 40) < 38,
                "urgency": 5,
                "diagnosis": "Manual check required",
                "treatment": "Isolate and monitor"
            }
    
    def calculate_quarantine_temp(self):
        """Calculate optimal quarantine room temperature based on chickens inside"""
        if not self.quarantine_chickens:
            return 28.0
            
        try:
            avg_body_temp = sum(c.get('temperature', 40) for c in self.quarantine_chickens) / len(self.quarantine_chickens)
            
            prompt = f"""
            Calculate optimal ROOM temperature for quarantine area.
            
            Number of sick chickens: {len(self.quarantine_chickens)}
            Average body temperature: {avg_body_temp:.1f}°C
            
            Consider:
            - Room temp should help normalize body temperature
            - Too cold worsens hypothermia
            - Too hot worsens fever
            - Comfortable range: 24-32°C
            
            Respond with just a number (the temperature in Celsius).
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a poultry care expert. Respond with just a number."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=10,
                temperature=0.1
            )
            
            temp = float(response.choices[0].message.content.strip())
            return max(20, min(35, temp))  # Clamp between 20-35°C
            
        except Exception as e:
            print(f"Temperature calculation error: {e}")
            return 28.0
    
    def move_to(self, target_x, target_z):
        """Move robot to target position"""
        self.status = 'moving'
        # In real implementation, this would control actual motors
        self.position['x'] = target_x
        self.position['z'] = target_z
        self.status = 'idle'
        
    def pickup_chicken(self, chicken):
        """Pick up a chicken"""
        self.status = 'picking_up'
        self.carrying_chicken = chicken
        self.status = 'carrying'
        
    def drop_chicken_in_quarantine(self):
        """Drop chicken in quarantine area"""
        if self.carrying_chicken:
            self.quarantine_chickens.append(self.carrying_chicken)
            self.carrying_chicken = None
            self.status = 'idle'
            # Recalculate quarantine temperature
            self.quarantine_temp = self.calculate_quarantine_temp()
            
    def get_status(self):
        """Get current robot status"""
        return {
            'position': self.position,
            'status': self.status,
            'carrying': self.carrying_chicken,
            'quarantine_count': len(self.quarantine_chickens),
            'quarantine_temp': self.quarantine_temp
        }


# For testing
if __name__ == '__main__':
    robot = ChickenTwinRobot()
    
    # Test chicken
    test_chicken = {
        'id': 1,
        'temperature': 43.5,
        'status': 'critical',
        'x': 10,
        'z': 15
    }
    
    print("Analyzing chicken...")
    analysis = robot.analyze_chicken(test_chicken)
    print(f"Analysis: {json.dumps(analysis, indent=2)}")
    
    if analysis.get('needs_quarantine'):
        print("\nChicken needs quarantine!")
        robot.pickup_chicken(test_chicken)
        robot.drop_chicken_in_quarantine()
        print(f"Robot status: {robot.get_status()}")