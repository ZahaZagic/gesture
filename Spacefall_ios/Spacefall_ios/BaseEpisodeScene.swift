import SpriteKit
import SwiftUI

class BaseEpisodeScene: SKScene {
    private static var backgroundAssetIndices: [Int: Int] = [:]

    enum ScenePhase {
        case intro
        case playing
        case victory
        case gameOver
        case exiting
    }

    var config: EpisodeConfig
    var onQuit: (() -> Void)?
    private(set) var scenePhase: ScenePhase = .intro

    var isNarrativeActive: Bool {
        scenePhase == .intro
    }

    var isGameplayActive: Bool {
        scenePhase == .playing
    }

    var isInTerminalPhase: Bool {
        switch scenePhase {
        case .victory, .gameOver, .exiting:
            return true
        case .intro, .playing:
            return false
        }
    }
    
    var score: Int {
        get { GazeEngine.shared.score }
        set { GazeEngine.shared.score = newValue }
    }
    
    var hp: Int {
        get { GazeEngine.shared.hp }
        set { GazeEngine.shared.hp = newValue }
    }
    
    var eyeIndicator: SKShapeNode!
    var cameraNode: SKCameraNode!
    private let hapticFeedback = UIImpactFeedbackGenerator(style: .heavy)
    private weak var musicLinkNode: SKShapeNode?
    private weak var intertitleOverlayNode: SKShapeNode?

    private func addMusicLink(to parent: SKNode, y: CGFloat) {
        guard !SoundManager.shared.currentTrackTitle.isEmpty else { return }
        let capsuleSize = CGSize(width: min(size.width - 70, 360), height: 52)
        let capsule = SKShapeNode(rectOf: capsuleSize, cornerRadius: 26)
        capsule.name = "musicLink"
        capsule.fillColor = UIColor.cosmicPrimary.withAlphaComponent(0.1)
        capsule.strokeColor = UIColor.cosmicPrimary.withAlphaComponent(0.32)
        capsule.lineWidth = 1
        capsule.position = CGPoint(x: 0, y: y)
        capsule.zPosition = 2

        let trackLabel = SKLabelNode(fontNamed: "AvenirNext-Bold")
        trackLabel.name = "musicLink"
        trackLabel.text = SoundManager.shared.currentTrackTitle
        trackLabel.fontSize = 13
        trackLabel.fontColor = UIColor.white.withAlphaComponent(0.9)
        trackLabel.position = CGPoint(x: 0, y: 8)
        capsule.addChild(trackLabel)

        let artistLabel = SKLabelNode(fontNamed: "AvenirNext-Bold")
        artistLabel.name = "musicLink"
        artistLabel.text = "by Zaha Zagic"
        artistLabel.fontSize = 13
        artistLabel.fontColor = UIColor.cosmicPrimary
        artistLabel.position = CGPoint(x: 0, y: -12)
        capsule.addChild(artistLabel)

        parent.addChild(capsule)
        musicLinkNode = capsule
    }

    private func addMusicReminder(to parent: SKNode, y: CGFloat) {
        let label = SKLabelNode(fontNamed: "AvenirNext-Medium")
        label.text = "Best experienced with music on."
        label.fontSize = 13
        label.fontColor = UIColor.white.withAlphaComponent(0.58)
        label.preferredMaxLayoutWidth = size.width - 80
        label.numberOfLines = 2
        label.verticalAlignmentMode = .center
        label.position = CGPoint(x: 0, y: y)
        parent.addChild(label)
    }

    private func dismissIntertitleAndStart() {
        guard let overlay = intertitleOverlayNode, overlay.parent != nil else { return }
        musicLinkNode = nil
        overlay.removeAllActions()
        overlay.run(.sequence([
            .fadeOut(withDuration: 0.18),
            .removeFromParent(),
            .run { [weak self] in
                self?.startGameplay()
            }
        ]))
    }
    
    func takeDamage() {
        guard !isInTerminalPhase else { return }
        hp -= 1
        hapticFeedback.impactOccurred()
        
        // Screen Shake
        shakeCamera(duration: 0.2, intensity: 10)
        
        if hp <= 0 {
            showGameOver()
        } else {
            shakeCamera(duration: 0.2, intensity: 10)
        }
    }

    func modifyHP(by delta: Int, feedback: Bool = false) {
        guard !isInTerminalPhase else { return }
        hp = max(0, min(GazeEngine.shared.maxHp, hp + delta))
        if feedback && delta < 0 {
            hapticFeedback.impactOccurred()
            shakeCamera(duration: 0.2, intensity: 10)
        }
        evaluateGameOver()
    }

    func evaluateGameOver() {
        if hp <= 0 {
            showGameOver()
        }
    }
    
