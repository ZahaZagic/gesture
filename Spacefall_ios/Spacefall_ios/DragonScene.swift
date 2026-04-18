import SpriteKit

class DragonScene: BaseEpisodeScene {
    private var dragon: SKSpriteNode!
    private let numLanes = 8
    private var laneWidth: CGFloat = 0
    private var dragonVelocityX: CGFloat = 0
    
    private var boss: SKSpriteNode!
    private var fishCollected = 0
    private var hasFiredJaw = false
    private var bossHearts: [SKNode] = []
    private var bossHeartContainer: SKNode!
    private var bossTargetPoint: CGPoint = .zero
    private var lastBossRetargetTime: TimeInterval = 0
    private var bossMotionStartTime: TimeInterval = 0
    private var followModeUntil: TimeInterval = 0
    private var lastBossHpSnapshot: Int = 0
    private var bossAttackCount = 0
    
    private var currentBossIndex = 1
    private let bossHps = [0, 5, 7, 10] // Index 1, 2, 3
    
    override func didMove(to view: SKView) {
        laneWidth = size.width / CGFloat(numLanes)
        super.didMove(to: view)
        GazeEngine.shared.fireAmmo = 3
        setupDragon()
        setupBoss()
        startSpawner()
        startBossShooting()
    }
    
    private func setupDragon() {
        dragon = SKSpriteNode(imageNamed: config.playerAsset)
        dragon.size = CGSize(width: laneWidth * 2.2, height: laneWidth * 1.5)
        dragon.position = CGPoint(x: size.width / 2, y: 150)
        addChild(dragon)
        applyPlayerDragonAnimation()
    }
    
    private func setupBoss() {
        boss = SKSpriteNode(imageNamed: "ep4/boss\(currentBossIndex)")
        boss.size = CGSize(width: laneWidth * 3, height: laneWidth * 2)
        boss.position = CGPoint(x: size.width / 2, y: size.height - 150)
        boss.name = "boss"
        // Flip fix: using yScale = -1 if tails are showing with zRotation
        boss.yScale = -1 
        addChild(boss)
        
        GazeEngine.shared.bossHp = bossHps[currentBossIndex]
        GazeEngine.shared.bossMaxHp = bossHps[currentBossIndex]
        lastBossHpSnapshot = bossHps[currentBossIndex]
        followModeUntil = 0
        bossAttackCount = 0
        // setupBossHearts() // Removed redundant SpriteKit hearts

        setupBossMovement()
    }
    
    private func setupBossMovement() {
        bossTargetPoint = boss.position
        lastBossRetargetTime = 0
        bossMotionStartTime = 0
        switch currentBossIndex {
        case 1:
            bossTargetPoint = CGPoint(x: size.width * 0.2, y: size.height - 165)
        case 2:
            bossTargetPoint = CGPoint(x: size.width * 0.5, y: size.height - 180)
        case 3:
            bossTargetPoint = CGPoint(x: size.width * 0.5, y: size.height - 210)
        default: break
        }
    }
    
    private func setupBossHearts() {
        if bossHeartContainer != nil { bossHeartContainer.removeFromParent() }
        bossHeartContainer = SKNode()
        // Position above the boss
        bossHeartContainer.position = CGPoint(x: size.width / 2, y: size.height - 80)
        bossHeartContainer.zPosition = 100
        addChild(bossHeartContainer)
        
        bossHearts.removeAll()
        let maxHp = bossHps[currentBossIndex]
        let spacing: CGFloat = 25
        let totalWidth = CGFloat(maxHp - 1) * spacing
        
        for i in 0..<maxHp {
            let heart = SKLabelNode(fontNamed: "AvenirNext-Medium")
            heart.text = "❤"
            heart.fontSize = 24
            heart.fontColor = .black
            heart.verticalAlignmentMode = .center
            
            let stroke = SKLabelNode(fontNamed: "AvenirNext-Medium")
            stroke.text = "❤"
            stroke.fontSize = 26
            stroke.fontColor = .white
            stroke.zPosition = -1
            stroke.verticalAlignmentMode = .center
            heart.addChild(stroke)
            
            heart.position = CGPoint(x: -totalWidth/2 + CGFloat(i) * spacing, y: 0)
            bossHeartContainer.addChild(heart)
            bossHearts.append(heart)
        }
    }
    
    private func updateBossHearts() {
        for (i, heart) in bossHearts.enumerated() {
            heart.isHidden = (i >= GazeEngine.shared.bossHp)
        }
    }

