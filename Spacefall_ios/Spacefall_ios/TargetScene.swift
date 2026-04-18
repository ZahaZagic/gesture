import SpriteKit
import UIKit

class TargetScene: BaseEpisodeScene {
    private static let ep3DodgingMonsterCharacters: Set<Int> = [6, 7, 10]
    private enum Ep3Kind {
        case innocent
        case monsterWeak
        case monsterStrong
        case mirror
        case reward
    }

    private enum Ep5Content {
        case treasure(points: Int)
        case heart
        case ghostDamage
        case ghostPenalty
    }

    private struct Ep5Cell {
        var node: SKSpriteNode
        var content: Ep5Content
        var contentAsset: String
        var coffinAsset: String
    }

    private var cursor: SKEmitterNode?
    private var lastBlinkTriggerState = false
    private var gameStartTime: TimeInterval = 0
    private var lastDifficultyCheck: TimeInterval = 0
    private var ep3SpeedMultiplier: Double = 1.0
    private var ep3NextSpawnTime: TimeInterval = 0
    private var ep3LastLaneSpawnTime: [Int: TimeInterval] = [:]
    private var ep3MonsterStoneCount = 0
    private var ep3RewardCharges = 0
    private var ep3MirrorBlockedUntil: TimeInterval = 0
    private var ep3MirrorOverlay: SKShapeNode?
    private var ep3RewardNode: SKSpriteNode?
    private var lastJawTriggerState = false

    private var ep5Board: [[Ep5Cell?]] = []
    private var ep5IsAnimating = false
    private var ep5IsCovered = false
    private var ep5RoundIndex = 0
    private var ep5PreviewDuration: TimeInterval = 3.0

    override func didMove(to view: SKView) {
        super.didMove(to: view)
        setupCursor()

        if config.id == 3 {
            GazeEngine.shared.maxHp = 999
            GazeEngine.shared.hp = 10
            GazeEngine.shared.score = 0
            startEp3Spawner()
        } else if config.id == 5 {
            GazeEngine.shared.maxHp = 5
            GazeEngine.shared.hp = max(3, GazeEngine.shared.hp)
            GazeEngine.shared.score = 0
        }
    }

    override func startGameplay() {
        super.startGameplay()
        if config.id == 5 && ep5Board.flatMap({ $0 }).allSatisfy({ $0 == nil }) {
            setupEp5Board()
        }
    }

    private func setupCursor() {
        if let emitter = SKEmitterNode(fileNamed: "Sparkles") {
            cursor = emitter
        } else {
            let fallback = SKEmitterNode()
            fallback.particleBirthRate = 18
            fallback.particleLifetime = 0.35
            fallback.particleScale = 0.12
            fallback.particleScaleRange = 0.05
            fallback.particleAlpha = 0.8
            fallback.particleAlphaSpeed = -2.0
            fallback.particleSpeed = 12
            fallback.particleSpeedRange = 8
            fallback.emissionAngleRange = .pi * 2
            fallback.particleColor = .cosmicPrimary
            cursor = fallback
        }

        cursor?.position = CGPoint(x: size.width / 2, y: size.height / 2)
        cursor?.zPosition = 25
        if let cursor {
            addChild(cursor)
        }
    }

    private func textureName(from candidates: [String], fallback: String) -> String {
        for candidate in candidates where UIImage(named: candidate) != nil {
            return candidate
        }
        return fallback
    }

    private func ep3Texture(character: Int, state: String) -> String {
        switch state {
        case "human":
            return textureName(from: ["ep3/char\(character)_human", "ep3/human\(min(character, 4))", "ep3/human"], fallback: "ep3/human\(min(character, 4))")
        case "human_stoned":
            return textureName(from: ["ep3/char\(character)_human_stoned", "ep3/stone\(min(character, 4))", "ep3/stone"], fallback: "ep3/stone\(min(character, 4))")
        case "monster":
            return textureName(from: ["ep3/char\(character)_monster", "ep3/human\(min(character, 4))"], fallback: "ep3/human\(min(character, 4))")
        case "monster_stoned":
            return textureName(from: ["ep3/char\(character)_monster_stoned", "ep3/char\(character)_monster", "ep3/human\(min(character, 4))"], fallback: "ep3/human\(min(character, 4))")
        default:
            return "ep3/human\(min(character, 4))"
        }
    }

