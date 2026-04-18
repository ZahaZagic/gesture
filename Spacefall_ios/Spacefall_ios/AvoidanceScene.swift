import SpriteKit
import UIKit

class AvoidanceScene: BaseEpisodeScene {
    private var player: SKSpriteNode!
    private let numLanes = 8
    private var laneWidth: CGFloat = 0
    
    private var lastLaneIndex: Int = 0
    
    // Episode 1 Laser Ammo
    private var laserAmmo = 5 // Increased from 3
    private var lastReloadTime: TimeInterval = 0
    private var hasFiredLaser = false
    private var lastJumpTime: TimeInterval = 0
    private var isJumping = false
    private var isRecoveringFromFall = false
    private var lastLaneBlockTime: TimeInterval = 0
    private var blockedLane: Int? = nil
    
    private var checkpointCount = 0
    
    // Phase 8: Refinements
    private var asteroidsShot = 0
    private var speedMultiplier: Double = 1.0
    private var gameStartTime: TimeInterval = 0
    private var lastDifficultyCheck: TimeInterval = 0
    private var difficultyLevel = 1
    private var lastEp2BlinkState = false
    private var didSpawnFirstEp1Reward = false
    private var pendingEp1HeartRewards = 0
    private var nextEp1UpgradeRockTarget = 10
    private var nextEp1HeartRockTarget = 30
    private var nextEp1TemporaryWeaponRockTarget = 50
    private var nextEp1TemporaryWeaponLevel = 6
    private var temporaryEp1WeaponLevel = 0
    private var temporaryEp1WeaponShotsRemaining = 0
    
    private func fireLaser() {
        fireLaser(target: nil)
    }

    private func laserSpeedMultiplier() -> CGFloat {
        let bonusLevels = max(0, GazeEngine.shared.weaponLevel - 1)
        return 1.0 + CGFloat(bonusLevels) * 0.1
    }

    private func laserAssetName(for level: Int = GazeEngine.shared.weaponLevel) -> String {
        let upgradeLevel = max(0, level - 1)
        guard upgradeLevel > 0 else { return "ep1/laser.png" }
        let assetIndex = min(6, upgradeLevel)
        return textureName(from: ["ep1/laser\(assetIndex)", "ep1/laser\(assetIndex).png", "laser\(assetIndex)"], fallback: "ep1/laser.png")
    }

    private func activeEpisodeOneWeaponLevel() -> Int {
        if temporaryEp1WeaponLevel > 0 && temporaryEp1WeaponShotsRemaining > 0 {
            return temporaryEp1WeaponLevel
        }
        return GazeEngine.shared.weaponLevel
    }

    private func fireLaser(target: SKNode?, assetName: String? = nil, speedScale: CGFloat = 1.0, pierceCount: Int = 1) {
        guard config.id == 1 || config.id == 6 else { return }

        if config.id == 1 && GazeEngine.shared.weaponLevel < 3 {
            if laserAmmo <= 0 { return }
            laserAmmo -= 1
            GazeEngine.shared.fireAmmo = laserAmmo
        }

        let laser = SKSpriteNode(imageNamed: assetName ?? laserAssetName())
        laser.size = CGSize(width: 80, height: 12)
        laser.position = player.position
        laser.name = "laser"
        laser.zPosition = -1
        laser.userData = ["pierceRemaining": pierceCount]
        addChild(laser)

        if let target {
            let homingDuration: TimeInterval = 1.6
            let homingSpeed: CGFloat = 1280 * laserSpeedMultiplier() * speedScale
            let homingAction = SKAction.customAction(withDuration: homingDuration) { [weak target] node, elapsedTime in
                guard let laser = node as? SKSpriteNode else { return }

                let destination: CGPoint
                if let target, target.parent != nil {
                    destination = target.position
                } else {
                    destination = CGPoint(x: laser.position.x, y: laser.position.y + 200)
                }

                let dx = destination.x - laser.position.x
                let dy = destination.y - laser.position.y
                let distance = hypot(dx, dy)
                guard distance > 1 else { return }

                let step = min(distance, homingSpeed / 60.0)
                let nx = dx / distance
                let ny = dy / distance
                laser.position = CGPoint(x: laser.position.x + nx * step, y: laser.position.y + ny * step)
                laser.zRotation = atan2(dy, dx)
            }
            laser.run(.sequence([homingAction, .removeFromParent()]))
        } else {
            laser.zRotation = -.pi / 2
            let duration = 0.4 / Double(laserSpeedMultiplier() * speedScale)
            laser.run(.sequence([.moveBy(x: 0, y: 1000, duration: duration), .removeFromParent()]))
        }

        SoundManager.shared.playSFX("ep1/laser.wav")
    }
    