    private func applyFlyingAnimation(to sprite: SKSpriteNode, intensity: CGFloat, keyPrefix: String) {
        sprite.removeAction(forKey: "\(keyPrefix)_wingbeat")
        sprite.removeAction(forKey: "\(keyPrefix)_hover")

        let baseXScale = sprite.xScale
        let baseYScale = sprite.yScale

        let flapUp = SKAction.group([
            .scaleX(to: baseXScale * (1.0 + 0.03 * intensity), duration: 0.18),
            .scaleY(to: baseYScale * (1.0 - 0.07 * intensity), duration: 0.18)
        ])
        let flapDown = SKAction.group([
            .scaleX(to: baseXScale * (1.0 - 0.02 * intensity), duration: 0.18),
            .scaleY(to: baseYScale * (1.0 + 0.08 * intensity), duration: 0.18)
        ])
        flapUp.timingMode = .easeInEaseOut
        flapDown.timingMode = .easeInEaseOut

        let hoverUp = SKAction.moveBy(x: 0, y: 8 * intensity, duration: 0.55)
        let hoverDown = SKAction.moveBy(x: 0, y: -8 * intensity, duration: 0.55)
        hoverUp.timingMode = .easeInEaseOut
        hoverDown.timingMode = .easeInEaseOut

        sprite.run(.repeatForever(.sequence([flapUp, flapDown])), withKey: "\(keyPrefix)_wingbeat")
        sprite.run(.repeatForever(.sequence([hoverUp, hoverDown])), withKey: "\(keyPrefix)_hover")
    }

    private func applyPlayerDragonAnimation() {
        let frameNames = [
            "ep4/Dragon_mid_up",
            "ep4/Dragon_fully_down",
            "ep4/Dragon_mid_down"
        ]

        let textures = frameNames.compactMap { name -> SKTexture? in
            let texture = SKTexture(imageNamed: name)
            return texture.size().width > 0 ? texture : nil
        }

        guard textures.count == frameNames.count else {
            applyFlyingAnimation(to: dragon, intensity: 1.0, keyPrefix: "player")
            return
        }

        dragon.removeAction(forKey: "player_wingbeat")
        dragon.removeAction(forKey: "player_hover")
        dragon.run(.repeatForever(.animate(with: textures, timePerFrame: 0.18, resize: false, restore: false)), withKey: "player_frames")

        let hoverUp = SKAction.moveBy(x: 0, y: 7, duration: 0.5)
        let hoverDown = SKAction.moveBy(x: 0, y: -7, duration: 0.5)
        hoverUp.timingMode = .easeInEaseOut
        hoverDown.timingMode = .easeInEaseOut
        dragon.run(.repeatForever(.sequence([hoverUp, hoverDown])), withKey: "player_hover")
    }
    
    private func startBossShooting() {
        let shoot = SKAction.run { [weak self] in
            self?.bossShoot()
        }
        
        let interval: TimeInterval
        switch currentBossIndex {
        case 1: interval = 2.5
        case 2: interval = 2.0
        case 3: interval = 1.5
        default: interval = 2.5
        }
        
        let wait = SKAction.wait(forDuration: interval)
        run(.repeatForever(.sequence([shoot, wait])), withKey: "bossShooting")
    }
    
    private func bossShoot() {
        if isNarrativeActive || GazeEngine.shared.bossHp <= 0 { return }
        bossAttackCount += 1

        let burstCount: Int
        if currentBossIndex == 2 && bossAttackCount % 5 == 0 {
            burstCount = 2
        } else if currentBossIndex == 3 && bossAttackCount % 5 == 0 {
            burstCount = 3
        } else {
            burstCount = 1
        }

        for index in 0..<burstCount {
            let delay = 0.5 * Double(index)
            run(.sequence([
                .wait(forDuration: delay),
                .run { [weak self] in
                    self?.spawnBossFireball(xOffset: 0)
                }
            ]))
        }
    }

    private func spawnBossFireball(xOffset: CGFloat) {
        let fireball = SKSpriteNode(imageNamed: "ep4/fire_boss\(currentBossIndex)")
        fireball.size = CGSize(width: 27, height: 38)
        fireball.position = CGPoint(x: boss.position.x + xOffset, y: boss.position.y)
        fireball.zRotation = .pi
        fireball.name = "bossFireball"
        addChild(fireball)

        let speed: TimeInterval
        switch currentBossIndex {
        case 1: speed = 2.5
        case 2: speed = 2.0
        case 3: speed = 1.5
        default: speed = 2.5
        }

        var duration = speed
        if currentBossIndex == 2 { duration *= 0.9 }
        if currentBossIndex == 3 { duration *= 0.855 }

        fireball.run(.sequence([.moveBy(x: 0, y: -800, duration: duration), .removeFromParent()]))
    }
    
    private func startSpawner() {
        let spawn = SKAction.run { [weak self] in
            self?.spawnTarget()
        }
        let wait = SKAction.wait(forDuration: 1.2)
        run(.repeatForever(.sequence([spawn, wait])))
    }
    