    private func startEp3Spawner() {
        ep3NextSpawnTime = 0
        ep3MonsterStoneCount = 0
        ep3RewardCharges = 0
        GazeEngine.shared.rewardCharges = 0
        ep3LastLaneSpawnTime.removeAll()
        ep3MirrorBlockedUntil = 0
        ep3MirrorOverlay?.removeFromParent()
        ep3MirrorOverlay = nil
        ep3RewardNode?.removeFromParent()
        ep3RewardNode = nil
    }

    private func ep3LaneX(_ lane: Int) -> CGFloat {
        let laneWidth = size.width / 5.0
        return laneWidth * CGFloat(lane + 1) + laneWidth / 2
    }

    private func ep3ActiveLaneItems() -> Int {
        children.filter { $0.name == "ep3_character" || $0.name == "ep3_mirror" || $0.name == "ep3_reward" }.count
    }

    private func ep3SpawnInterval(elapsed: TimeInterval) -> TimeInterval {
        max(0.82, 1.55 - elapsed * 0.016)
    }

    private func ep3MaxActiveItems(elapsed: TimeInterval) -> Int {
        min(6, 3 + Int(elapsed / 20.0))
    }

    private func spawnEp3LaneItem(elapsed: TimeInterval) {
        guard !isNarrativeActive, ep3ActiveLaneItems() < ep3MaxActiveItems(elapsed: elapsed) else { return }

        let roll = Double.random(in: 0...1)
        if roll < 0.08 {
            spawnEp3Mirror()
        } else {
            spawnEp3Character()
        }
    }

    private func spawnEp3Character() {
        var lane = Int.random(in: 0..<3)
        let now = CACurrentMediaTime()
        var attempts = 0
        while attempts < 6 {
            if (ep3LastLaneSpawnTime[lane] ?? 0) < now - 1.05 { break }
            lane = Int.random(in: 0..<3)
            attempts += 1
        }
        ep3LastLaneSpawnTime[lane] = now

        let character = Int.random(in: 1...10)
        let roll = Double.random(in: 0...1)
        let kind: Ep3Kind
        let stages: [String]
        let speedFactor: Double

        if roll < 0.3 {
            kind = .innocent
            stages = ["human"]
            speedFactor = 1.04
        } else if roll < 0.8 {
            kind = .monsterWeak
            stages = ["monster"]
            speedFactor = 0.92
        } else {
            kind = .monsterStrong
            stages = ["monster"]
            speedFactor = 0.84
        }

        let node = SKSpriteNode(imageNamed: ep3Texture(character: character, state: stages[0]))
        node.size = CGSize(width: 68, height: 102)
        node.position = CGPoint(x: ep3LaneX(lane), y: size.height + 110)
        node.name = "ep3_character"
        node.zPosition = 12
        node.userData = [
            "characterIndex": character,
            "kind": kindKey(kind),
            "stages": stages,
            "stageIndex": 0,
            "lane": lane,
            "dodgedOnce": false
        ]
        addChild(node)

        let duration = max(3.8, 6.1 / (ep3SpeedMultiplier * speedFactor))
        let move = SKAction.moveTo(y: -180, duration: duration)
        let finish = SKAction.run { [weak self, weak node] in
            guard let self, let node else { return }
            self.resolveEp3Escape(for: node)
        }
        node.run(.sequence([move, finish, .removeFromParent()]))
    }

    private func spawnEp3Mirror() {
        let lane = Int.random(in: 0..<3)
        let node = SKSpriteNode(imageNamed: "ep3/mirror")
        node.size = CGSize(width: 76, height: 112)
        node.position = CGPoint(x: ep3LaneX(lane), y: size.height + 100)
        node.name = "ep3_mirror"
        node.zPosition = 12
        node.userData = ["lane": lane]
        addChild(node)
        node.run(.sequence([.moveTo(y: -180, duration: 6.8 / ep3SpeedMultiplier), .removeFromParent()]))
    }

    private func spawnEp3Reward() {
        guard ep3RewardNode == nil else { return }
        let lane = Int.random(in: 0..<3)
        let node = SKSpriteNode(imageNamed: "ep3/reward")
        node.size = CGSize(width: 76, height: 96)
        node.position = CGPoint(x: ep3LaneX(lane), y: size.height + 100)
        node.name = "ep3_reward"
        node.zPosition = 12
        node.userData = ["lane": lane]
        addChild(node)
        ep3RewardNode = node
        runEp3RewardCycle(on: node)
    }

