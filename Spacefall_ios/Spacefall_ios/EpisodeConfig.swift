import Foundation

struct EpisodeConfig {
    let id: Int
    let name: String
    let quote: String
    let instruction: String
    let bgAsset: String
    let alternateBackgroundAssets: [String]
    let playerAsset: String
    let obstacleAsset: String
    let sfxAsset: String
    let bgmAssets: [String]
    
    static let allEpisodes: [EpisodeConfig] = [
        EpisodeConfig(id: 1, name: "SPACE FALL", quote: "Across the deepest universe, our heartbeats still resonate.", instruction: "Move your eyes smoothly left and right to steer the ship. Double blink to fire. Break asteroids, catch rewards, and keep your hearts up.", bgAsset: "ep1/bg.jpg", alternateBackgroundAssets: ["ep1/bg1.jpg", "ep1/bg2.jpg", "ep1/bg3.jpg"], playerAsset: "ep1/ship", obstacleAsset: "ep1/asteroid", sfxAsset: "ep1/sfx", bgmAssets: ["music/Space fall.wav", "music/Free will.wav", "music/Above Saturn.wav", "music/Cross solar wind.wav"]),
        EpisodeConfig(id: 2, name: "GLACIER ESCAPE", quote: "Last golden glow over the glacier -- when I look into your eyes.", instruction: "Move your eyes smoothly left and right to carve through the snow. Blink to jump. Touch checkpoints to refill jump energy and keep running.", bgAsset: "ep2/bg.jpg", alternateBackgroundAssets: ["ep2/bg1.jpg"], playerAsset: "ep2/player", obstacleAsset: "ep2/ice", sfxAsset: "ep2/sfx", bgmAssets: ["music/Snow 2020.wav", "music/Water tale.wav"]),
        EpisodeConfig(id: 3, name: "CURSE OF GLIMPSE", quote: "My eyes are made to fool the other senses.", instruction: "Track the falling lanes with your gaze. Double blink near a target to cast a glance. Protect the population, avoid mirrors, collect holy statues, and open your jaw to cleanse every monster on screen.", bgAsset: "ep3/bg.jpg", alternateBackgroundAssets: ["ep3/bg1.jpg"], playerAsset: "ep3/mirror", obstacleAsset: "ep3/human", sfxAsset: "ep3/sfx", bgmAssets: ["music/Idolatry.wav", "music/Free will.wav"]),
        EpisodeConfig(id: 4, name: "DRAGON RAGE", quote: "I consume to conquer, feed the hunger to destroy.", instruction: "Steer the dragon smoothly with your eyes. Eat food to build fire ammo. Open your jaw to breathe fire and wear the boss down.", bgAsset: "ep4/bg.jpg", alternateBackgroundAssets: ["ep4/bg1.jpg", "ep4/bg2.jpg"], playerAsset: "ep4/Dragon", obstacleAsset: "ep4/food", sfxAsset: "ep4/eat", bgmAssets: ["music/W8.wav", "music/Above Saturn.wav", "music/Free will.wav"]),
        EpisodeConfig(id: 5, name: "SPIRITUAL RECON", quote: "What shall I leave you with? Diamonds and gold? Or the endless ghosting and fear - To haunt the rest of your life.", instruction: "Memorize the board before the coffins close. Scan the bottom row with your gaze. Blink to dig one coffin and survive the ghosts while collecting treasure.", bgAsset: "ep5/bg.jpg", alternateBackgroundAssets: ["ep5/bg1.jpg"], playerAsset: "ep5/lens", obstacleAsset: "ep5/tomb", sfxAsset: "ep5/sfx", bgmAssets: ["music/Arabic wind.wav", "music/Last Kiss of Dinosaur.wav"]),
        EpisodeConfig(id: 6, name: "ROAD RAGE 405", quote: "Road rage!!! Relax, they're just having a bad day. Don't let them ruin yours.", instruction: "Move your eyes smoothly left and right to split traffic. Double blink to throw a brick and force lighter cars to dodge. Heavy trucks and buses will not budge, so stay calm and protect your health.", bgAsset: "ep6/highway.jpg", alternateBackgroundAssets: [], playerAsset: "ep6/bike", obstacleAsset: "ep6/car", sfxAsset: "ep6/sfx", bgmAssets: ["music/August red moon.wav", "music/Charlie the Dance Bot.wav", "music/Cross solar wind.wav"])
    ]
}