    private func spawnTarget() {
        if isNarrativeActive { return }
        
        let isBird = Double.random(in: 0...1) < 0.14 // ~1 in 7 chance (every 6 normal ones)
        let assetName: String
        
        if isBird {
            assetName = "ep4/food3"
        } else {
            let variations = ["", "1", "2"]
            assetName = "ep4/food\(variations.randomElement()!)"
        }
        
        let target = SKSpriteNode(imageNamed: assetName)
        if isBird {
            target.size = CGSize(width: laneWidth * 2.2, height: laneWidth * 1.5) // Larger (2 lanes)
            target.zRotation = .pi // Rotate 180 degrees
            target.name = "bird"
        } else {
            target.size = CGSize(width: laneWidth * 0.8, height: laneWidth * 0.8)
            target.name = "food"
        }
        
        let lane = isBird ? Int.random(in: 0..<numLanes-1) : Int.random(in: 0..<numLanes)
        target.position = CGPoint(x: CGFloat(lane) * laneWidth + (isBird ? laneWidth : laneWidth/2), y: size.height + 100)
        addChild(target)
        
        let duration = 3.0
        let move = SKAction.moveTo(y: -200, duration: duration)
        target.run(.sequence([move, .removeFromParent()]))
    }
    
    override func update(_ currentTime: TimeInterval) {
        super.update(currentTime)
        if isNarrativeActive { return }
        
        updateBossMotion(currentTime)
        
        let minX = laneWidth * 0.9
        let maxX = size.width - laneWidth * 0.9
        let gazeTargetX = min(maxX, max(minX, GazeEngine.shared.lookAtPoint.x * size.width))
        let xDelta = gazeTargetX - dragon.position.x
        dragonVelocityX = (dragonVelocityX * 0.78) + (xDelta * 0.09)
        dragonVelocityX = max(-18, min(18, dragonVelocityX))
        dragon.position.x = min(maxX, max(minX, dragon.position.x + dragonVelocityX))
        dragon.zRotation = dragonVelocityX * 0.015
        
        // updateBossHearts() // Removed redundant SpriteKit hearts
        
        // Fire spit logic (JAW OPEN to shoot - Needs Ammo)
        if GestureManager.shared.isJawOpen && !hasFiredJaw && GazeEngine.shared.fireAmmo > 0 {
            spitFire()
            GazeEngine.shared.fireAmmo -= 1
            hasFiredJaw = true
        } else if !GestureManager.shared.isJawOpen {
            hasFiredJaw = false
        }
        
        // Collisions
        enumerateChildNodes(withName: "*") { node, _ in
            if node.name == "food" {
                if self.dragon.intersects(node) {
                    node.removeFromParent()
                    self.fishCollected += 1
                    if self.fishCollected >= 3 {
                        GazeEngine.shared.fireAmmo += 1
                        self.fishCollected = 0
                    }
                    SoundManager.shared.playSFX("ep4/eat")
                }
            } else if node.name == "bird" {
                if self.dragon.intersects(node) {
                    node.removeFromParent()
                    GazeEngine.shared.fireAmmo += 1 // 1 bird = 1 ammo
                    SoundManager.shared.playSFX("ep4/eat")
                    self.createExplosion(at: node.position, color: .yellow)
                }
            } else if node.name == "enemy" || node.name == "bossFireball" {
                if self.dragon.intersects(node) {
                    self.createExplosion(at: node.position, color: .orange)
                    node.removeFromParent()
                    self.takeDamage()
                }
            } else if node.name == "fire" {
                // Fire vs Boss
                if self.boss.intersects(node) && GazeEngine.shared.bossHp > 0 {
                    node.removeFromParent()
                    self.createExplosion(at: node.position, color: .red)
                    GazeEngine.shared.bossHp -= 1
                    
                    if GazeEngine.shared.bossHp <= 0 {
                        self.handleBossDefeat()
                    }
                }
                // Fire vs Enemy/Food
                self.enumerateChildNodes(withName: "*") { target, stop in
                    if (target.name == "food" || target.name == "enemy") && node.intersects(target) {
                        node.removeFromParent()
                        target.removeFromParent()
                        stop.pointee = true
                    }
                }
            }
        }
    }
    
    private func handleBossDefeat() {
        self.score += 1000 * currentBossIndex
        
        if currentBossIndex < 3 {
            currentBossIndex += 1
            // Refill user HP
            GazeEngine.shared.hp = 3
            
            // Visual transition to next boss
            boss.run(.sequence([
                .fadeOut(withDuration: 0.5),
                .run { [weak self] in
                    guard let self = self else { return }
                    self.boss.texture = SKTexture(imageNamed: "ep4/boss\(self.currentBossIndex)")
                    if self.currentBossIndex == 3 {
                         self.boss.size = CGSize(width: self.laneWidth * 4, height: self.laneWidth * 2.5) // Scale up Boss 3
                    }
                    GazeEngine.shared.bossHp = self.bossHps[self.currentBossIndex]
                    GazeEngine.shared.bossMaxHp = self.bossHps[self.currentBossIndex]
                    self.lastBossHpSnapshot = self.bossHps[self.currentBossIndex]
                    self.followModeUntil = 0
                    self.bossAttackCount = 0
                    self.setupBossMovement()
                },
                .fadeIn(withDuration: 0.5),
                .run { [weak self] in
                    self?.removeAction(forKey: "bossShooting")
                    self?.startBossShooting()
                }
            ]))
        } else {
            // Final Boss Defeated: Victory Sequence
            boss.run(.fadeOut(withDuration: 1.0))
            completeEpisode(message: NSLocalizedString("CONGRATULATIONS", comment: ""), quitDelay: 4.0)
        }
    }
    