    private func runEp3RewardCycle(on node: SKSpriteNode) {
        let lane = Int.random(in: 0..<3)
        node.position = CGPoint(x: ep3LaneX(lane), y: size.height + 100)
        node.userData?["lane"] = lane
        node.removeAllActions()
        node.run(.sequence([
            .moveTo(y: -180, duration: 7.0 / ep3SpeedMultiplier),
            .run { [weak self, weak node] in
                guard let self, let node, node.parent != nil else { return }
                self.runEp3RewardCycle(on: node)
            }
        ]))
    }

    private func kindKey(_ kind: Ep3Kind) -> String {
        switch kind {
        case .innocent: return "innocent"
        case .monsterWeak: return "monsterWeak"
        case .monsterStrong: return "monsterStrong"
        case .mirror: return "mirror"
        case .reward: return "reward"
        }
    }

    private func isMonsterKind(_ key: String) -> Bool {
        key == "monsterWeak" || key == "monsterStrong"
    }

    private func resolveEp3Escape(for node: SKSpriteNode) {
        guard let kind = node.userData?["kind"] as? String else { return }
        if isMonsterKind(kind) {
            hp = hp / 2
            UIImpactFeedbackGenerator(style: .heavy).impactOccurred()
            shakeCamera(duration: 0.2, intensity: 10)
            evaluateGameOver()
        } else if kind == "innocent" {
            hp += 1
        }
    }

    private func hoveredNode(prefixes: [String], at pos: CGPoint) -> SKSpriteNode? {
        var best: SKSpriteNode?
        var bestScore = -CGFloat.greatestFiniteMagnitude
        for child in children {
            guard let sprite = child as? SKSpriteNode, let name = sprite.name else { continue }
            guard prefixes.contains(where: { name.hasPrefix($0) }) else { continue }
            let expanded = sprite.frame.insetBy(dx: -34, dy: -34)
            let distance = hypot(pos.x - sprite.position.x, pos.y - sprite.position.y)
            let score = (expanded.contains(pos) ? 1800.0 : 0.0) - distance
            if score > bestScore {
                bestScore = score
                best = sprite
            }
        }
        return best
    }

    private func ep3HoveredNode(prefixes: [String], at pos: CGPoint) -> SKSpriteNode? {
        var best: SKSpriteNode?
        var bestScore = -CGFloat.greatestFiniteMagnitude

        for child in children {
            guard let sprite = child as? SKSpriteNode, let name = sprite.name else { continue }
            guard prefixes.contains(where: { name.hasPrefix($0) }) else { continue }
            let yDistance = abs(sprite.position.y - pos.y)
            let xDistance = abs(sprite.position.x - pos.x)
            guard xDistance < 58, yDistance < 86 else { continue }
            let score = 1400.0 - yDistance * 2.4 - xDistance * 3.0
            if score > bestScore {
                bestScore = score
                best = sprite
            }
        }

        return best
    }

    private func advanceEp3Character(_ node: SKSpriteNode) {
        guard let character = node.userData?["characterIndex"] as? Int,
              let kind = node.userData?["kind"] as? String,
              let stages = node.userData?["stages"] as? [String],
              let stageIndex = node.userData?["stageIndex"] as? Int else { return }

        playEp3StoneCombo(finalHit: false)

        if kind == "monsterStrong",
           let dodgedOnce = node.userData?["dodgedOnce"] as? Bool,
           Self.ep3DodgingMonsterCharacters.contains(character),
           !dodgedOnce {
            node.userData?["dodgedOnce"] = true
            performEp3MonsterDodge(node)
            return
        }

        if stageIndex < stages.count - 1 {
            let nextIndex = stageIndex + 1
            let nextState = stages[nextIndex]
            node.userData?["stageIndex"] = nextIndex
            node.texture = SKTexture(imageNamed: ep3Texture(character: character, state: nextState))
            createExplosion(at: node.position, color: .cosmicPrimary)
            return
        }

        node.userData?["stageIndex"] = stageIndex + 1
        if kind == "innocent" {
            node.texture = SKTexture(imageNamed: ep3Texture(character: character, state: "human_stoned"))
            createExplosion(at: node.position, color: .nebulaRose)
        } else {
            node.texture = SKTexture(imageNamed: ep3Texture(character: character, state: "monster_stoned"))
            playEp3StoneCombo(finalHit: true)
            createExplosion(at: node.position, color: .yellow)
        }
        node.removeAllActions()
        node.run(.sequence([.wait(forDuration: 1.0), .fadeOut(withDuration: 0.18), .removeFromParent()]))

        if isMonsterKind(kind) {
            score += 1
            ep3MonsterStoneCount += 1
            if ep3MonsterStoneCount >= 10 {
                ep3MonsterStoneCount -= 10
                if ep3RewardNode == nil {
                    spawnEp3Reward()
                } else {
                    ep3RewardCharges += 1
                    GazeEngine.shared.rewardCharges = ep3RewardCharges
                }
            }
        }
    }

