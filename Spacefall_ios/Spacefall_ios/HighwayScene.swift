import SpriteKit

class HighwayScene: BaseEpisodeScene {
    private var rider: SKSpriteNode!
    private let numLanes = 6
    private var laneWidth: CGFloat = 0
    private var lastLaneSpawnTimes: [Int: TimeInterval] = [:]
    private var scrollingBackgrounds: [SKNode] = []
    
    private var brickAmmo = 3
    private var lastBrickTime: TimeInterval = 0
    private var gameStartTime: TimeInterval = 0
    private var lastDifficultyCheck: TimeInterval = 0
    private var difficultyLevel = 1
    private let minimumVehicleGap: CGFloat = 210
    
    override func didMove(to view: SKView) {
        laneWidth = size.width / CGFloat(numLanes)
        super.didMove(to: view)
        brickAmmo = 3
        GazeEngine.shared.fireAmmo = brickAmmo
        setupScrollingRoad()
        setupRider()
        startTrafficSpawner()
        startBrickSpawner()
    }

    private func setupScrollingRoad() {
        scrollingBackgrounds.forEach { $0.removeFromParent() }
        scrollingBackgrounds.removeAll()

        let texture = SKTexture(imageNamed: config.bgAsset)
        guard texture.size().width > 0, texture.size().height > 0 else { return }

        for index in 0..<2 {
            let bg = SKSpriteNode(texture: texture)
            bg.size = CGSize(width: size.width * 1.15, height: size.height * 1.15)
            bg.position = CGPoint(x: size.width / 2, y: size.height / 2 + CGFloat(index) * size.height)
            bg.zPosition = -10
            addChild(bg)
            scrollingBackgrounds.append(bg)
        }
    }
    
    private func setupRider() {
        rider = SKSpriteNode(imageNamed: config.playerAsset)
        rider.size = CGSize(width: laneWidth * 0.42, height: laneWidth * 0.63)
        rider.position = CGPoint(x: size.width / 2, y: 150)
        addChild(rider)
    }
    
    private func startTrafficSpawner() {
        let spawn = SKAction.run { [weak self] in
            self?.spawnVehicle()
        }
        let wait = SKAction.wait(forDuration: 1.2)
        run(.repeatForever(.sequence([wait, spawn])))
    }
    