    func shakeCamera(duration: TimeInterval, intensity: CGFloat) {
        let originalPos = cameraNode.position
        let shake = SKAction.customAction(withDuration: duration) { node, elapsedTime in
            let amount = max(0, intensity * (1.0 - (elapsedTime / duration)))
            let x = CGFloat.random(in: -amount...amount)
            let y = CGFloat.random(in: -amount...amount)
            node.position = CGPoint(x: originalPos.x + x, y: originalPos.y + y)
        }
        let reset = SKAction.move(to: originalPos, duration: 0.05)
        cameraNode.run(.sequence([shake, reset]))
    }
    
    func createExplosion(at pos: CGPoint, color: UIColor = .white) {
        let diameter: CGFloat = 8
        UIGraphicsBeginImageContextWithOptions(CGSize(width: diameter, height: diameter), false, 0)
        let context = UIGraphicsGetCurrentContext()
        context?.setFillColor(color.cgColor)
        context?.fillEllipse(in: CGRect(x: 0, y: 0, width: diameter, height: diameter))
        let textureImage = UIGraphicsGetImageFromCurrentImageContext()
        UIGraphicsEndImageContext()
        
        let emitter = SKEmitterNode()
        if let textureImage = textureImage {
            emitter.particleTexture = SKTexture(image: textureImage)
        }
        emitter.particleBirthRate = 500
        emitter.particleLifetime = 0.5
        emitter.particlePositionRange = CGVector(dx: 10, dy: 10)
        emitter.particleSpeed = 100
        emitter.particleSpeedRange = 50
        emitter.particleAlpha = 1.0
        emitter.particleAlphaSpeed = -2.0
        emitter.particleScale = 0.2
        emitter.particleScaleRange = 0.1
        emitter.particleColor = color
        emitter.numParticlesToEmit = 50
        emitter.position = pos
        emitter.zPosition = 100
        addChild(emitter)
        
        let wait = SKAction.wait(forDuration: 1.0)
        emitter.run(.sequence([wait, .removeFromParent()]))
    }
    
    private func showGameOver() {
        scenePhase = .gameOver
        GazeEngine.shared.isGameplayHUDVisible = false
        self.removeAllActions() // Stop all spawners
        
        // Stop movement on all existing children
        for child in children {
            if child.name != "narrative" {
                child.removeAllActions()
            }
        }
        
        // Dark Overlay
        let overlay = SKShapeNode(rectOf: size)
        overlay.fillColor = .black
        overlay.strokeColor = .clear
        overlay.position = CGPoint(x: size.width/2, y: size.height/2)
        overlay.zPosition = 100 // Ensure top-most
        overlay.alpha = 0
        addChild(overlay)
        
        // Game Over Label
        let label = SKLabelNode(fontNamed: "AvenirNext-Bold")
        label.text = NSLocalizedString("GAME OVER", comment: "")
        label.fontSize = 50
        label.fontColor = .white
        label.position = CGPoint(x: 0, y: 50)
        overlay.addChild(label)
        
        // Score Display
        let scoreLabel = SKLabelNode(fontNamed: "AvenirNext-Medium")
        let scoreText = "SCORE: \(score)" // Direct score display
        scoreLabel.text = scoreText
        scoreLabel.fontSize = 30
        scoreLabel.fontColor = .cosmicPrimary
        scoreLabel.position = CGPoint(x: 0, y: -20)
        overlay.addChild(scoreLabel)
        
        // Record Message
        let highScore = UserDefaults.standard.integer(forKey: "highScore_\(config.id)")
        if score > highScore {
            UserDefaults.standard.set(score, forKey: "highScore_\(config.id)")
            let recordLabel = SKLabelNode(fontNamed: "AvenirNext-Bold")
            recordLabel.text = NSLocalizedString("NEW_RECORD", comment: "")
            recordLabel.fontSize = 24
            recordLabel.fontColor = .yellow
            recordLabel.position = CGPoint(x: 0, y: -70)
            overlay.addChild(recordLabel)
        }

        addMusicLink(to: overlay, y: 122)
        
        overlay.run(.sequence([
            .fadeAlpha(to: 0.85, duration: 0.5),
            .wait(forDuration: 3.5),
            .run { [weak self] in 
                print("GAME OVER COMPLETE - EXITING")
                self?.requestQuit()
            }
        ]))
        
    }
    