    private func shootEp3Beam(named assetName: String, from start: CGPoint, to target: CGPoint, zRotationOffset: CGFloat = 0) {
        let beam = SKSpriteNode(imageNamed: assetName)
        let dx = target.x - start.x
        let dy = target.y - start.y
        let length = max(40, hypot(dx, dy))
        beam.size = CGSize(width: 30, height: length)
        beam.position = CGPoint(x: (start.x + target.x) / 2, y: (start.y + target.y) / 2)
        beam.zRotation = atan2(dy, dx) + zRotationOffset
        beam.alpha = 0.0
        beam.zPosition = 40
        addChild(beam)
        beam.run(.sequence([
            .group([
                .fadeIn(withDuration: 0.04),
                .scaleX(to: 1.3, duration: 0.06)
            ]),
            .wait(forDuration: 0.08),
            .fadeOut(withDuration: 0.12),
            .removeFromParent()
        ]))
    }

    private func shootEp3GlimpseBeam(to node: SKNode) {
        shootEp3Beam(named: "ep3/glimpse.png", from: CGPoint(x: size.width / 2, y: 40), to: node.position)
    }

    private func shootEp3BombBeam(to node: SKNode, delay: TimeInterval) {
        let start = CGPoint(x: node.position.x + CGFloat.random(in: -35...35), y: size.height + 80)
        run(.sequence([
            .wait(forDuration: delay),
            .run { [weak self, weak node] in
                guard let self, let node else { return }
                self.shootEp3Beam(named: "ep3/bomb.png", from: start, to: node.position)
            }
        ]))
    }

    private func performEp3MonsterDodge(_ node: SKSpriteNode) {
        guard let currentLane = node.userData?["lane"] as? Int else { return }
        let candidateLanes = [currentLane - 1, currentLane + 1].filter { (0..<3).contains($0) }
        let safeLane = candidateLanes.first { lane in
            !children.contains { other in
                guard other !== node,
                      let sprite = other as? SKSpriteNode,
                      sprite.name == "ep3_character" || sprite.name == "ep3_mirror" || sprite.name == "ep3_reward" else { return false }
                let sameLane = abs(sprite.position.x - ep3LaneX(lane)) < 22
                let closeY = abs(sprite.position.y - node.position.y) < 120
                return sameLane && closeY
            }
        } ?? currentLane

        node.userData?["lane"] = safeLane
        let destination = CGPoint(x: ep3LaneX(safeLane), y: node.position.y - 10)
        let dodge = SKAction.group([
            .sequence([
                .fadeAlpha(to: 0.18, duration: 0.08),
                .fadeAlpha(to: 1.0, duration: 0.1)
            ]),
            .move(to: destination, duration: 0.18)
        ])
        node.run(dodge)
    }