    private func setupLaneIndicators() {
        guard config.id == 6 else { return }
        for i in 1..<numLanes {
            let x = CGFloat(i) * laneWidth
            let line = SKShapeNode(rectOf: CGSize(width: 2, height: size.height))
            line.position = CGPoint(x: x, y: size.height / 2)
            line.fillColor = .white
            line.strokeColor = .clear
            line.alpha = 0.2
            line.zPosition = -2
            addChild(line)
        }
    }

    override func didMove(to view: SKView) {
        laneWidth = size.width / CGFloat(numLanes)
        lastLaneIndex = GazeEngine.shared.laneIndex
        super.didMove(to: view)
        setupPlayer()
        setupLaneIndicators()
        startSpawner()
        
        if config.id == 1 {
            syncWeaponStats()
            didSpawnFirstEp1Reward = false
            pendingEp1HeartRewards = 0
            nextEp1UpgradeRockTarget = 10
            nextEp1HeartRockTarget = 30
            nextEp1TemporaryWeaponRockTarget = 50
            nextEp1TemporaryWeaponLevel = 6
            temporaryEp1WeaponLevel = 0
            temporaryEp1WeaponShotsRemaining = 0
            GazeEngine.shared.temporaryWeaponAmmo = 0
        } else if config.id == 2 {
            GazeEngine.shared.jumpEnergy = 5
            GazeEngine.shared.jumpEnergyMax = 5
        }
    }

    override func startGameplay() {
        super.startGameplay()
        if config.id == 1 {
            SoundManager.shared.playSFX("ep1/spaceship.wav")
        }
    }
    
    private func setupPlayer() {
        player = SKSpriteNode(imageNamed: config.playerAsset)
        player.size = CGSize(width: laneWidth * 0.8, height: laneWidth * 0.8)
        player.position = CGPoint(x: size.width / 2, y: 100)
        if config.id == 1 || config.id == 6 {
            player.zRotation = .pi // Rotate 180 degrees
        }
        addChild(player)
    }

    private func syncWeaponStats() {
        switch GazeEngine.shared.weaponLevel {
        case 1:
            GazeEngine.shared.fireAmmoMax = 10
            GazeEngine.shared.fireRecoveryRate = 2.0
            laserAmmo = min(max(laserAmmo, 0), 10)
        case 2:
            GazeEngine.shared.fireAmmoMax = 20
            GazeEngine.shared.fireRecoveryRate = 1.0
            laserAmmo = min(max(laserAmmo, 0), 20)
        default:
            GazeEngine.shared.fireAmmoMax = 999
            GazeEngine.shared.fireRecoveryRate = 0.0
            laserAmmo = 999
        }

        GazeEngine.shared.fireAmmo = laserAmmo
    }

    private func nearestAsteroidTargets(limit: Int) -> [SKNode] {
        var targets: [(node: SKNode, score: CGFloat)] = []
        enumerateChildNodes(withName: "enemy") { node, _ in
            let verticalDistance = node.position.y - self.player.position.y
            guard verticalDistance > 40 else { return }
            let horizontalPenalty = abs(node.position.x - self.player.position.x) * 0.2
            targets.append((node, verticalDistance + horizontalPenalty))
        }
        return targets.sorted { $0.score < $1.score }.prefix(limit).map(\.node)
    }

    private func asteroidsAheadInCurrentLane(limit: Int) -> [SKNode] {
        var targets: [(node: SKNode, y: CGFloat)] = []
        enumerateChildNodes(withName: "enemy") { node, _ in
            guard node.position.y > self.player.position.y + 35,
                  abs(node.position.x - self.player.position.x) <= self.laneWidth * 0.62 else { return }
            targets.append((node, node.position.y))
        }
        return targets.sorted { $0.y < $1.y }.prefix(limit).map(\.node)
    }

