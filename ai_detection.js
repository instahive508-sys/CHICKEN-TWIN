// ═══════════════════════════════════════════════════════════════
// CHICKEN TWIN - AI Detection & Symptom Analysis Module
// ═══════════════════════════════════════════════════════════════

const AIDetection = {
    
    // ═══════════════════════════════════════════════════════════════
    // CONFIGURATION
    // ═══════════════════════════════════════════════════════════════
    config: {
        // Behavioral thresholds
        lethargy: {
            sittingTimeThreshold: 0.6,      // 60% of time sitting = lethargy
            movementThreshold: 0.3,          // Less than 30% movement = lethargy
            stepCountThreshold: 50           // Less than 50 steps/hour = reduced movement
        },
        
        isolation: {
            distanceThreshold: 3.0,          // 3+ meters from flock = isolation
            flockCenterThreshold: 5.0,       // 5+ meters from flock center
            durationThreshold: 300           // 5+ minutes = isolation confirmed
        },
        
        movement: {
            normalSpeed: 0.15,               // m/s normal walking speed
            slowSpeedThreshold: 0.05,        // Below this = slow movement
            erraticThreshold: 0.8,           // High variance = erratic
            stepsPerMinuteNormal: 15         // Normal steps per minute
        },
        
        posture: {
            normalWingAngle: 35,             // Degrees from body
            droopThreshold: 20,              // Below this = wing droop
            normalBodyTilt: 5,               // Normal tilt variance
            unstableTiltThreshold: 15        // Above this = unstable
        },
        
        temperature: {
            normalMin: 40.6,
            normalMax: 41.7,
            warningLow: 39.0,
            warningHigh: 42.5,
            criticalLow: 38.0,
            criticalHigh: 43.0
        },
        
        // Risk calculation weights
        weights: {
            lethargy: 0.20,
            reducedMovement: 0.15,
            isolation: 0.15,
            abnormalSleep: 0.10,
            limping: 0.15,
            wingDroop: 0.10,
            ruffledFeathers: 0.05,
            paleComb: 0.05,
            abnormalFeces: 0.05
        }
    },
    
    // ═══════════════════════════════════════════════════════════════
    // FLOCK STATISTICS (Updated each frame)
    // ═══════════════════════════════════════════════════════════════
    flockStats: {
        centerX: 0,
        centerZ: 0,
        avgMovementSpeed: 0,
        avgStepsPerMinute: 0,
        avgSittingTime: 0,
        avgTemperature: 0,
        stdDevMovement: 0,
        totalBirds: 0
    },
    
    // ═══════════════════════════════════════════════════════════════
    // HISTORICAL DATA (For trend analysis)
    // ═══════════════════════════════════════════════════════════════
    history: {},
    historyMaxLength: 1800, // 30 minutes at 1 sample/second
    
    // ═══════════════════════════════════════════════════════════════
    // INITIALIZE
    // ═══════════════════════════════════════════════════════════════
    init() {
        this.history = {};
        console.log('[AIDetection] Module initialized');
    },
    
    // ═══════════════════════════════════════════════════════════════
    // UPDATE FLOCK STATISTICS
    // ═══════════════════════════════════════════════════════════════
    updateFlockStats(chickens) {
        if (chickens.length === 0) return;
        
        const farmChickens = chickens.filter(c => !c.inQuarantine && !c.isBeingCarried);
        if (farmChickens.length === 0) return;
        
        // Calculate flock center
        let sumX = 0, sumZ = 0;
        farmChickens.forEach(c => {
            sumX += c.x;
            sumZ += c.z;
        });
        this.flockStats.centerX = sumX / farmChickens.length;
        this.flockStats.centerZ = sumZ / farmChickens.length;
        
        // Calculate averages
        const speeds = farmChickens.map(c => 
            Math.sqrt(c.velocityX * c.velocityX + c.velocityZ * c.velocityZ)
        );
        this.flockStats.avgMovementSpeed = speeds.reduce((a, b) => a + b, 0) / speeds.length;
        
        const steps = farmChickens.map(c => c.stepCount);
        this.flockStats.avgStepsPerMinute = steps.reduce((a, b) => a + b, 0) / steps.length;
        
        const sittingRatios = farmChickens.map(c => 
            c.sittingTime / Math.max(0.01, c.sittingTime + c.activeTime)
        );
        this.flockStats.avgSittingTime = sittingRatios.reduce((a, b) => a + b, 0) / sittingRatios.length;
        
        const temps = farmChickens.map(c => c.temperature);
        this.flockStats.avgTemperature = temps.reduce((a, b) => a + b, 0) / temps.length;
        
        // Calculate standard deviation of movement
        const mean = this.flockStats.avgMovementSpeed;
        const squaredDiffs = speeds.map(s => Math.pow(s - mean, 2));
        this.flockStats.stdDevMovement = Math.sqrt(
            squaredDiffs.reduce((a, b) => a + b, 0) / squaredDiffs.length
        );
        
        this.flockStats.totalBirds = farmChickens.length;
    },
    
    // ═══════════════════════════════════════════════════════════════
    // ANALYZE SINGLE CHICKEN
    // ═══════════════════════════════════════════════════════════════
    analyzeChicken(chicken, allChickens) {
        // Initialize history for this chicken
        if (!this.history[chicken.id]) {
            this.history[chicken.id] = {
                positions: [],
                temperatures: [],
                speeds: [],
                riskScores: [],
                symptoms: []
            };
        }
        
        const h = this.history[chicken.id];
        
        // Store current data
        h.positions.push({ x: chicken.x, z: chicken.z, t: Date.now() });
        h.temperatures.push({ v: chicken.temperature, t: Date.now() });
        h.speeds.push(Math.sqrt(chicken.velocityX ** 2 + chicken.velocityZ ** 2));
        
        // Trim history
        if (h.positions.length > this.historyMaxLength) h.positions.shift();
        if (h.temperatures.length > this.historyMaxLength) h.temperatures.shift();
        if (h.speeds.length > this.historyMaxLength) h.speeds.shift();
        
        // Perform symptom detection
        const symptoms = this.detectSymptoms(chicken, allChickens, h);
        
        // Calculate risk score
        const riskScore = this.calculateRiskScore(symptoms, chicken);
        
        // Store for trend analysis
        h.riskScores.push({ v: riskScore, t: Date.now() });
        if (h.riskScores.length > this.historyMaxLength) h.riskScores.shift();
        
        return {
            symptoms,
            riskScore,
            trends: this.analyzeTrends(h),
            recommendation: this.getRecommendation(riskScore, symptoms)
        };
    },
    
    // ═══════════════════════════════════════════════════════════════
    // DETECT ALL SYMPTOMS
    // ═══════════════════════════════════════════════════════════════
    detectSymptoms(chicken, allChickens, history) {
        const symptoms = {};
        
        // 1. Lethargy Detection
        symptoms.lethargy = this.detectLethargy(chicken, history);
        
        // 2. Reduced Movement Detection
        symptoms.reducedMovement = this.detectReducedMovement(chicken, history);
        
        // 3. Isolation Detection
        symptoms.isolation = this.detectIsolation(chicken, allChickens);
        
        // 4. Abnormal Sleep Detection
        symptoms.abnormalSleep = this.detectAbnormalSleep(chicken);
        
        // 5. Limping Detection
        symptoms.limping = this.detectLimping(chicken, history);
        
        // 6. Wing Droop Detection
        symptoms.wingDroop = this.detectWingDroop(chicken);
        
        // 7. Ruffled Feathers Detection (simulated via temperature/stress)
        symptoms.ruffledFeathers = this.detectRuffledFeathers(chicken);
        
        // 8. Pale Comb Detection (simulated via temperature)
        symptoms.paleComb = this.detectPaleComb(chicken);
        
        // 9. Abnormal Feces Detection (simulated randomly based on health)
        symptoms.abnormalFeces = this.detectAbnormalFeces(chicken);
        
        return symptoms;
    },
    
    // ═══════════════════════════════════════════════════════════════
    // INDIVIDUAL SYMPTOM DETECTORS
    // ═══════════════════════════════════════════════════════════════
    
    detectLethargy(chicken, history) {
        // Calculate sitting ratio
        const sittingRatio = chicken.sittingTime / 
            Math.max(0.01, chicken.sittingTime + chicken.activeTime);
        
        // Compare to flock average
        const flockAvg = this.flockStats.avgSittingTime;
        const deviation = sittingRatio - flockAvg;
        
        // Check if significantly more sitting than average
        let score = 0;
        
        if (sittingRatio > this.config.lethargy.sittingTimeThreshold) {
            score += 0.5;
        }
        
        if (deviation > 0.2) { // 20% more sitting than flock average
            score += 0.3;
        }
        
        // Check activity level
        if (chicken.activity === 'idle' || chicken.activity === 'sleeping') {
            score += 0.2;
        }
        
        return Math.min(1, score);
    },
    
    detectReducedMovement(chicken, history) {
        // Calculate average speed from history
        const recentSpeeds = history.speeds.slice(-60); // Last 60 samples
        if (recentSpeeds.length === 0) return 0;
        
        const avgSpeed = recentSpeeds.reduce((a, b) => a + b, 0) / recentSpeeds.length;
        
        // Compare to flock average
        const flockAvg = this.flockStats.avgMovementSpeed;
        
        let score = 0;
        
        // Below threshold speed
        if (avgSpeed < this.config.movement.slowSpeedThreshold) {
            score += 0.5;
        }
        
        // Significantly slower than flock
        if (flockAvg > 0 && avgSpeed < flockAvg * 0.5) {
            score += 0.3;
        }
        
        // Low step count
        if (chicken.stepCount < this.config.lethargy.stepCountThreshold) {
            score += 0.2;
        }
        
        return Math.min(1, score);
    },
    
    detectIsolation(chicken, allChickens) {
        if (chicken.inQuarantine) return 0;
        
        // Calculate distance to flock center
        const distToCenter = Math.sqrt(
            Math.pow(chicken.x - this.flockStats.centerX, 2) +
            Math.pow(chicken.z - this.flockStats.centerZ, 2)
        );
        
        // Find nearest neighbor distance
        let minNeighborDist = Infinity;
        allChickens.forEach(other => {
            if (other.id !== chicken.id && !other.inQuarantine) {
                const dist = Math.sqrt(
                    Math.pow(chicken.x - other.x, 2) +
                    Math.pow(chicken.z - other.z, 2)
                );
                if (dist < minNeighborDist) minNeighborDist = dist;
            }
        });
        
        let score = 0;
        
        // Far from flock center
        if (distToCenter > this.config.isolation.flockCenterThreshold) {
            score += 0.4;
        }
        
        // Far from nearest neighbor
        if (minNeighborDist > this.config.isolation.distanceThreshold) {
            score += 0.4;
        }
        
        // Very isolated
        if (minNeighborDist > this.config.isolation.distanceThreshold * 2) {
            score += 0.2;
        }
        
        return Math.min(1, score);
    },
    
    detectAbnormalSleep(chicken) {
        // Check if sleeping during active hours (simulated)
        const hour = new Date().getHours();
        const isActiveHours = hour >= 6 && hour <= 20;
        
        let score = 0;
        
        if (isActiveHours) {
            if (chicken.posture.headPosition === 'tucked') {
                score += 0.6;
            }
            if (chicken.activity === 'sleeping') {
                score += 0.4;
            }
        }
        
        return Math.min(1, score);
    },
    
    detectLimping(chicken, history) {
        // Analyze gait patterns from position history
        const recentPositions = history.positions.slice(-30);
        if (recentPositions.length < 10) return 0;
        
        // Calculate step lengths (simplified)
        let stepLengths = [];
        for (let i = 1; i < recentPositions.length; i++) {
            const dx = recentPositions[i].x - recentPositions[i-1].x;
            const dz = recentPositions[i].z - recentPositions[i-1].z;
            stepLengths.push(Math.sqrt(dx*dx + dz*dz));
        }
        
        // Calculate variance in step lengths
        if (stepLengths.length < 2) return 0;
        
        const mean = stepLengths.reduce((a, b) => a + b, 0) / stepLengths.length;
        const variance = stepLengths.reduce((sum, s) => sum + Math.pow(s - mean, 2), 0) / stepLengths.length;
        const stdDev = Math.sqrt(variance);
        
        // High variance indicates uneven gait
        let score = 0;
        
        if (stdDev > mean * 0.5) { // High variance
            score += 0.5;
        }
        
        // Check posture for leg issues
        if (chicken.posture.stance === 'unstable') {
            score += 0.3;
        }
        
        // Random component based on existing symptom
        if (chicken.symptoms && chicken.symptoms.limping > 0) {
            score += 0.2;
        }
        
        return Math.min(1, score);
    },
    
    detectWingDroop(chicken) {
        const leftAngle = chicken.posture.wingAngleLeft;
        const rightAngle = chicken.posture.wingAngleRight;
        const avgAngle = (leftAngle + rightAngle) / 2;
        
        let score = 0;
        
        // Wing angle below normal
        if (avgAngle < this.config.posture.droopThreshold) {
            score += 0.6;
        } else if (avgAngle < this.config.posture.normalWingAngle - 10) {
            score += 0.3;
        }
        
        // Asymmetric wings (one side drooping more)
        const asymmetry = Math.abs(leftAngle - rightAngle);
        if (asymmetry > 10) {
            score += 0.2;
        }
        
        return Math.min(1, score);
    },
    
    detectRuffledFeathers(chicken) {
        // Ruffled feathers correlate with fever or illness
        // Simulated based on temperature and stress
        
        let score = 0;
        
        // High temperature often causes ruffled feathers
        if (chicken.temperature > this.config.temperature.warningHigh) {
            score += 0.4;
        }
        
        // Low temperature (hypothermia) also causes it
        if (chicken.temperature < this.config.temperature.warningLow) {
            score += 0.4;
        }
        
        // Stress factor
        if (chicken.stressFactor > 0.3) {
            score += 0.2;
        }
        
        return Math.min(1, score);
    },
    
    detectPaleComb(chicken) {
        // Pale comb indicates circulation issues
        // Correlates with low temperature or illness
        
        let score = 0;
        
        // Hypothermia causes pale comb
        if (chicken.temperature < this.config.temperature.warningLow) {
            score += 0.5;
        }
        
        // Very low temperature - definitely pale
        if (chicken.temperature < this.config.temperature.criticalLow) {
            score += 0.3;
        }
        
        // Poor health factor
        if (chicken.healthFactor < 0.95) {
            score += 0.2;
        }
        
        return Math.min(1, score);
    },
    
    detectAbnormalFeces(chicken) {
        // Simulated based on health status and temperature
        
        let score = 0;
        
        // Temperature abnormalities often cause digestive issues
        if (chicken.temperature > this.config.temperature.criticalHigh ||
            chicken.temperature < this.config.temperature.criticalLow) {
            score += 0.4;
        }
        
        // Random chance based on overall health
        if (chicken.healthFactor < 0.95 && Math.random() < 0.3) {
            score += 0.3;
        }
        
        // Existing digestive symptom
        if (chicken.symptoms && chicken.symptoms.abnormalFeces > 0.2) {
            score += 0.3;
        }
        
        return Math.min(1, score);
    },
    
    // ═══════════════════════════════════════════════════════════════
    // CALCULATE RISK SCORE
    // ═══════════════════════════════════════════════════════════════
    calculateRiskScore(symptoms, chicken) {
        let totalRisk = 0;
        
        // Weighted sum of all symptoms
        for (const [symptom, value] of Object.entries(symptoms)) {
            const weight = this.config.weights[symptom] || 0;
            totalRisk += value * weight;
        }
        
        // Temperature contribution
        const temp = chicken.temperature;
        if (temp > this.config.temperature.criticalHigh || 
            temp < this.config.temperature.criticalLow) {
            totalRisk += 0.25;
        } else if (temp > this.config.temperature.warningHigh || 
                   temp < this.config.temperature.warningLow) {
            totalRisk += 0.12;
        }
        
        // Multiplier for multiple symptoms (synergy effect)
        const symptomCount = Object.values(symptoms).filter(v => v > 0.3).length;
        if (symptomCount >= 3) {
            totalRisk *= 1.2;
        } else if (symptomCount >= 5) {
            totalRisk *= 1.4;
        }
        
        return Math.max(0, Math.min(1, totalRisk));
    },
    
    // ═══════════════════════════════════════════════════════════════
    // ANALYZE TRENDS
    // ═══════════════════════════════════════════════════════════════
    analyzeTrends(history) {
        const trends = {
            temperature: 'stable',
            risk: 'stable',
            movement: 'stable'
        };
        
        // Temperature trend
        if (history.temperatures.length >= 10) {
            const recent = history.temperatures.slice(-10);
            const older = history.temperatures.slice(-20, -10);
            
            if (older.length > 0) {
                const recentAvg = recent.reduce((a, b) => a + b.v, 0) / recent.length;
                const olderAvg = older.reduce((a, b) => a + b.v, 0) / older.length;
                
                if (recentAvg > olderAvg + 0.3) {
                    trends.temperature = 'increasing';
                } else if (recentAvg < olderAvg - 0.3) {
                    trends.temperature = 'decreasing';
                }
            }
        }
        
        // Risk trend
        if (history.riskScores.length >= 10) {
            const recent = history.riskScores.slice(-10);
            const older = history.riskScores.slice(-20, -10);
            
            if (older.length > 0) {
                const recentAvg = recent.reduce((a, b) => a + b.v, 0) / recent.length;
                const olderAvg = older.reduce((a, b) => a + b.v, 0) / older.length;
                
                if (recentAvg > olderAvg + 0.05) {
                    trends.risk = 'worsening';
                } else if (recentAvg < olderAvg - 0.05) {
                    trends.risk = 'improving';
                }
            }
        }
        
        // Movement trend
        if (history.speeds.length >= 10) {
            const recent = history.speeds.slice(-10);
            const older = history.speeds.slice(-20, -10);
            
            if (older.length > 0) {
                const recentAvg = recent.reduce((a, b) => a + b, 0) / recent.length;
                const olderAvg = older.reduce((a, b) => a + b, 0) / older.length;
                
                if (recentAvg > olderAvg * 1.3) {
                    trends.movement = 'increasing';
                } else if (recentAvg < olderAvg * 0.7) {
                    trends.movement = 'decreasing';
                }
            }
        }
        
        return trends;
    },
    
    // ═══════════════════════════════════════════════════════════════
    // GET RECOMMENDATION
    // ═══════════════════════════════════════════════════════════════
    getRecommendation(riskScore, symptoms) {
        if (riskScore >= 0.8) {
            return {
                action: 'isolate',
                priority: 'critical',
                message: 'Immediate isolation required',
                details: this.getSymptomDetails(symptoms)
            };
        } else if (riskScore >= 0.6) {
            return {
                action: 'monitor_closely',
                priority: 'high',
                message: 'Close monitoring required',
                details: this.getSymptomDetails(symptoms)
            };
        } else if (riskScore >= 0.4) {
            return {
                action: 'monitor',
                priority: 'medium',
                message: 'Continue observation',
                details: this.getSymptomDetails(symptoms)
            };
        } else {
            return {
                action: 'none',
                priority: 'low',
                message: 'Bird appears healthy',
                details: []
            };
        }
    },
    
    getSymptomDetails(symptoms) {
        return Object.entries(symptoms)
            .filter(([_, value]) => value > 0.3)
            .map(([name, value]) => ({
                name: name.replace(/([A-Z])/g, ' $1').trim(),
                severity: value > 0.7 ? 'severe' : value > 0.5 ? 'moderate' : 'mild',
                confidence: Math.round(value * 100)
            }))
            .sort((a, b) => b.confidence - a.confidence);
    },
    
    // ═══════════════════════════════════════════════════════════════
    // GET FLOCK HEALTH SUMMARY
    // ═══════════════════════════════════════════════════════════════
    getFlockHealthSummary(chickens) {
        if (chickens.length === 0) {
            return { healthy: 0, monitoring: 0, elevated: 0, critical: 0, avgRisk: 0 };
        }
        
        const summary = {
            healthy: 0,
            monitoring: 0,
            elevated: 0,
            critical: 0,
            avgRisk: 0,
            commonSymptoms: {},
            hotspots: []
        };
        
        chickens.forEach(c => {
            if (c.riskScore < 0.4) summary.healthy++;
            else if (c.riskScore < 0.6) summary.monitoring++;
            else if (c.riskScore < 0.8) summary.elevated++;
            else summary.critical++;
            
            summary.avgRisk += c.riskScore;
            
            // Track common symptoms
            if (c.symptoms) {
                Object.entries(c.symptoms).forEach(([name, value]) => {
                    if (value > 0.3) {
                        summary.commonSymptoms[name] = (summary.commonSymptoms[name] || 0) + 1;
                    }
                });
            }
        });
        
        summary.avgRisk /= chickens.length;
        
        // Sort common symptoms
        summary.topSymptoms = Object.entries(summary.commonSymptoms)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5)
            .map(([name, count]) => ({ name, count, percentage: (count / chickens.length * 100).toFixed(1) }));
        
        return summary;
    }
};

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AIDetection;
}