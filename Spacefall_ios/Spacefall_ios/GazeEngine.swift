import Foundation
import ARKit
import SceneKit
import CoreMotion

class GazeEngine: NSObject, ARSessionDelegate, ObservableObject {
    static let shared = GazeEngine()
    
    @Published var score: Int = 0
    @Published var hp: Int = 3
    @Published var maxHp: Int = 5 // User requested capacity up to 5
    
    @Published var fireAmmo: Int = 0
    @Published var fireAmmoMax: Int = 5 // Can be upgraded to 10, 15, 20
    @Published var weaponLevel: Int = 1 // Added for Phase 13
    @Published var fireRecoveryRate: Double = 1.0 // Decreased by 50% per upgrade
    @Published var temporaryWeaponAmmo: Int = 0
    @Published var jumpEnergy: Int = 5
    @Published var jumpEnergyMax: Int = 5
    @Published var rewardCharges: Int = 0
    @Published var isGameplayHUDVisible: Bool = false
    
    // Streak Trackers
    var rockCount: Int = 0 // Ep 1
    var checkpointStreak: Int = 0 // Ep 2
    var figureStreak: Int = 0 // Ep 3
    var carStreak: Int = 0 // Ep 6
    
    @Published var digsRemaining: Int = 6
    let totalTreasures: Int = 6
    @Published var bossHp: Int = 10
    @Published var bossMaxHp: Int = 10
    @Published var errorMessage: String? = nil
    
    private let session = ARSession()
    var lookAtPoint: CGPoint = .zero
    var laneIndex: Int = 0
    private let motionManager = CMMotionManager()
    var tiltY: CGFloat = 0.0
    var tiltX: CGFloat = 0.0
    private let numLanes = 8
    
    private var calibrationOffset: CGPoint = .zero
    
    // --- Advanced Smoothing (Double Exponential) ---
    private var lastObservedPoint: CGPoint = .zero
    private var trend: CGPoint = .zero
    private let alpha: CGFloat = 0.3 // Level smoothing
    private let beta: CGFloat = 0.1  // Trend smoothing
    
    func resetState(for episodeId: Int) {
        hp = 3
        maxHp = 3
        score = 0
        fireAmmo = 0
        fireAmmoMax = 5
        weaponLevel = 1
        fireRecoveryRate = 1.0
        temporaryWeaponAmmo = 0
        jumpEnergy = 5
        jumpEnergyMax = 5
        rewardCharges = 0
        isGameplayHUDVisible = false
        
        rockCount = 0
        checkpointStreak = 0
        figureStreak = 0
        carStreak = 0
        
        digsRemaining = 6
        bossHp = 10
        bossMaxHp = 10
        errorMessage = nil
        lookAtPoint = CGPoint(x: 0.5, y: 0.5)
        laneIndex = numLanes / 2
        tiltY = 0
        tiltX = 0
        // Clear smoothing buffers
        lastObservedPoint = .zero
        trend = .zero
    }
    
    override init() {
        super.init()
        session.delegate = self
    }

    private func runOnMain(_ work: @escaping () -> Void) {
        if Thread.isMainThread {
            work()
        } else {
            DispatchQueue.main.async(execute: work)
        }
    }
    
    func start() {
        guard ARFaceTrackingConfiguration.isSupported else {
            errorMessage = "ARFaceTracking is not supported on this device."
            return
        }
        errorMessage = nil
        let configuration = ARFaceTrackingConfiguration()
        session.run(configuration, options: [.resetTracking, .removeExistingAnchors])
        
        if motionManager.isDeviceMotionAvailable {
            motionManager.deviceMotionUpdateInterval = 1.0 / 60.0
            motionManager.startDeviceMotionUpdates(to: .main) { [weak self] motion, error in
                guard let motion = motion else { return }
                // Pitch: rotation around the side-to-side axis.
                let pitch = motion.attitude.pitch // Radians
                let neutralPitch: Double = 0.6 // More natural holding angle
                self?.tiltY = CGFloat(pitch - neutralPitch)
                
                let roll = motion.attitude.roll
                self?.tiltX = CGFloat(roll)
            }
        }
    }
    