    private func spawnVehicle() {
        if isNarrativeActive { return }
        
        let vehiclesToSpawn = min(difficultyLevel, 3) 
        var usedLanes = Set<Int>()
        
        for i in 0..<vehiclesToSpawn {
            var lane = Int.random(in: 0..<numLanes)
            let spawnY = size.height + 100 + CGFloat(i) * 150.0
            
            // Traffic spacing: 
            // 1. No parallel vehicles (usedLanes)
            // 2. No adjacent lanes simultaneously (lane-1, lane+1)
            // 3. Time-staggered spacing
            // 4. Real on-road spacing against vehicles already moving or changing lanes
            let now = CACurrentMediaTime()
            var attempts = 0
            while attempts < 15 {
                let isAdjacent = usedLanes.contains(lane-1) || usedLanes.contains(lane+1)
                let recentlyUsed = (lastLaneSpawnTimes[lane] ?? 0) > now - 1.2 // Increased gap
                let roadSpaceAvailable = isVehicleLaneSafe(lane, near: spawnY, extraGap: 80)
                
                if !usedLanes.contains(lane) && !isAdjacent && !recentlyUsed && roadSpaceAvailable {
                    break // Found a good lane
                }
                lane = Int.random(in: 0..<numLanes)
                attempts += 1
            }
            if attempts >= 15 { continue }
            
            usedLanes.insert(lane)
            lastLaneSpawnTimes[lane] = now
            
            let vehiclePool = ["car", "car1", "car2", "car3", "car4", "truck", "truck1", "electric"]
            let assetName = "ep6/\(vehiclePool.randomElement()!)"
            let vehicle = SKSpriteNode(imageNamed: assetName)
            let isElectric = assetName.contains("electric")
            let isTruck = assetName.contains("truck")
            
            let vWidth: CGFloat = isTruck ? laneWidth * 0.85 : laneWidth * 0.8
            let vHeight: CGFloat = isTruck ? 140 : 100
            
            vehicle.size = CGSize(width: vWidth, height: vHeight)
            vehicle.zRotation = .pi
            // Scatter around: slight Y offset for each vehicle in the wave
            vehicle.position = CGPoint(x: CGFloat(lane) * laneWidth + laneWidth/2, y: spawnY)
            vehicle.name = isElectric ? "electric" : (isTruck ? "truck" : "small")
            vehicle.userData = ["lane": lane]
            addChild(vehicle)
            
            let roadSpeed = Double(roadScrollSpeedPerFrame() * 60.0)
            let leftLaneForwardBias = Double(numLanes - lane) * 14.0
            let speedVariance = Double.random(in: -16.0...18.0)
            let trafficForwardSpeed = 42.0 + leftLaneForwardBias + Double(difficultyLevel) * 5.0 + speedVariance
            let totalSpeed = max(95.0, roadSpeed - trafficForwardSpeed)
            let duration = (size.height + 450) / totalSpeed
            
            let move = SKAction.moveBy(x: 0, y: -(size.height + 450), duration: duration)
            
            // Electric Vehicle Dodge Logic
            if isElectric {
                let dodgeCheck = SKAction.run { [weak self, weak vehicle] in
                    guard let self = self, let vehicle = vehicle else { return }
                    let dist = vehicle.position.y - self.rider.position.y
                    if dist < 300 && dist > 100 {
                        // Dodge if rider is in the same lane
                        let riderLane = Int(self.rider.position.x / self.laneWidth)
                        let myLane = vehicle.userData?["lane"] as? Int ?? 0
                        if riderLane == myLane {
                            let newLane = myLane > 0 ? myLane - 1 : myLane + 1
                            if self.isVehicleLaneSafe(newLane, near: vehicle.position.y, excluding: vehicle) {
                                self.performVehicleDodge(vehicle, to: newLane)
                            }
                        }
                    }
                }
                let dodgeLoop = SKAction.repeatForever(.sequence([.wait(forDuration: 0.1), dodgeCheck]))
                vehicle.run(.group([
                    move,
                    dodgeLoop,
                    .sequence([
                        .wait(forDuration: duration),
                        .run { [weak self, weak vehicle] in
                            guard let self, let vehicle, vehicle.parent != nil else { return }
                            self.score += 5
                        },
                        .removeFromParent()
                    ])
                ]))
            } else {
                vehicle.run(.sequence([
                    move,
                    .run { [weak self, weak vehicle] in
                        guard let self, let vehicle, vehicle.parent != nil else { return }
                        self.score += 5
                    },
                    .removeFromParent()
                ]))
            }
        }
    }
    
    private func startBrickSpawner() {
        let spawn = SKAction.run { [weak self] in
            self?.spawnBrick()
        }
        let wait = SKAction.wait(forDuration: 4.0)
        run(.repeatForever(.sequence([wait, spawn])))
    }
    
    private func spawnBrick() {
        if isNarrativeActive { return }
        let lane = Int.random(in: 0..<numLanes)
        let brick = SKSpriteNode(imageNamed: "ep6/brick_ammo")
        brick.size = CGSize(width: 40, height: 40)
        brick.position = CGPoint(x: CGFloat(lane) * laneWidth + laneWidth/2, y: size.height + 100)
        brick.name = "brick_ammo"
        addChild(brick)
        
        brick.run(.sequence([.moveTo(y: -100, duration: 4.0), .removeFromParent()]))
    }
    