    private func asteroidsAheadForZigzag(limit: Int) -> [SKNode] {
        var targets: [(node: SKNode, y: CGFloat)] = []
        enumerateChildNodes(withName: "enemy") { node, _ in
            guard node.position.y > self.player.position.y + 35 else { return }
            targets.append((node, node.position.y))
        }
        return targets.sorted { $0.y < $1.y }.prefix(limit).map(\.node)
    }

    private func combinedSpiralDispersionTargets(limit: Int) -> [SKNode] {
        var seen = Set<ObjectIdentifier>()
        var targets: [SKNode] = []
        for node in asteroidsAheadInCurrentLane(limit: limit) + nearestAsteroidTargets(limit: limit * 2) {
            let id = ObjectIdentifier(node)
            guard !seen.contains(id) else { continue }
            seen.insert(id)
            targets.append(node)
            if targets.count >= limit { break }
        }
        return targets
    }

    private func fireEp1SpiralVolley() {
        let asset = laserAssetName(for: 6)
        let dispersionTargets = combinedSpiralDispersionTargets(limit: 5)
        let spiralDuration: CGFloat = 0.3
        let totalDuration: TimeInterval = 0.95
        let frequency: CGFloat = 18.0
        let baseAmplitude: CGFloat = laneWidth * 0.46
        let centerStart = player.position
        let centerEnd = CGPoint(x: player.position.x, y: min(size.height * 0.46, player.position.y + 260))

        for index in 0..<5 {
            let laser = SKSpriteNode(imageNamed: asset)
            laser.size = CGSize(width: 78, height: 12)
            laser.position = player.position
            laser.name = "laser"
            laser.zPosition = -1
            laser.userData = ["pierceRemaining": 12]
            addChild(laser)

            let phase = CGFloat(index) * (.pi * 2 / 5)
            let targetNode = index < dispersionTargets.count ? dispersionTargets[index] : nil
            let fallbackEnd = CGPoint(
                x: centerStart.x + (CGFloat(index) - 2.0) * laneWidth * 0.42,
                y: size.height + 260
            )

            let dispersionDuration = max(0.1, CGFloat(totalDuration) - spiralDuration)
            let action = SKAction.customAction(withDuration: totalDuration) { node, elapsed in
                guard let laser = node as? SKSpriteNode else { return }
                let t = CGFloat(elapsed)
                if t <= spiralDuration {
                    let progress = t / spiralDuration
                    let axis = CGPoint(
                        x: centerStart.x + (centerEnd.x - centerStart.x) * progress,
                        y: centerStart.y + (centerEnd.y - centerStart.y) * progress
                    )
                    let offset = sin(t * frequency + phase) * baseAmplitude
                    let yOffset = cos(t * frequency + phase) * baseAmplitude * 0.55
                    laser.position = CGPoint(x: axis.x + offset, y: axis.y + yOffset)
                    laser.zRotation = atan2(centerEnd.y - centerStart.y, centerEnd.x - centerStart.x) + sin(t * frequency + phase) * 0.35
                } else {
                    let dispersionProgress = min(1, (t - spiralDuration) / dispersionDuration)
                    let start = CGPoint(
                        x: centerEnd.x + sin(spiralDuration * frequency + phase) * baseAmplitude,
                        y: centerEnd.y + cos(spiralDuration * frequency + phase) * baseAmplitude * 0.55
                    )
                    let liveTarget = (targetNode?.parent != nil) ? targetNode!.position : fallbackEnd
                    let easedProgress = 1 - pow(1 - dispersionProgress, 3)
                    laser.position = CGPoint(
                        x: start.x + (liveTarget.x - start.x) * easedProgress,
                        y: start.y + (liveTarget.y - start.y) * easedProgress
                    )
                    let dx = liveTarget.x - laser.position.x
                    let dy = liveTarget.y - laser.position.y
                    laser.zRotation = atan2(dy, dx)
                }
            }
            laser.run(.sequence([action, .removeFromParent()]))
        }
        SoundManager.shared.playSFX("ep1/laser.wav")
    }