    // --- Phase 11 Consolidation: Reward System ---
    func spawnPersistentReward(type: String, at pos: CGPoint) {
        let reward = SKShapeNode(circleOfRadius: 25)
        reward.fillColor = type == "heart" ? .nebulaRose : (type == "upgrade" ? .cosmicPrimary : .orange)
        reward.strokeColor = .white
        reward.lineWidth = 2
        reward.position = pos
        reward.name = "reward"
        reward.userData = ["type": type]
        reward.zPosition = 200 // Ensure visibility
        addChild(reward)
        
        let label = SKLabelNode(fontNamed: "AvenirNext-Bold")
        label.text = type == "heart" ? "❤" : (type == "upgrade" ? "⚡" : "🚧")
        label.fontSize = 24
        label.verticalAlignmentMode = .center
        reward.addChild(label)
        
        // Use a continuous loop for persistence
        let move = SKAction.moveBy(x: 0, y: -size.height - 400, duration: 6.0)
        reward.run(.repeatForever(move))
    }
    
    func applyReward(type: String) {
        switch type {
        case "heart":
            if GazeEngine.shared.maxHp < 5 { GazeEngine.shared.maxHp += 1 }
            if GazeEngine.shared.hp < GazeEngine.shared.maxHp { GazeEngine.shared.hp += 1 }
            createExplosion(at: eyeIndicator.position, color: .nebulaRose)
        case "upgrade":
            if GazeEngine.shared.fireAmmoMax < 20 { GazeEngine.shared.fireAmmoMax += 5 }
            GazeEngine.shared.fireRecoveryRate *= 0.5
            createExplosion(at: eyeIndicator.position, color: .cosmicPrimary)
        default: break
        }
    }
    
    func updateRewardPersistence() {
        enumerateChildNodes(withName: "reward") { node, _ in
            if node.position.y < -50 {
                node.position.y = self.size.height + 150
            }
        }
    }
    
    init(size: CGSize, config: EpisodeConfig) {
        self.config = config
        super.init(size: size)
    }
    
    required init?(coder aDecoder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }
    
    override func didMove(to view: SKView) {
        setupCamera()
        setupBackground()
        setupUI()
        SoundManager.shared.playBGM(for: config.id, candidates: config.bgmAssets)
        showIntertitle()
    }

    private func activeBackgroundAsset() -> String {
        let backgrounds = [config.bgAsset] + config.alternateBackgroundAssets
        let nextIndex = Self.backgroundAssetIndices[config.id, default: 0] % backgrounds.count
        Self.backgroundAssetIndices[config.id] = (nextIndex + 1) % backgrounds.count
        return backgrounds[nextIndex]
    }
    
    private func setupCamera() {
        cameraNode = SKCameraNode()
        cameraNode.position = CGPoint(x: size.width / 2, y: size.height / 2)
        addChild(cameraNode)
        self.camera = cameraNode
    }
    
    private func setupBackground() {
        let texture = SKTexture(imageNamed: activeBackgroundAsset())
        guard texture.size().width > 0, texture.size().height > 0 else {
            let fallback = SKShapeNode(rectOf: size)
            fallback.fillColor = .bgDark
            fallback.strokeColor = .clear
            fallback.position = CGPoint(x: size.width / 2, y: size.height / 2)
            fallback.zPosition = -10
            addChild(fallback)
            return
        }
        let bg = SKSpriteNode(texture: texture)
        
        let screenRatio = size.width / size.height
        let imageRatio = texture.size().width / texture.size().height
        
        if config.id == 3 {
            bg.size = CGSize(width: size.height * imageRatio, height: size.height)
        } else if imageRatio > screenRatio {
            // Image is wider than screen: match height, crop sides
            bg.size = CGSize(width: size.height * imageRatio, height: size.height)
        } else {
            // Image is taller than screen: match width, crop top/bottom
            bg.size = CGSize(width: size.width, height: size.width / imageRatio)
        }
        
        bg.position = CGPoint(x: size.width / 2, y: size.height / 2)
        bg.zPosition = -10
        addChild(bg)
    }
    
    private func setupUI() {
        // Eye Position Indicator
        eyeIndicator = SKShapeNode(circleOfRadius: 8)
        eyeIndicator.fillColor = UIColor(red: 50/255, green: 199/255, blue: 228/255, alpha: 0.5) // Primary Cyan Translucent
        eyeIndicator.strokeColor = .white
        eyeIndicator.lineWidth = 1
        eyeIndicator.zPosition = 600
        addChild(eyeIndicator)
    }
    