    private func playEp3StoneCombo(finalHit: Bool) {
        SoundManager.shared.playSFX("ep3/magicgaze")
        guard finalHit else { return }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.08) {
            SoundManager.shared.playSFX("ep3/sfx.wav")
        }
    }

    private func clearVisibleMonsters() {
        let monsters = children.compactMap { node -> SKSpriteNode? in
            guard let sprite = node as? SKSpriteNode,
                  sprite.name == "ep3_character",
                  let kind = sprite.userData?["kind"] as? String,
                  self.isMonsterKind(kind) else { return nil }
            return sprite
        }.sorted { $0.position.y < $1.position.y }

        for (index, sprite) in monsters.enumerated() {
            let delay = SKAction.wait(forDuration: Double(index) * 0.08)
            run(.sequence([delay, .run { [weak self, weak sprite] in
                guard let self, let sprite else { return }
                self.advanceEp3CharacterToClear(sprite)
            }]))
        }
    }

    private func advanceEp3CharacterToClear(_ node: SKSpriteNode) {
        guard let character = node.userData?["characterIndex"] as? Int,
              let kind = node.userData?["kind"] as? String else { return }
        node.removeAllActions()
        node.texture = SKTexture(imageNamed: ep3Texture(character: character, state: "monster_stoned"))
        playEp3StoneCombo(finalHit: true)
        createExplosion(at: node.position, color: .yellow)
        node.run(.sequence([.wait(forDuration: 1.0), .fadeOut(withDuration: 0.18), .removeFromParent()]))
        if isMonsterKind(kind) {
            score += 1
            ep3MonsterStoneCount += 1
            if ep3MonsterStoneCount >= 10 {
                ep3MonsterStoneCount -= 10
                if ep3RewardNode == nil {
                    spawnEp3Reward()
                } else {
                    ep3RewardCharges += 1
                    GazeEngine.shared.rewardCharges = ep3RewardCharges
                }
            }
        }
    }

    private func handleEp3DoubleBlink(at pos: CGPoint) {
        guard CACurrentMediaTime() >= ep3MirrorBlockedUntil else { return }

        if let reward = ep3HoveredNode(prefixes: ["ep3_reward"], at: pos) {
            SoundManager.shared.playSFX("ep3/magicgaze")
            ep3RewardNode = nil
            reward.removeFromParent()
            ep3RewardCharges += 1
            GazeEngine.shared.rewardCharges = ep3RewardCharges
            return
        }

        if let mirror = ep3HoveredNode(prefixes: ["ep3_mirror"], at: pos) {
            SoundManager.shared.playSFX("ep3/mirror.wav")
            mirror.removeFromParent()
            let overlay = SKShapeNode(rectOf: size)
            overlay.fillColor = UIColor.black.withAlphaComponent(0.7)
            overlay.strokeColor = .clear
            overlay.position = CGPoint(x: size.width / 2, y: size.height / 2)
            overlay.zPosition = 90
            addChild(overlay)
            ep3MirrorOverlay?.removeFromParent()
            ep3MirrorOverlay = overlay
            ep3MirrorBlockedUntil = CACurrentMediaTime() + 3.0
            overlay.run(.sequence([.wait(forDuration: 3.0), .fadeOut(withDuration: 0.2), .removeFromParent()]))
            return
        }

        if let character = ep3HoveredNode(prefixes: ["ep3_character"], at: pos) {
            if let kind = character.userData?["kind"] as? String, kind == "innocent" {
                SoundManager.shared.playSFX("ep3/human stone.wav")
            }
            advanceEp3Character(character)
        }
    }

    private func setupEp5Board() {
        children.filter { $0.name == "ep5_tomb" }.forEach { $0.removeFromParent() }
        ep5RoundIndex += 1
        ep5IsAnimating = true
        ep5IsCovered = false
        ep5PreviewDuration = ep5PreviewDurationForRound()
        ep5Board = Array(repeating: Array(repeating: nil, count: 4), count: ep5RowCount)

        for row in 0..<ep5RowCount {
            for column in 0..<4 {
                let cell = makeEp5Cell(row: row, column: column, covered: false)
                ep5Board[row][column] = cell
                addChild(cell.node)
            }
        }

        ensureEp5TreasurePerRow()
        if ep5RoundIndex >= 3 {
            ensureEp5GhostPerRow()
            ensureEp5TreasurePerRow()
        }

        layoutEp5Board(animated: false)
        run(.sequence([
            .wait(forDuration: ep5PreviewDuration),
            .run { [weak self] in self?.coverAndShuffleEp5Board() }
        ]))
    }

    private var ep5RowCount: Int {
        ep5RoundIndex > 5 ? 6 : 4
    }

    private func makeEp5Cell(row: Int, column: Int, covered: Bool) -> Ep5Cell {
        let tombIndex = Int.random(in: 1...8)
        let coffinAsset = "ep5/tomb\(tombIndex)"
        let contentRoll = Int.random(in: 0...99)
        let ghostBias = min(24, ep5RoundIndex * 4)
        let content: Ep5Content
        let contentAsset: String

        if contentRoll < 12 {
            content = .heart
            contentAsset = textureName(from: ["ep5/treasureHeart", "ep5/heart", "ep5/treasure"], fallback: "ep5/treasure")
        } else if contentRoll < max(28, 54 - ghostBias) {
            let points = [10, 20].randomElement() ?? 10
            content = .treasure(points: points)
            contentAsset = textureName(from: ["ep5/treasure\(Int.random(in: 1...5))", "ep5/treasure"], fallback: "ep5/treasure")
        } else if contentRoll < max(42, 72 - ghostBias / 2) {
            content = .treasure(points: 50)
            contentAsset = textureName(from: ["ep5/treasure5", "ep5/treasure"], fallback: "ep5/treasure")
        } else if contentRoll < min(90, 88 + ghostBias / 2) {
            content = .ghostDamage
            contentAsset = textureName(from: ["ep5/ghost\(Int.random(in: 1...5))", "ep5/ghost"], fallback: "ep5/ghost")
        } else {
            content = .ghostPenalty
            contentAsset = textureName(from: ["ep5/ghost\(Int.random(in: 1...5))", "ep5/ghost"], fallback: "ep5/ghost")
        }

        let node = SKSpriteNode(imageNamed: covered ? coffinAsset : contentAsset)
        node.size = CGSize(width: 59, height: 70)
        node.zPosition = 12
        node.name = "ep5_tomb"
        node.userData = [
            "row": row,
            "column": column
        ]

        return Ep5Cell(node: node, content: content, contentAsset: contentAsset, coffinAsset: coffinAsset)
    }

    private func ep5Position(row: Int, column: Int) -> CGPoint {
        let totalColumns: CGFloat = 6
        let laneWidth = size.width / totalColumns
        let spacingY: CGFloat = ep5RowCount > 4 ? 72 : 82
        let originY = ep5RowCount > 4 ? size.height * 0.22 : size.height * 0.25
        let playableColumn = column + 1
        return CGPoint(
            x: laneWidth * (CGFloat(playableColumn) + 0.5),
            y: originY + CGFloat(row) * spacingY
        )
    }

    private func ep5PreviewDurationForRound() -> TimeInterval {
        if ep5RoundIndex <= 5 { return 5.0 }
        if ep5RoundIndex <= 10 { return 5.5 }
        return 6.0
    }

    private func ensureEp5GhostPerRow() {
        for row in 0..<ep5RowCount {
            let hasGhost = ep5Board[row].contains { cell in
                guard let cell else { return false }
                switch cell.content {
                case .ghostDamage, .ghostPenalty:
                    return true
                default:
                    return false
                }
            }
            if !hasGhost {
                let column = Int.random(in: 0..<4)
                let asset = textureName(from: ["ep5/ghost\(Int.random(in: 1...5))", "ep5/ghost"], fallback: "ep5/ghost")
                ep5Board[row][column]?.content = Bool.random() ? .ghostDamage : .ghostPenalty
                ep5Board[row][column]?.contentAsset = asset
                if !ep5IsCovered {
                    ep5Board[row][column]?.node.texture = SKTexture(imageNamed: asset)
                }
            }
        }
    }

    private func ensureEp5TreasurePerRow() {
        for row in 0..<ep5RowCount {
            let hasTreasure = ep5Board[row].contains { cell in
                guard let cell else { return false }
                switch cell.content {
                case .treasure, .heart:
                    return true
                default:
                    return false
                }
            }
            if !hasTreasure {
                let column = Int.random(in: 0..<4)
                let points = [10, 20, 50].randomElement() ?? 10
                let asset = textureName(from: ["ep5/treasure\(Int.random(in: 1...5))", "ep5/treasure"], fallback: "ep5/treasure")
                ep5Board[row][column]?.content = .treasure(points: points)
                ep5Board[row][column]?.contentAsset = asset
                if !ep5IsCovered {
                    ep5Board[row][column]?.node.texture = SKTexture(imageNamed: asset)
                }
            }
        }
    }

    private func layoutEp5Board(animated: Bool) {
        for row in 0..<ep5RowCount {
            for column in 0..<4 {
                guard let cell = ep5Board[row][column] else { continue }
                cell.node.userData?["row"] = row
                cell.node.userData?["column"] = column
                let target = ep5Position(row: row, column: column)
                if animated {
                    cell.node.run(.move(to: target, duration: 0.26))
                } else {
                    cell.node.position = target
                }
            }
        }
    }

    private func coverAndShuffleEp5Board() {
        SoundManager.shared.playSFX("ep5/tomb.wav")
        for row in 0..<ep5RowCount {
            for column in 0..<4 {
                guard let cell = ep5Board[row][column] else { continue }
                cell.node.texture = SKTexture(imageNamed: cell.coffinAsset)
            }
        }
        ep5IsCovered = true
        shuffleEp5Board(step: 0)
    }

    private func ep5ShuffleCount() -> Int {
        if ep5RoundIndex <= 2 { return 2 }
        return min(10, 3 + ep5RoundIndex)
    }

    private func shuffleEp5Board(step: Int) {
        guard step < ep5ShuffleCount() else {
            ep5IsAnimating = false
            return
        }

        guard let first = randomEp5Coordinate(),
              let second = randomAdjacentEp5Coordinate(from: first) else {
            ep5IsAnimating = false
            return
        }

        let firstCell = ep5Board[first.row][first.column]
        ep5Board[first.row][first.column] = ep5Board[second.row][second.column]
        ep5Board[second.row][second.column] = firstCell

        let action = SKAction.run { [weak self] in
            self?.layoutEp5Board(animated: true)
        }
        run(.sequence([
            action,
            .wait(forDuration: 0.36),
            .run { [weak self] in
                self?.shuffleEp5Board(step: step + 1)
            }
        ]))
    }

    private func randomEp5Coordinate() -> (row: Int, column: Int)? {
        var options: [(Int, Int)] = []
        for row in 0..<ep5RowCount {
            for column in 0..<4 where ep5Board[row][column] != nil {
                options.append((row, column))
            }
        }
        guard let choice = options.randomElement() else { return nil }
        return (choice.0, choice.1)
    }

    private func randomAdjacentEp5Coordinate(from origin: (row: Int, column: Int)) -> (row: Int, column: Int)? {
        let neighbors = [
            (origin.row + 1, origin.column),
            (origin.row - 1, origin.column),
            (origin.row, origin.column + 1),
            (origin.row, origin.column - 1)
        ].filter { row, column in
            (0..<ep5RowCount).contains(row) && (0..<4).contains(column) && ep5Board[row][column] != nil
        }
        guard let choice = neighbors.randomElement() else { return nil }
        return choice
    }

    private func hoveredEp5BottomTomb(at pos: CGPoint) -> (row: Int, column: Int, cell: Ep5Cell)? {
        guard ep5IsCovered else { return nil }

        var best: (row: Int, column: Int, cell: Ep5Cell)?
        var bestDistance = CGFloat.greatestFiniteMagnitude

        for column in 0..<4 {
            guard let cell = ep5Board[0][column] else { continue }
            let target = ep5Position(row: 0, column: column)
            let expanded = CGRect(x: target.x - 44, y: target.y - 36, width: 88, height: 72)
            if expanded.contains(pos) {
                let distance = abs(target.x - pos.x)
                if distance < bestDistance {
                    bestDistance = distance
                    best = (0, column, cell)
                }
            }
        }

        return best
    }

    private func beginEp5Dig(at pos: CGPoint) {
        guard !ep5IsAnimating, let hovered = hoveredEp5BottomTomb(at: pos) else { return }
        ep5IsAnimating = true

        let node = hovered.cell.node
        let shakeSteps: [(TimeInterval, CGFloat, UIImpactFeedbackGenerator.FeedbackStyle)] = [
            (0.06, 4, .light),
            (0.08, 7, .medium),
            (0.1, 10, .heavy)
        ]

        var actions: [SKAction] = []
        for step in shakeSteps {
            actions.append(.run {
                UIImpactFeedbackGenerator(style: step.2).impactOccurred()
            })
            actions.append(.sequence([
                .moveBy(x: step.1, y: 0, duration: step.0 / 2),
                .moveBy(x: -step.1 * 2, y: 0, duration: step.0),
                .moveBy(x: step.1, y: 0, duration: step.0 / 2)
            ]))
        }
        actions.append(.run { [weak self] in
            self?.revealEp5Row(fromColumn: hovered.column)
        })

        node.run(.sequence(actions), withKey: "ep5Dig")
    }

    private func revealEp5Row(fromColumn selectedColumn: Int) {
        guard let chosenCell = ep5Board[0][selectedColumn] else {
            ep5IsAnimating = false
            return
        }

        chosenCell.node.texture = SKTexture(imageNamed: chosenCell.contentAsset)
        applyEp5Content(chosenCell.content, at: chosenCell.node.position, ghostAsset: chosenCell.contentAsset)

        run(.sequence([
            .wait(forDuration: 0.28),
            .run { [weak self] in
                self?.collapseEp5BottomRow()
            }
        ]))
    }

    private func animateEp5Ghost(asset: String, at position: CGPoint) {
        let ghost = SKSpriteNode(imageNamed: asset)
        ghost.size = CGSize(width: 74, height: 86)
        ghost.position = position
        ghost.zPosition = 45
        addChild(ghost)
        ghost.run(.sequence([
            .group([
                .scale(to: 2.2, duration: 0.58),
                .fadeOut(withDuration: 0.58)
            ]),
            .removeFromParent()
        ]))
    }

    private func applyEp5Content(_ content: Ep5Content, at position: CGPoint, ghostAsset: String) {
        switch content {
        case .treasure(let points):
            score += points
            SoundManager.shared.playSFX("ep5/bones")
            createExplosion(at: position, color: .yellow)
        case .heart:
            applyReward(type: "heart")
            score += 20
        case .ghostDamage:
            takeDamage()
            createExplosion(at: position, color: .white)
            animateEp5Ghost(asset: ghostAsset, at: position)
            SoundManager.shared.playSFX("ep5/ghost")
            SoundManager.shared.playSFX("ep5/scream.wav")
        case .ghostPenalty:
            score = max(0, score - 50)
            createExplosion(at: position, color: .white)
            animateEp5Ghost(asset: ghostAsset, at: position)
            SoundManager.shared.playSFX("ep5/ghost")
            SoundManager.shared.playSFX("ep5/scream.wav")
        }
    }

    private func collapseEp5BottomRow() {
        for column in 0..<4 {
            ep5Board[0][column]?.node.removeFromParent()
            ep5Board[0][column] = nil
        }

        for row in 1..<ep5RowCount {
            for column in 0..<4 {
                ep5Board[row - 1][column] = ep5Board[row][column]
                ep5Board[row][column] = nil
            }
        }

        if ep5Board.allSatisfy({ row in row.allSatisfy({ $0 == nil }) }) {
            run(.sequence([
                .wait(forDuration: 0.35),
                .run { [weak self] in self?.setupEp5Board() }
            ]))
            return
        }

        layoutEp5Board(animated: true)
        run(.sequence([
            .wait(forDuration: 0.24),
            .run { [weak self] in self?.ep5IsAnimating = false }
        ]))
    }

    override func update(_ currentTime: TimeInterval) {
        super.update(currentTime)
        if isNarrativeActive { return }

        let isSingle = GestureManager.shared.isSingleBlink()
        let isDouble = GestureManager.shared.isDoubleBlinking()
        let isJawOpen = GestureManager.shared.isJawOpen
        let isTriggering = isSingle || isDouble
        let didStartBlink = isTriggering && !lastBlinkTriggerState
        let didStartJaw = isJawOpen && !lastJawTriggerState
        lastBlinkTriggerState = isTriggering
        lastJawTriggerState = isJawOpen

        let gazePos = CGPoint(
            x: GazeEngine.shared.lookAtPoint.x * size.width,
            y: GazeEngine.shared.lookAtPoint.y * size.height
        )
        cursor?.position = gazePos
        eyeIndicator?.position = gazePos

        if config.id == 3 {
            if gameStartTime == 0 { gameStartTime = currentTime }
            let elapsed = currentTime - gameStartTime

            if elapsed - lastDifficultyCheck > 16.0 {
                ep3SpeedMultiplier *= 1.12
                lastDifficultyCheck = elapsed
            }

            if currentTime >= ep3NextSpawnTime {
                spawnEp3LaneItem(elapsed: elapsed)
                ep3NextSpawnTime = currentTime + ep3SpawnInterval(elapsed: elapsed)
            }

            if didStartJaw && ep3RewardCharges > 0 {
                ep3RewardCharges -= 1
                GazeEngine.shared.rewardCharges = ep3RewardCharges
                SoundManager.shared.playSFX("ep3/reward.wav")
                UIImpactFeedbackGenerator(style: .heavy).impactOccurred()
                clearVisibleMonsters()
            }

            if didStartBlink {
                handleEp3DoubleBlink(at: gazePos)
            }
        } else if config.id == 5 {
            let bottomTrackY = size.height * 0.25
            let trackedPos = CGPoint(x: gazePos.x, y: bottomTrackY)
            cursor?.position = trackedPos
            eyeIndicator?.position = trackedPos

            if didStartBlink {
                beginEp5Dig(at: trackedPos)
            }
        }
    }
}
