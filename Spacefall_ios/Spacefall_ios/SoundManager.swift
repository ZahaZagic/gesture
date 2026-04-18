import UIKit
import AVFoundation

class SoundManager: NSObject, AVAudioPlayerDelegate, ObservableObject {
    static let shared = SoundManager()

    static let spotifyAlbumURL = URL(string: "https://open.spotify.com/album/2YtIDqV1qfRW94M7rc0Vpk?si=VxHPel-ZRN63PrBHqd9B7g")!
    
    private var bgmPlayer: AVAudioPlayer?
    var isBGMPlaying: Bool { bgmPlayer?.isPlaying ?? false }
    private var sfxPool: [String: AVAudioPlayer] = [:]
    private var playedPrimaryEpisodes = Set<Int>()
    private var currentEpisodeId: Int?
    private var currentEpisodeTracks: [String] = []
    private var currentQueue: [String] = []
    @Published var currentTrackTitle: String = ""
    
    override init() {
        super.init()
        configureAudioSession()
    }
    
    private func configureAudioSession() {
        do {
            try AVAudioSession.sharedInstance().setCategory(.ambient, mode: .default, options: [.mixWithOthers])
            try AVAudioSession.sharedInstance().setActive(true)
        } catch {
            print("SoundManager: Failed to set audio session category: \(error)")
        }
    }
    
    func playBGM(for episodeId: Int, candidates: [String]) {
        currentEpisodeId = episodeId
        currentEpisodeTracks = candidates.filter { !$0.isEmpty }
        currentQueue = makeQueue(for: episodeId, tracks: currentEpisodeTracks)
        playNextTrackInQueue()
    }

    private func makeQueue(for episodeId: Int, tracks: [String]) -> [String] {
        guard let primary = tracks.first else { return [] }
        let remaining = Array(tracks.dropFirst())

        if !playedPrimaryEpisodes.contains(episodeId) {
            playedPrimaryEpisodes.insert(episodeId)
            return [primary] + remaining.shuffled()
        }

        if remaining.isEmpty {
            return [primary]
        }

        return remaining.shuffled()
    }

    private func replenishQueueIfNeeded() {
        guard currentQueue.isEmpty, let episodeId = currentEpisodeId else { return }
        currentQueue = makeQueue(for: episodeId, tracks: currentEpisodeTracks)
    }

    private func playNextTrackInQueue() {
        replenishQueueIfNeeded()
        guard !currentQueue.isEmpty else { return }
        let name = currentQueue.removeFirst()
        bgmPlayer?.stop()
        currentTrackTitle = displayTitle(for: name)
        
        // Try Asset Catalog first (strip extension)
        let assetName = (name as NSString).deletingPathExtension
        if let asset = NSDataAsset(name: assetName) {
            do {
                bgmPlayer = try AVAudioPlayer(data: asset.data)
                bgmPlayer?.delegate = self
                bgmPlayer?.numberOfLoops = 0
                bgmPlayer?.play()
                return
            } catch { print("BGM Data Error: \(error)") }
        }
        
        // Fallback to File URL
        guard let url = findSound(name) else {
            print("SoundManager: Missing BGM asset \(name)")
            return
        }
        do {
            bgmPlayer = try AVAudioPlayer(contentsOf: url)
            bgmPlayer?.delegate = self
            bgmPlayer?.numberOfLoops = 0
            bgmPlayer?.play()
        } catch { print("BGM File Error: \(error)") }
    }
    
    func playSFX(_ name: String) {
        // Use a consistent player instance or pool to avoid immediate deallocation
        let assetName = (name as NSString).deletingPathExtension
        
        let player: AVAudioPlayer?
        if let asset = NSDataAsset(name: assetName) {
            player = try? AVAudioPlayer(data: asset.data)
        } else if let url = findSound(name) {
            player = try? AVAudioPlayer(contentsOf: url)
        } else {
            print("SoundManager: Missing SFX asset \(name)")
            return
        }
        
        guard let p = player else { return }
        p.prepareToPlay()
        p.play()
        
        // Store in a dictionary to prevent premature deallocation
        let key = UUID().uuidString
        sfxPool[key] = p
        
        // Clean up after a typical max SFX length
        DispatchQueue.main.asyncAfter(deadline: .now() + 5.0) { [weak self] in
            self?.sfxPool.removeValue(forKey: key)
        }
    }
    
    private func findSound(_ name: String) -> URL? {
        if let url = Bundle.main.url(forResource: name, withExtension: nil) { return url }
        
        let pathParts = name.components(separatedBy: "/")
        let lastPart = pathParts.last ?? name
        let directory = pathParts.count > 1 ? pathParts.dropLast().joined(separator: "/") : nil
        
        let fileParts = lastPart.components(separatedBy: ".")
        let baseName = fileParts.first ?? lastPart
        let ext = fileParts.count > 1 ? fileParts.last : "wav"
        
        if let url = Bundle.main.url(forResource: baseName, withExtension: ext, subdirectory: directory) {
            return url
        }
        
        return nil
    }

    private func displayTitle(for name: String) -> String {
        let lastPart = name.components(separatedBy: "/").last ?? name
        let base = (lastPart as NSString).deletingPathExtension
        return base
            .replacingOccurrences(of: "_", with: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    func stopAllAudio() {
        bgmPlayer?.stop()
        bgmPlayer?.delegate = nil
        bgmPlayer = nil
        currentEpisodeId = nil
        currentEpisodeTracks = []
        currentQueue = []
        currentTrackTitle = ""
        sfxPool.values.forEach { $0.stop() }
        sfxPool.removeAll()
    }

    func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        guard player === bgmPlayer else { return }
        playNextTrackInQueue()
    }
}