    private func fireEp1ZigzagPiercer() {
        let targets = asteroidsAheadForZigzag(limit: 10)
        if targets.isEmpty {
            fireLaser(target: nil, assetName: laserAssetName(for: 7), speedScale: 2.8, pierceCount: 10)
            return
        }

        let laser = SKSpriteNode(imageNamed: laserAssetName(for: 7))
        laser.size = CGSize(width: 84, height: 12)
        laser.position = player.position
        laser.name = "laser"
        laser.zPosition = -1
        laser.userData = ["pierceRemaining": 10]
        addChild(laser)

        let segmentDuration: CGFloat = 0.08
        let totalDuration = TimeInterval(segmentDuration * CGFloat(targets.count))
        let startPosition = player.position
        let action = SKAction.customAction(withDuration: totalDuration) { node, elapsed in
            guard let laser = node as? SKSpriteNode else { return }
            let t = CGFloat(elapsed)
            let rawSegment = min(CGFloat(targets.count) - 0.001, t / segmentDuration)
            let segmentIndex = max(0, min(targets.count - 1, Int(rawSegment)))
            let localProgress = rawSegment - CGFloat(segmentIndex)
            let from = segmentIndex == 0 ? startPosition : targets[segmentIndex - 1].position
            let to = targets[segmentIndex].position
            let zigzag = sin(localProgress * .pi) * 12 * (segmentIndex.isMultiple(of: 2) ? 1 : -1)
            let dx = to.x - from.x
            let dy = to.y - from.y
            let distance = max(1, hypot(dx, dy))
            let perpendicular = CGPoint(x: -dy / distance, y: dx / distance)
            laser.position = CGPoint(
                x: from.x + dx * localProgress + perpendicular.x * zigzag,
                y: from.y + dy * localProgress + perpendicular.y * zigzag
            )
            laser.zRotation = atan2(dy, dx)
        }
        laser.run(.sequence([action, .removeFromParent()]))
        SoundManager.shared.playSFX("ep1/laser.wav")
    }

    private func fireEpisodeOneWeapon() {
        let level = activeEpisodeOneWeaponLevel()
        if level >= 7 {
            fireEp1ZigzagPiercer()
        } else if level >= 6 {
            fireEp1SpiralVolley()
        } else if level >= 5 {
            let targets = nearestAsteroidTargets(limit: 3)
            if targets.isEmpty {
                fireLaser()
            } else {
                for target in targets {
                    fireLaser(target: target)
                }
            }
        } else if level >= 4 {
            fireLaser(target: nearestAsteroidTargets(limit: 1).first)
        } else {
            fireLaser()
        }

        if temporaryEp1WeaponLevel > 0 && temporaryEp1WeaponShotsRemaining > 0 {
            temporaryEp1WeaponShotsRemaining -= 1
            GazeEngine.shared.temporaryWeaponAmmo = temporaryEp1WeaponShotsRemaining
            if temporaryEp1WeaponShotsRemaining == 0 {
                temporaryEp1WeaponLevel = 0
            }
        }
    }

    private func hasActiveEp1Reward(type: String) -> Bool {
        var hasReward = false
        enumerateChildNodes(withName: "reward") { node, stop in
            if node.userData?["type"] as? String == type {
                hasReward = true
                stop.pointee = true
            }
        }
        return hasReward
    }

    private func spawnOrQueueEp1Reward(type: String, at position: CGPoint) {
        if type == "heart" && GazeEngine.shared.hp >= GazeEngine.shared.maxHp {
            pendingEp1HeartRewards += 1
            return
        }
        spawnPersistentReward(type: type, at: position)
    }

    private func spawnEp1TemporaryWeaponReward(level: Int, at position: CGPoint) {
        let reward = SKShapeNode(circleOfRadius: 25)
        reward.fillColor = UIColor.cosmicPrimary
        reward.strokeColor = .white
        reward.lineWidth = 2
        reward.position = position
        reward.name = "reward"
        reward.userData = ["type": "temporaryUpgrade", "weaponLevel": level]
        reward.zPosition = 200
        addChild(reward)

        let label = SKLabelNode(fontNamed: "AvenirNext-Bold")
        label.text = "⚡"
        label.fontSize = 24
        label.verticalAlignmentMode = .center
        reward.addChild(label)

        let move = SKAction.moveBy(x: 0, y: -size.height - 400, duration: 6.0)
        reward.run(.repeatForever(move))
    }

    private func releasePendingEp1HeartRewardIfNeeded() {
        guard config.id == 1,
              pendingEp1HeartRewards > 0,
              GazeEngine.shared.hp < GazeEngine.shared.maxHp,
              !hasActiveEp1Reward(type: "heart") else { return }
        pendingEp1HeartRewards -= 1
        spawnPersistentReward(type: "heart", at: CGPoint(x: player.position.x, y: size.height + 100))
    }