    func stop() {
        session.pause()
        motionManager.stopDeviceMotionUpdates()
    }
    
    func session(_ session: ARSession, didFailWithError error: Error) {
        runOnMain { [weak self] in
            self?.errorMessage = error.localizedDescription
        }
    }
    
    func sessionWasInterrupted(_ session: ARSession) {
        runOnMain { [weak self] in
            self?.errorMessage = "AR Session Interrupted"
        }
    }
    
    func sessionInterruptionEnded(_ session: ARSession) {
        runOnMain { [weak self] in
            self?.errorMessage = nil
        }
    }
    
    func session(_ session: ARSession, didUpdate anchors: [ARAnchor]) {
        guard let faceAnchor = anchors.compactMap({ $0 as? ARFaceAnchor }).first else { return }

        runOnMain {
            GestureManager.shared.update(with: faceAnchor)

            let rawPoint = faceAnchor.lookAtPoint
            self.updateGaze(xAxis: 0.5 - CGFloat(rawPoint.x), yAxis: CGFloat(rawPoint.y) + 0.5)
        }
    }
    
    // --- Core Logic ---
    func updateGaze(xAxis: CGFloat, yAxis: CGFloat) {
        if !Thread.isMainThread {
            runOnMain { [weak self] in
                self?.updateGaze(xAxis: xAxis, yAxis: yAxis)
            }
            return
        }

        let clampedX = min(max(xAxis, 0), 1)
        let clampedY = min(max(yAxis, 0), 1)
        let newPoint = CGPoint(x: clampedX, y: clampedY)
        
        // Double Exponential Smoothing (Holt-Winters)
        if lastObservedPoint == .zero {
            lastObservedPoint = newPoint
            lookAtPoint = newPoint
        } else {
            let previousLevel = lookAtPoint
            let level = alpha * newPoint + (1 - alpha) * (previousLevel + trend)
            trend = beta * (level - previousLevel) + (1 - beta) * trend
            lookAtPoint = level
        }
        
        // Lane calculation with step-based limiting (Phase 17)
        let normalizedX = (lookAtPoint.x - 0.5) * 1.4 + 0.5
        let rawTargetLane = Int(normalizedX * CGFloat(numLanes))
        let clampedTarget = max(0, min(numLanes - 1, rawTargetLane))
        
        // Only allow switching 1 lane at a time
        if clampedTarget != laneIndex {
            let step = (clampedTarget > laneIndex) ? 1 : -1
            laneIndex += step
        }
    }
    
    func setCalibration(at screenTarget: CGPoint) {
        // Calibration logic removed as part of Phase 7 reversion
    }
    
    // --- High Score Persistence ---
    func saveHighScore(for episodeId: Int) {
        let currentHighScore = getHighScore(for: episodeId)
        if score > currentHighScore {
            UserDefaults.standard.set(score, forKey: "HighScore_Ep\(episodeId)")
        }
    }
    
    func getHighScore(for episodeId: Int) -> Int {
        return UserDefaults.standard.integer(forKey: "HighScore_Ep\(episodeId)")
    }
    
    func isNewRecord(for episodeId: Int) -> Bool {
        return score > getHighScore(for: episodeId)
    }
}

// --- Arithmetic Helpers ---
extension CGPoint {
    static func + (left: CGPoint, right: CGPoint) -> CGPoint {
        return CGPoint(x: left.x + right.x, y: left.y + right.y)
    }
    static func - (left: CGPoint, right: CGPoint) -> CGPoint {
        return CGPoint(x: left.x - right.x, y: left.y - right.y)
    }
    static func * (scalar: CGFloat, point: CGPoint) -> CGPoint {
        return CGPoint(x: scalar * point.x, y: scalar * point.y)
    }
}