    private func spitFire() {
        let fire = SKSpriteNode(imageNamed: "ep4/fire_ball")
        fire.size = CGSize(width: 27, height: 38)
        fire.position = dragon.position
        fire.zPosition = -1
//        fire.zRotation = -.pi / 2
        fire.name = "fire"
        addChild(fire)
        fire.run(.sequence([.moveBy(x: 0, y: 800, duration: 1.0), .removeFromParent()]))
        SoundManager.shared.playSFX("ep4/fire")
    }

    private func updateBossMotion(_ currentTime: TimeInterval) {
        if bossMotionStartTime == 0 {
            bossMotionStartTime = currentTime
        }

        let time = currentTime - bossMotionStartTime
        let leftLimit = laneWidth * 0.7
        let rightLimit = size.width - laneWidth * 0.7
        let bossHp = GazeEngine.shared.bossHp
        if bossHp < lastBossHpSnapshot {
            if currentBossIndex == 2 && bossHp <= 2 {
                followModeUntil = max(followModeUntil, currentTime + 30.0)
            }
            if currentBossIndex == 3 && bossHp > 0 && bossHp % 3 == 1 {
                followModeUntil = max(followModeUntil, currentTime + 30.0)
            }
            lastBossHpSnapshot = bossHp
        }

        let isFollowMode = currentTime < followModeUntil

        switch currentBossIndex {
        case 1:
            let span = (rightLimit - leftLimit) * 0.5
            let center = (leftLimit + rightLimit) * 0.5
            let targetX = center + sin(time * 1.1) * span
            let targetY = size.height - 165 + cos(time * 1.9) * 22
            bossTargetPoint = CGPoint(x: targetX, y: targetY)
        case 2:
            if isFollowMode {
                let playerLeadX = dragon.position.x + dragonVelocityX * 5
                let targetX = min(rightLimit, max(leftLimit, playerLeadX + sin(time * 1.2) * laneWidth * 0.4))
                let targetY = size.height - 185 + cos(time * 2.0) * 18
                bossTargetPoint = CGPoint(x: targetX, y: targetY)
            } else {
                if lastBossRetargetTime == 0 || currentTime - lastBossRetargetTime > 1.55 {
                    lastBossRetargetTime = currentTime
                    bossTargetPoint = CGPoint(
                        x: CGFloat.random(in: leftLimit...rightLimit),
                        y: CGFloat.random(in: (size.height - 255)...(size.height - 135))
                    )
                }
                let driftX = sin(time * 2.1) * 16
                let driftY = cos(time * 2.5) * 10
                bossTargetPoint.x = min(rightLimit, max(leftLimit, bossTargetPoint.x + driftX * 0.04))
                bossTargetPoint.y = min(size.height - 120, max(size.height - 280, bossTargetPoint.y + driftY * 0.04))
            }
        case 3:
            let playerLeadX = dragon.position.x + dragonVelocityX * (isFollowMode ? 7 : 4)
            let trackingX = min(rightLimit, max(leftLimit, playerLeadX))
            let ambushOffset = sin(time * (isFollowMode ? 2.6 : 1.5)) * laneWidth * (isFollowMode ? 0.45 : 1.1)
            let targetX = min(rightLimit, max(leftLimit, trackingX + ambushOffset))
            let targetY = size.height - 205 + cos(time * (isFollowMode ? 3.4 : 2.1)) * (isFollowMode ? 24 : 40)
            bossTargetPoint = CGPoint(x: targetX, y: targetY)
        default:
            break
        }

        let followStrength: CGFloat
        switch currentBossIndex {
        case 1: followStrength = 0.065
        case 2: followStrength = isFollowMode ? 0.09 : 0.055
        case 3: followStrength = isFollowMode ? 0.11 : 0.075
        default: followStrength = 0.08
        }

        let dx = bossTargetPoint.x - boss.position.x
        let dy = bossTargetPoint.y - boss.position.y
        boss.position.x += dx * followStrength
        boss.position.y += dy * max(0.04, followStrength * 0.65)
        boss.zRotation = dx * 0.0028
    }
}