    private func nextEp1UpgradeIncrement(after level: Int) -> Int {
        return level >= 5 ? 50 : 10
    }

    private func activateTemporaryEp1Weapon(level: Int, currentTime: TimeInterval) {
        temporaryEp1WeaponLevel = level
        temporaryEp1WeaponShotsRemaining = 10
        GazeEngine.shared.temporaryWeaponAmmo = temporaryEp1WeaponShotsRemaining
        createExplosion(at: player.position, color: .cosmicPrimary)
    }

    private func textureName(from candidates: [String], fallback: String) -> String {
        for candidate in candidates where UIImage(named: candidate) != nil {
            return candidate
        }
        return fallback
    }

    private func ep2StandingTexture(for dx: CGFloat) -> String {
        if abs(dx) < 5 {
            return config.playerAsset
        } else if dx > 0 {
            return textureName(from: ["ep2/player right", "ep2/player_right", "ep2/right"], fallback: "ep2/player right")
        } else {
            return textureName(from: ["ep2/player left", "ep2/player_left", "ep2/left"], fallback: "ep2/player left")
        }
    }

    private func performEp2Jump(currentTime: TimeInterval) {
        guard !isJumping, !isRecoveringFromFall, currentTime - lastJumpTime > 0.55 else { return }
        guard GazeEngine.shared.jumpEnergy > 0 else { return }

        GazeEngine.shared.jumpEnergy -= 1
        isJumping = true
        lastJumpTime = currentTime

        let jumpTexture = textureName(from: ["ep2/player jump", "ep2/player_jump", "ep2/jump"], fallback: config.playerAsset)
        player.texture = SKTexture(imageNamed: jumpTexture)

        let jumpUp = SKAction.moveBy(x: 0, y: 34, duration: 0.12)
        jumpUp.timingMode = .easeOut
        let jumpDown = SKAction.moveBy(x: 0, y: -34, duration: 0.16)
        jumpDown.timingMode = .easeIn
        player.run(.sequence([
            jumpUp,
            jumpDown,
            .run { [weak self] in
                guard let self else { return }
                self.isJumping = false
                self.player.texture = SKTexture(imageNamed: self.config.playerAsset)
            }
        ]), withKey: "ep2Jump")
    }

    private func handleEp2Crash() {
        guard !isRecoveringFromFall else { return }
        isRecoveringFromFall = true
        takeDamage()

        let fallTexture = textureName(from: ["ep2/player fall", "ep2/player_fall", "ep2/fall"], fallback: config.playerAsset)

        player.removeAction(forKey: "ep2Jump")
        player.texture = SKTexture(imageNamed: fallTexture)
        player.run(.sequence([
            .rotate(toAngle: -.pi * 0.45, duration: 0.08),
            .wait(forDuration: 0.08),
            .rotate(toAngle: 0, duration: 0.08),
            .run { [weak self] in
                guard let self else { return }
                self.player.texture = SKTexture(imageNamed: self.config.playerAsset)
                self.isRecoveringFromFall = false
                self.isJumping = false
            }
        ]), withKey: "ep2Recover")
    }
    
    private func startSpawner() {
        let spawn = SKAction.run { [weak self] in
            if self?.config.id == 2 {
                if Double.random(in: 0...1) < 0.3 {
                    self?.spawnGate()
                } else {
                    self?.spawnObstacle()
                }
            } else {
                self?.spawnObstacle()
            }
        }
        let wait = SKAction.wait(forDuration: 1.0)
        run(.repeatForever(.sequence([spawn, wait])))
    }
    
    private func spawnGate() {
        if isNarrativeActive { return }
        let lane = Int.random(in: 0..<numLanes)
        let gate = SKSpriteNode(imageNamed: "ep2/gate.png")
        gate.size = CGSize(width: laneWidth * 1.0, height: 40)
        gate.position = CGPoint(x: CGFloat(lane) * laneWidth + laneWidth/2, y: size.height + 100)
        gate.name = "gate"
        addChild(gate)
        
        let duration = max(1.2, (4.0 - Double(score) / 500.0) / speedMultiplier)
        let move = SKAction.moveTo(y: -200, duration: duration)
        gate.run(.sequence([move, .removeFromParent()]))
    }
    