    override func update(_ currentTime: TimeInterval) {
        super.update(currentTime)
        if isNarrativeActive { return }
        
        // Difficulty Scaling every 20s
        if gameStartTime == 0 { gameStartTime = currentTime }
        let elapsed = currentTime - gameStartTime
        if elapsed - lastDifficultyCheck > 20.0 {
            difficultyLevel += 1
            lastDifficultyCheck = elapsed
        }
        
        updateRewardPersistence()
        updateRoadScroll()
        resolveVehicleSpacing()
        
        // Handle Electric Dash (if applicable) or other active effects
        
        // Dynamic lane mapping for 6 lanes (Ep 6)
        let normalizedGazeX = (GazeEngine.shared.lookAtPoint.x - 0.5) * 1.4 + 0.5
        let clampedGazeX = min(max(normalizedGazeX, 0), 1)
        let horizontalInset = laneWidth / 2
        let targetX = horizontalInset + clampedGazeX * (size.width - horizontalInset * 2)
        rider.position.x += (targetX - rider.position.x) * 0.28
        
        // Throw Brick (Double Blink)
        if GestureManager.shared.isDoubleBlinking() && brickAmmo > 0 && currentTime - lastBrickTime > 1.0 {
            throwBrick()
            brickAmmo -= 1
            lastBrickTime = currentTime
        }
        
        GazeEngine.shared.fireAmmo = brickAmmo
        
        enumerateChildNodes(withName: "*") { node, _ in
            if node.name == "small" || node.name == "truck" || node.name == "electric" {
                if node.name == "electric" {
                    self.handleElectricLogic(node)
                }
                if self.rider.intersects(node) && self.shouldCrashWithVehicle(node) {
                    self.createExplosion(at: node.position, color: .red)
                    node.removeFromParent()
                    GazeEngine.shared.carStreak = 0 // Reset on crash
                    self.takeDamage()
                }
            } else if node.name == "reward" {
                if self.rider.intersects(node) {
                    node.removeFromParent()
                    self.applyReward(type: "heart")
                }
            } else if node.name == "brick_ammo" {
                if self.rider.intersects(node) {
                    node.removeFromParent()
                    self.brickAmmo += 5
                }
            } else if node.name == "thrown_brick" {
                self.enumerateChildNodes(withName: "*") { target, stop in
                    if (target.name == "small" || target.name == "truck" || target.name == "electric") && node.intersects(target) {
                        // AI Dodge Logic: Hit by brick makes vehicle switch lanes (Red Truck is immune)
                        if let currentLane = target.userData?["lane"] as? Int, target.name != "truck" && target.name != "bus" {
                            let riderLane = Int(round((self.rider.position.x - self.laneWidth / 2) / self.laneWidth))
                            let preferredRightLane = min(currentLane + 1, self.numLanes - 1)
                            let preferredLeftLane = max(currentLane - 1, 0)
                            var newLane: Int
                            if currentLane == self.numLanes - 1 {
                                newLane = preferredLeftLane
                            } else if currentLane == 0 {
                                newLane = 1
                            } else if riderLane <= currentLane {
                                newLane = preferredRightLane
                            } else {
                                newLane = preferredLeftLane
                            }
                            if !self.isVehicleLaneSafe(newLane, near: target.position.y, excluding: target) {
                                let alternateLane = newLane == preferredRightLane ? preferredLeftLane : preferredRightLane
                                if self.isVehicleLaneSafe(alternateLane, near: target.position.y, excluding: target) {
                                    newLane = alternateLane
                                } else {
                                    node.removeFromParent()
                                    stop.pointee = true
                                    return
                                }
                            }
                            
                            self.performVehicleDodge(target, to: newLane)
                        }
                        node.removeFromParent()
                        self.createExplosion(at: target.position, color: .yellow)
                        self.score += 50
                        
                        // Ep 6 Streak
                        GazeEngine.shared.carStreak += 1
                        if GazeEngine.shared.carStreak % 5 == 0 {
                            self.spawnPersistentReward(type: "heart", at: CGPoint(x: target.position.x, y: self.size.height + 100))
                        }
                        stop.pointee = true
                    }
                }
            }
        }
    }
    
    private func handleElectricLogic(_ vehicle: SKNode) {
        let dist = vehicle.position.y - rider.position.y
        if dist < 400 && dist > 350 {
            let riderLane = GazeEngine.shared.laneIndex
            let vehicleLane = vehicle.userData?["lane"] as? Int ?? -1
            
            if riderLane == vehicleLane {
                // Dodge!
                let targetLane = vehicleLane == 0 ? 1 : vehicleLane - 1
                if isVehicleLaneSafe(targetLane, near: vehicle.position.y, excluding: vehicle) {
                    performVehicleDodge(vehicle, to: targetLane)
                }
            }
        }
    }

    private func isTrafficVehicle(_ node: SKNode) -> Bool {
        node.name == "small" || node.name == "truck" || node.name == "electric"
    }

    private func occupiedTrafficLanes(for node: SKNode) -> Set<Int> {
        var lanes = Set<Int>()
        if let lane = node.userData?["lane"] as? Int, (0..<numLanes).contains(lane) {
            lanes.insert(lane)
        }
        if let targetLane = node.userData?["targetLane"] as? Int, (0..<numLanes).contains(targetLane) {
            lanes.insert(targetLane)
        }

        let visualLane = Int(round((node.position.x - laneWidth / 2) / laneWidth))
        if (0..<numLanes).contains(visualLane) {
            lanes.insert(visualLane)
        }
        return lanes
    }

    private func requiredVehicleGap(between first: SKNode, and second: SKNode) -> CGFloat {
        max(minimumVehicleGap, (first.frame.height + second.frame.height) / 2 + 80)
    }