    private func showIntertitle() {
        scenePhase = .intro
        GazeEngine.shared.isGameplayHUDVisible = false
        let overlay = SKShapeNode(rectOf: size)
        overlay.fillColor = UIColor(red: 17/255, green: 30/255, blue: 33/255, alpha: 1.0)
        overlay.strokeColor = .clear
        overlay.position = CGPoint(x: size.width / 2, y: size.height / 2)
        overlay.alpha = 1.0
        overlay.zPosition = 100
        addChild(overlay)
        intertitleOverlayNode = overlay
        
        let title = SKLabelNode(fontNamed: "AvenirNext-Bold")
        title.text = config.name
        title.fontSize = 28
        title.fontColor = .white
        title.position = CGPoint(x: 0, y: 102)
        overlay.addChild(title)

        let quote = SKLabelNode(fontNamed: "AvenirNext-Medium")
        quote.text = config.quote
        quote.fontSize = 15
        quote.fontColor = UIColor(red: 229/255, green: 154/255, blue: 166/255, alpha: 1.0)
        quote.preferredMaxLayoutWidth = size.width - 80
        quote.numberOfLines = 0
        quote.verticalAlignmentMode = .center
        quote.position = CGPoint(x: 0, y: 54)
        overlay.addChild(quote)

        let instruction = SKLabelNode(fontNamed: "AvenirNext-Regular")
        instruction.text = config.instruction.replacingOccurrences(of: ". ", with: ".\n")
        instruction.fontSize = 16
        instruction.fontColor = .white.withAlphaComponent(0.86)
        instruction.preferredMaxLayoutWidth = size.width - 90
        instruction.numberOfLines = 0
        instruction.verticalAlignmentMode = .center
        instruction.position = CGPoint(x: 0, y: -46)
        overlay.addChild(instruction)

        addMusicReminder(to: overlay, y: 272)
        addMusicLink(to: overlay, y: 214)

        if config.id == 1 {
            let credit = SKLabelNode(fontNamed: "AvenirNext-Regular")
            credit.text = "Background credits: NASA"
            credit.fontSize = 13
            credit.fontColor = UIColor.white.withAlphaComponent(0.58)
            credit.position = CGPoint(x: 0, y: -size.height / 2 + 34)
            overlay.addChild(credit)
        }
        
        overlay.run(.sequence([
            .wait(forDuration: 5.0),
            .run { [weak self] in
                self?.dismissIntertitleAndStart()
            }
        ]))
    }

    func startGameplay() {
        guard scenePhase == .intro else { return }
        scenePhase = .playing
        GazeEngine.shared.isGameplayHUDVisible = true
    }

    func completeEpisode(message: String = NSLocalizedString("CONGRATULATIONS", comment: ""),
                         fontColor: UIColor = .cosmicPrimary,
                         quitDelay: TimeInterval = 3.0) {
        guard !isInTerminalPhase else { return }
        scenePhase = .victory
        GazeEngine.shared.isGameplayHUDVisible = false
        removeAllActions()
        children.forEach { $0.removeAllActions() }

        let overlay = SKShapeNode(rectOf: size)
        overlay.fillColor = UIColor.black.withAlphaComponent(0.55)
        overlay.strokeColor = .clear
        overlay.position = CGPoint(x: size.width / 2, y: size.height / 2)
        overlay.zPosition = 100
        overlay.alpha = 0
        addChild(overlay)

        let label = SKLabelNode(fontNamed: "AvenirNext-Bold")
        label.text = message
        label.fontSize = 34
        label.fontColor = fontColor
        label.position = CGPoint(x: 0, y: 0)
        label.preferredMaxLayoutWidth = size.width - 80
        label.numberOfLines = 0
        label.verticalAlignmentMode = .center
        overlay.addChild(label)

        overlay.run(.sequence([
            .fadeIn(withDuration: 0.2),
            .wait(forDuration: quitDelay),
            .run { [weak self] in
                self?.requestQuit()
            }
        ]))
    }

    func requestQuit() {
        guard scenePhase != .exiting else { return }
        scenePhase = .exiting
        GazeEngine.shared.isGameplayHUDVisible = false
        SoundManager.shared.stopAllAudio()
        onQuit?()
    }
    
    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent?) {
        guard let touch = touches.first else { return }
        let location = touch.location(in: self)
        func nodeOrAncestor(named target: String, from node: SKNode?) -> Bool {
            var current = node
            while let unwrapped = current {
                if unwrapped.name == target { return true }
                current = unwrapped.parent
            }
            return false
        }

        let tappedNodes = nodes(at: location)
        let focusedNode = atPoint(location)

        if nodeOrAncestor(named: "skipIntro", from: focusedNode) ||
            tappedNodes.contains(where: { nodeOrAncestor(named: "skipIntro", from: $0) }) {
            dismissIntertitleAndStart()
            return
        }
        if nodeOrAncestor(named: "musicLink", from: focusedNode) ||
            tappedNodes.contains(where: { nodeOrAncestor(named: "musicLink", from: $0) }) {
            UIApplication.shared.open(SoundManager.spotifyAlbumURL)
        }
    }
    
    override func update(_ currentTime: TimeInterval) {
        guard isGameplayActive else { return }
        
        let gazePos = CGPoint(x: GazeEngine.shared.lookAtPoint.x * size.width,
                              y: GazeEngine.shared.lookAtPoint.y * size.height)
        eyeIndicator?.position = gazePos
        
        updateRewardPersistence()
    }
}