    private func setupHUD() {
        // Ep 1 HUD is now handled in MainMenuView.swift (SwiftUI)
    }
    
    private func spawnObstacle() {
        if isNarrativeActive { return }
        
        let lanesToSpawn = min(difficultyLevel, numLanes - 1)
        var usedLanes = Set<Int>()
        
        for i in 0..<lanesToSpawn {
            var lane = Int.random(in: 0..<numLanes)
            while usedLanes.contains(lane) || lane == blockedLane { 
                lane = Int.random(in: 0..<numLanes) 
            }
            usedLanes.insert(lane)
            
            let isEp2 = config.id == 2
            let isEp1 = config.id == 1
            
            var asset = ""
            var isSatellite = false
            
            if isEp1 {
                if Double.random(in: 0...1) < 0.12 {
                    asset = "ep1/satellite"
                    isSatellite = true
                } else {
                    let variations = ["", "1", "2", "3", "4"]
                    asset = "ep1/asteroid\(variations.randomElement()!)"
                }
            } else if isEp2 {
                let variations = ["", "1", "2", "3", "4"]
                asset = "ep2/ice\(variations.randomElement()!)"
            } else {
                asset = config.obstacleAsset
            }
            
            let obstacle = SKSpriteNode(imageNamed: asset)
            if isSatellite {
                obstacle.size = CGSize(width: laneWidth * 2.0, height: laneWidth * 1.0) // Even larger and wider
            } else {
                obstacle.size = CGSize(width: laneWidth * 0.82, height: laneWidth * 0.82)
            }
            obstacle.position = CGPoint(x: CGFloat(lane) * laneWidth + laneWidth/2, y: size.height + 100)
            obstacle.name = isSatellite ? "indestructible" : "enemy"
            obstacle.userData = ["isSatellite": isSatellite]
            addChild(obstacle)
            
            // Acceleration Duration Math (Slightly slower than last iteration)
            let baseDur: Double = isEp2 ? 4.2 : 5.8
            let minDur: Double = 1.5
            let ramp = Double(score) / 150.0 
            let duration = max(minDur, (baseDur - ramp) / speedMultiplier)
            
            let move = SKAction.moveTo(y: -200, duration: duration)
            
            // Stagger multiple obstacles in time
            let delay = Double(i) * 0.2
            let spawnAction = SKAction.run {
                obstacle.run(.sequence([move, .removeFromParent()]))
            }
            run(.sequence([.wait(forDuration: delay), spawnAction]))
        }

    }
    