    private func isVehicleLaneSafe(_ lane: Int, near y: CGFloat, excluding ignored: SKNode? = nil, extraGap: CGFloat = 0) -> Bool {
        guard (0..<numLanes).contains(lane) else { return false }
        let laneCenter = CGFloat(lane) * laneWidth + laneWidth / 2
        for node in children {
            guard node !== ignored, isTrafficVehicle(node) else { continue }
            let sameLane = occupiedTrafficLanes(for: node).contains(lane) || abs(node.position.x - laneCenter) < laneWidth * 0.48
            let closeY = abs(node.position.y - y) < minimumVehicleGap + extraGap
            if sameLane && closeY {
                return false
            }
        }
        return true
    }

    private func resolveVehicleSpacing() {
        let vehicles = children.filter { isTrafficVehicle($0) }
        guard vehicles.count > 1 else { return }

        for lane in 0..<numLanes {
            let laneVehicles = vehicles
                .filter { occupiedTrafficLanes(for: $0).contains(lane) }
                .sorted { $0.position.y < $1.position.y }

            guard laneVehicles.count > 1 else { continue }

            for index in 1..<laneVehicles.count {
                let frontVehicle = laneVehicles[index - 1]
                let trailingVehicle = laneVehicles[index]
                let minGap = requiredVehicleGap(between: frontVehicle, and: trailingVehicle)
                let currentGap = trailingVehicle.position.y - frontVehicle.position.y

                if currentGap < minGap {
                    trailingVehicle.position.y = frontVehicle.position.y + minGap
                }
            }
        }
    }

    private func performVehicleDodge(_ vehicle: SKNode, to lane: Int) {
        let clampedLane = min(max(lane, 0), numLanes - 1)
        let targetX = CGFloat(clampedLane) * laneWidth + laneWidth / 2
        guard isVehicleLaneSafe(clampedLane, near: vehicle.position.y, excluding: vehicle, extraGap: 35) else { return }
        vehicle.userData?["lane"] = clampedLane
        vehicle.userData?["targetLane"] = clampedLane
        let direction: CGFloat = targetX > vehicle.position.x ? -1 : 1
        vehicle.removeAction(forKey: "laneDodge")
        vehicle.run(.group([
            .moveTo(x: targetX, duration: 0.34),
            .sequence([
                .rotate(toAngle: .pi + direction * 0.22, duration: 0.08, shortestUnitArc: true),
                .rotate(toAngle: .pi - direction * 0.16, duration: 0.12, shortestUnitArc: true),
                .rotate(toAngle: .pi, duration: 0.14, shortestUnitArc: true)
            ])
        ]), withKey: "laneDodge")
        vehicle.run(.sequence([
            .wait(forDuration: 0.36),
            .run { [weak vehicle] in
                vehicle?.userData?.removeObject(forKey: "targetLane")
            }
        ]), withKey: "laneReservation")
    }

    private func autoDodgeRider(awayFrom vehicle: SKNode) -> Bool {
        let direction: CGFloat = rider.position.x <= vehicle.position.x ? -1 : 1
        let minX = laneWidth * 0.5
        let maxX = size.width - laneWidth * 0.5
        let targetX = min(maxX, max(minX, rider.position.x + direction * laneWidth * 0.28))
        guard abs(targetX - rider.position.x) > 4 else { return false }
        rider.removeAction(forKey: "autoDodge")
        rider.run(.moveTo(x: targetX, duration: 0.14), withKey: "autoDodge")
        return true
    }

    private func shouldCrashWithVehicle(_ vehicle: SKNode) -> Bool {
        let centerOverlap = abs(rider.position.x - vehicle.position.x) <= laneWidth * 0.35
        if centerOverlap { return true }
        return !autoDodgeRider(awayFrom: vehicle)
    }
    
    private func throwBrick() {
        let projectile = ["brick", "brick1", "harmmer1", "harmmer2", "rocks"].randomElement() ?? "brick"
        let brick = SKSpriteNode(imageNamed: "ep6/\(projectile).png")
        brick.size = CGSize(width: 30, height: 30)
        brick.position = rider.position
        brick.name = "thrown_brick"
        addChild(brick)
        brick.run(.sequence([.moveBy(x: 0, y: 600, duration: 0.8), .removeFromParent()]))
    }

    private func updateRoadScroll() {
        let scrollSpeed = roadScrollSpeedPerFrame()
        for bg in scrollingBackgrounds {
            bg.position.y -= scrollSpeed
            if bg.position.y <= -size.height / 2 {
                bg.position.y += size.height * 2
            }
        }
    }

    private func roadScrollSpeedPerFrame() -> CGFloat {
        CGFloat(4.6 + Double(difficultyLevel) * 0.7)
    }
}