    override func update(_ currentTime: TimeInterval) {
        super.update(currentTime)
        if isNarrativeActive { return }

        if config.id == 2 && gameStartTime == 0 && speedMultiplier == 1.0 {
            speedMultiplier = 1.35
        }
        if config.id == 1 {
            syncWeaponStats()
            releasePendingEp1HeartRewardIfNeeded()
            if temporaryEp1WeaponLevel > 0 && temporaryEp1WeaponShotsRemaining <= 0 {
                temporaryEp1WeaponLevel = 0
                GazeEngine.shared.temporaryWeaponAmmo = 0
            }
        }
        
        // Update player position
        let currentLane = GazeEngine.shared.laneIndex
        if config.id == 2 && currentLane != lastLaneIndex {
            lastLaneIndex = currentLane
        }
        
        let normalizedGazeX = (GazeEngine.shared.lookAtPoint.x - 0.5) * 1.4 + 0.5
        let clampedGazeX = min(max(normalizedGazeX, 0), 1)
        let horizontalInset = laneWidth / 2
        let targetX = horizontalInset + clampedGazeX * (size.width - horizontalInset * 2)
        let dx = targetX - player.position.x
        
        if config.id == 2 && !isJumping && !isRecoveringFromFall {
            player.texture = SKTexture(imageNamed: ep2StandingTexture(for: dx))
        }
        
        player.position.x += dx * 0.24
        
        // Difficulty Scaling (Consolidated)
        if gameStartTime == 0 { gameStartTime = currentTime }
        let elapsed = currentTime - gameStartTime
        let scalingInterval: TimeInterval = (config.id == 1) ? 30.0 : 20.0
        if elapsed - lastDifficultyCheck > scalingInterval {
            difficultyLevel += 1
            let scaling: Double = 1.1
            speedMultiplier *= scaling 
            lastDifficultyCheck = elapsed
        }
        
        // Double-Blink Laser (Ep 1, 6)
        if (config.id == 1 || config.id == 6) {
            // Reload Logic (Ep 1 only)
            let reloadRate = GazeEngine.shared.fireRecoveryRate
            if config.id == 1 && GazeEngine.shared.weaponLevel < 3 && laserAmmo < GazeEngine.shared.fireAmmoMax && currentTime - lastReloadTime > reloadRate {
                laserAmmo += 1
                lastReloadTime = currentTime
                GazeEngine.shared.fireAmmo = laserAmmo
            }
            
            let isBlinking = GestureManager.shared.isDoubleBlinking()
            if isBlinking && !hasFiredLaser {
                if config.id == 1 {
                    fireEpisodeOneWeapon()
                } else {
                    fireLaser()
                }
                hasFiredLaser = true
            } else if !isBlinking {
                hasFiredLaser = false
            }
        }
        
        if config.id == 2 {
            let currentBlinkState = GestureManager.shared.isSingleBlink() || GestureManager.shared.isDoubleBlinking()
            let didStartBlink = currentBlinkState && !lastEp2BlinkState
            lastEp2BlinkState = currentBlinkState
            if didStartBlink {
                performEp2Jump(currentTime: currentTime)
            }

            // Active Checkpoint Logic (Ep 2)
            enumerateChildNodes(withName: "gate") { gate, _ in
                if self.player.intersects(gate) {
                    gate.name = "gate_checked" // Avoid double counting
                    self.checkpointCount += 1
                    self.score = self.checkpointCount * 10
                    GazeEngine.shared.jumpEnergy = min(GazeEngine.shared.jumpEnergyMax, GazeEngine.shared.jumpEnergy + 5)
                    SoundManager.shared.playSFX("ep2/bonus")
                    
                    if self.checkpointCount % 5 == 0 {
                        self.spawnPersistentReward(type: "heart", at: CGPoint(x: gate.position.x, y: self.size.height + 150))
                    }
                    
                    gate.run(.fadeOut(withDuration: 0.2))
                }
            }
            
        }
        
        // Laser vs Enemy/Indestructible Collision
        enumerateChildNodes(withName: "laser") { laser, _ in
            self.enumerateChildNodes(withName: "*") { node, _ in
                guard node.name == "enemy" || node.name == "indestructible" else { return }
                
                if laser.intersects(node) {
                    if node.name == "enemy" {
                        // Ep 1: Black debris for rock destruction
                        self.createExplosion(at: node.position, color: .black)
                        let remainingPierce = laser.userData?["pierceRemaining"] as? Int ?? 1
                        if remainingPierce > 1 {
                            laser.userData?["pierceRemaining"] = remainingPierce - 1
                        } else {
                            laser.removeFromParent()
                        }
                        node.removeFromParent()
                        self.score += 20
                        
                        if self.config.id == 1 && self.activeEpisodeOneWeaponLevel() <= 5 {
                            GazeEngine.shared.rockCount += 1

                            if GazeEngine.shared.weaponLevel < 5,
                               GazeEngine.shared.rockCount >= self.nextEp1UpgradeRockTarget,
                               !self.hasActiveEp1Reward(type: "upgrade") {
                                let shouldPrioritizeHeart = self.didSpawnFirstEp1Reward && GazeEngine.shared.hp < 3
                                if shouldPrioritizeHeart {
                                    if !self.hasActiveEp1Reward(type: "heart") {
                                        self.spawnOrQueueEp1Reward(type: "heart", at: CGPoint(x: node.position.x, y: self.size.height + 100))
                                    }
                                } else {
                                    self.didSpawnFirstEp1Reward = true
                                    self.spawnOrQueueEp1Reward(type: "upgrade", at: CGPoint(x: node.position.x, y: self.size.height + 100))
                                }
                            }

                            if GazeEngine.shared.weaponLevel >= 4,
                               GazeEngine.shared.rockCount >= self.nextEp1HeartRockTarget,
                               !self.hasActiveEp1Reward(type: "heart") {
                                self.nextEp1HeartRockTarget += 30
                                self.spawnOrQueueEp1Reward(type: "heart", at: CGPoint(x: node.position.x, y: self.size.height + 100))
                            }

                            if GazeEngine.shared.weaponLevel >= 5,
                               GazeEngine.shared.rockCount >= self.nextEp1TemporaryWeaponRockTarget {
                                self.nextEp1TemporaryWeaponRockTarget += 50
                                if !self.hasActiveEp1Reward(type: "temporaryUpgrade") {
                                    self.spawnEp1TemporaryWeaponReward(
                                        level: self.nextEp1TemporaryWeaponLevel,
                                        at: CGPoint(x: node.position.x, y: self.size.height + 100)
                                    )
                                    self.nextEp1TemporaryWeaponLevel = self.nextEp1TemporaryWeaponLevel == 6 ? 7 : 6
                                }
                            }
                        }
                        
                        // Ep 6: 10-Car Streak
                        if self.config.id == 6 {
                            GazeEngine.shared.carStreak += 1
                            if GazeEngine.shared.carStreak % 10 == 0 {
                                let rewardType = Bool.random() ? "heart" : "barrier"
                                self.spawnPersistentReward(type: rewardType, at: CGPoint(x: node.position.x, y: self.size.height + 100))
                            }
                        }
                    } else {
                        // Indestructible: Laser stops, Yellow debris (scratch)
                        self.createExplosion(at: laser.position, color: .yellow)
                        laser.removeAllActions()
                        laser.removeFromParent()
                    }
                }
            }
        }
        
        // Player Collision
        enumerateChildNodes(withName: "*") { node, _ in
            if node.name == "enemy" || node.name == "indestructible" {
                if self.player.intersects(node) {
                    if self.config.id == 2 {
                        if self.isJumping {
                            self.createExplosion(at: node.position, color: .white)
                            node.removeFromParent()
                            self.score += 5
                            return
                        }
                        self.createExplosion(at: node.position, color: .red)
                        node.removeFromParent()
                        self.handleEp2Crash()
                    } else {
                        let explosionColor: UIColor = (self.config.id == 1 && node.name == "enemy") ? .yellow : .red
                        self.createExplosion(at: node.position, color: explosionColor)
                        node.removeFromParent()
                        self.takeDamage()
                    }
                }
            } else if node.name == "reward" {
                if self.player.intersects(node) {
                    let type = node.userData?["type"] as? String ?? ""
                    let temporaryWeaponLevel = node.userData?["weaponLevel"] as? Int
                    node.removeFromParent()
                    if type == "barrier" {
                        self.applyLaneBarrier()
                    } else if type == "temporaryUpgrade", let temporaryWeaponLevel {
                        self.activateTemporaryEp1Weapon(level: temporaryWeaponLevel, currentTime: CACurrentMediaTime())
                    } else {
                        self.applyReward(type: type)
                    }
                }
            } else if node.name == "gate" {
                if self.player.intersects(node) {
                    node.removeFromParent()
                    if self.config.id == 2 {
                        self.checkpointCount += 1
                        self.score = self.checkpointCount * 10
                    } else {
                        self.score += 50
                    }
                    SoundManager.shared.playSFX("ep2/ski_carve.wav")
                }
            }
        }
    }
    
    private func winLevel() {
        guard isGameplayActive else { return }
        completeEpisode(message: NSLocalizedString("LEVEL_COMPLETE", comment: ""), quitDelay: 3.0)
    }
    
    private func applyLaneBarrier() {
        self.blockedLane = Int.random(in: 0..<numLanes)
        self.lastLaneBlockTime = CACurrentMediaTime()
        SoundManager.shared.playSFX("ep6/sfx")
    }
    
    // Override applyReward to handle weaponLevel
    override func applyReward(type: String) {
        if type == "upgrade" {
            GazeEngine.shared.weaponLevel = min(5, GazeEngine.shared.weaponLevel + 1)
            nextEp1UpgradeRockTarget = GazeEngine.shared.rockCount + nextEp1UpgradeIncrement(after: GazeEngine.shared.weaponLevel)
            if GazeEngine.shared.weaponLevel >= 4 {
                nextEp1HeartRockTarget = max(nextEp1HeartRockTarget, GazeEngine.shared.rockCount + 30)
            }
            if GazeEngine.shared.weaponLevel >= 5 {
                nextEp1TemporaryWeaponRockTarget = GazeEngine.shared.rockCount + 50
            }
            syncWeaponStats()
            createExplosion(at: eyeIndicator.position, color: .cosmicPrimary)
        } else {
            super.applyReward(type: type)
        }
    }
}
