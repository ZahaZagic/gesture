import SwiftUI
import SpriteKit

struct MainMenuView: View {
    @State private var isGameActive = false
    @State private var selectedEpisode: EpisodeConfig?
    @ObservedObject private var gazeEngine = GazeEngine.shared
    
    var body: some View {
        ZStack {
            Color.bgDark.ignoresSafeArea()
            AnimatedMenuBackdrop()

            if isGameActive, let episode = selectedEpisode {
                // --- GAME MODE ---
                SpriteView(scene: createScene(for: episode))
                    .id(episode.id) // Force scene recreation to fix crossover bug
                    .ignoresSafeArea()
                    .transition(.opacity)
                    .gesture(
                        DragGesture(minimumDistance: 0)
                            .onChanged { value in
                                let x = value.location.x / UIScreen.main.bounds.width
                                let y = value.location.y / UIScreen.main.bounds.height
                                GazeEngine.shared.updateGaze(xAxis: x, yAxis: y)
                            }
                    )
                
                // SwiftUI Overlay (Highest Layer)
                // SwiftUI Overlay (Highest Layer) - Redesigned HUD
                if gazeEngine.isGameplayHUDVisible {
                VStack(spacing: 0) {
                    HStack(alignment: .top) {
                        // Left Column: Quit Button
                        Button(action: {
                            withAnimation(.spring()) {
                                isGameActive = false
                                selectedEpisode = nil
                            }
                        }) {
                            Image(systemName: "arrow.left")
                                .font(.system(size: 16, weight: .bold))
                                .foregroundColor(.white)
                                .frame(width: 36, height: 30)
                                .background(.ultraThinMaterial)
                                .cornerRadius(15)
                                .overlay(RoundedRectangle(cornerRadius: 15).stroke(Color.white.opacity(0.2), lineWidth: 0.5))
                        }
                        .padding(.leading, 15)
                        
                // Center Column: HP Hearts (User & Boss)
                VStack(spacing: 6) {
                    if episode.id != 3 {
                    // USER HP (Supports up to 5)
                    HStack(spacing: 5) {
                        ForEach(0..<max(3, gazeEngine.maxHp), id: \.self) { i in
                            Image(systemName: i < gazeEngine.hp ? "heart.fill" : "heart")
                                .foregroundColor(i < gazeEngine.hp ? .nebulaRose : .white.opacity(0.2))
                                .font(.system(size: 16))
                                .scaleEffect(i < gazeEngine.hp ? 1.0 : 0.8)
                        }
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(.ultraThinMaterial)
                    .cornerRadius(15)
                    .overlay(RoundedRectangle(cornerRadius: 15).stroke(Color.white.opacity(0.1), lineWidth: 0.5))
                    }

                    // BOSS HP (Ep 4)
                    if episode.id == 4 && gazeEngine.bossHp > 0 {
                        HStack(spacing: 3) {
                            ForEach(0..<gazeEngine.bossMaxHp, id: \.self) { i in
                                Image(systemName: i < gazeEngine.bossHp ? "heart.fill" : "heart")
                                    .foregroundColor(i < gazeEngine.bossHp ? .orange : .white.opacity(0.2))
                                    .font(.system(size: 11))
                                    .scaleEffect(i < gazeEngine.bossHp ? 0.88 : 0.76)
                            }
                        }
                        .padding(.horizontal, 10)
                        .padding(.vertical, 5)
                        .background(.ultraThinMaterial)
                        .cornerRadius(15)
                        .overlay(RoundedRectangle(cornerRadius: 15).stroke(Color.white.opacity(0.1), lineWidth: 0.5))
                        .padding(.top, 10)
                    }
                }
                
                Spacer()
                        
                        // Right Column: Score & Ammo/Status
                        VStack(alignment: .trailing, spacing: 6) {
                            // Score Area
                            HStack(spacing: 6) {
                                Image(systemName: "star.fill")
                                    .foregroundColor(.cosmicPrimary)
                                    .font(.system(size: 14))
                                Text("\(gazeEngine.score)")
                                    .font(.custom("AvenirNext-Bold", size: 18))
                                    .foregroundColor(.white)
                                    .monospacedDigit()
                                    .fixedSize()
                            }
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .frame(minWidth: 90, alignment: .trailing)
                            .background(.ultraThinMaterial)
                            .cornerRadius(12)
                            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.white.opacity(0.1), lineWidth: 0.5))
                            
                            // Ammo Area
                            if episode.id == 1 || episode.id == 4 || episode.id == 6 {
                                HStack(spacing: 6) {
                                    let iconName: String = {
                                        if episode.id == 1 { return "bolt.fill" }
                                        if episode.id == 4 { return "flame.fill" }
                                        return "square.fill"
                                    }()
                                    HStack(spacing: 2) {
                                        Image(systemName: iconName)
                                            .foregroundColor(episode.id == 4 ? .orange : (episode.id == 1 ? .yellow : .cosmicPrimary))
                                            .font(.system(size: 14))
                                        if episode.id == 1 {
                                            ForEach(1..<max(1, gazeEngine.weaponLevel), id: \.self) { _ in
                                                Image(systemName: "bolt.fill")
                                                    .foregroundColor(.yellow)
                                                    .font(.system(size: 12))
                                            }
                                        }
                                    }
                                    Text(episode.id == 1 && gazeEngine.temporaryWeaponAmmo > 0 ? "\(gazeEngine.temporaryWeaponAmmo)" : (gazeEngine.weaponLevel >= 3 && episode.id == 1 ? "∞" : "\(gazeEngine.fireAmmo)"))
                                        .font(.custom("AvenirNext-Bold", size: 16))
                                        .foregroundColor(.white)
                                        .monospacedDigit()
                                }
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .frame(minWidth: 90, alignment: .trailing)
                                .background(.ultraThinMaterial)
                                .cornerRadius(12)
                                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.white.opacity(0.1), lineWidth: 0.5))
                            }

                            if episode.id == 2 {
                                HStack(spacing: 6) {
                                    Image(systemName: "figure.run")
                                        .foregroundColor(.cosmicPrimary)
                                        .font(.system(size: 14))
                                    Text("\(gazeEngine.jumpEnergy)")
                                        .font(.custom("AvenirNext-Bold", size: 16))
                                        .foregroundColor(.white)
                                        .monospacedDigit()
                                    Text("/\(gazeEngine.jumpEnergyMax)")
                                        .font(.custom("AvenirNext-Regular", size: 12))
                                        .foregroundColor(.white.opacity(0.65))
                                }
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .frame(minWidth: 90, alignment: .trailing)
                                .background(.ultraThinMaterial)
                                .cornerRadius(12)
                                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.white.opacity(0.1), lineWidth: 0.5))
                            }

                            if episode.id == 3 {
                                HStack(spacing: 6) {
                                    Image(systemName: "person.3.fill")
                                        .foregroundColor(.cosmicPrimary)
                                        .font(.system(size: 14))
                                    Text("\(gazeEngine.hp)")
                                        .font(.custom("AvenirNext-Bold", size: 16))
                                        .foregroundColor(.white)
                                        .monospacedDigit()
                                }
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .frame(minWidth: 90, alignment: .trailing)
                                .background(.ultraThinMaterial)
                                .cornerRadius(12)
                                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.white.opacity(0.1), lineWidth: 0.5))

                                HStack(spacing: 6) {
                                    Text("💣")
                                        .font(.system(size: 15))
                                    Text("\(gazeEngine.rewardCharges)")
                                        .font(.custom("AvenirNext-Bold", size: 16))
                                        .foregroundColor(.white)
                                        .monospacedDigit()
                                }
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .frame(minWidth: 90, alignment: .trailing)
                                .background(.ultraThinMaterial)
                                .cornerRadius(12)
                                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.white.opacity(0.1), lineWidth: 0.5))
                            }
                        }
                        .padding(.trailing, 15)
                    }
                    .padding(.top, 40) // Closer to the top

                    Spacer()
                }
                }
                
                // Calibration Overlay
                // Calibration Overlay Removed
            } else {
                // --- MENU MODE ---
                VStack(spacing: 30) {
                    // Header Pill
                    HStack(spacing: 4) {
                        Text("Inspired by music of ".uppercased())
                        Link(destination: URL(string: "https://open.spotify.com/album/2YtIDqV1qfRW94M7rc0Vpk?si=VxHPel-ZRN63PrBHqd9B7g")!) {
                            Text("Zaha Zagic".uppercased())
                                .underline()
                        }
                    }
                    .font(.custom("AvenirNext-Medium", size: 10))
                    .foregroundColor(.cosmicPrimary)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
                    .background(Capsule().fill(Color.cosmicPrimary.opacity(0.1)))
                    .overlay(Capsule().stroke(Color.cosmicPrimary.opacity(0.3), lineWidth: 1))
                    .padding(.top, 40)

                    Text("ABOVE SATURN")
                        .font(.custom("AvenirNext-Bold", size: 36))
                        .foregroundColor(.white)
                    
                    ScrollView {
                        VStack(spacing: 15) {
                            ForEach(EpisodeConfig.allEpisodes, id: \.id) { episode in
                                Button(action: {
                                    withAnimation {
                                        selectedEpisode = episode
                                        GazeEngine.shared.resetState(for: episode.id)
                                        isGameActive = true
                                    }
                                }) {
                                    HStack {
                                        Text(episode.name)
                                            .font(.custom("AvenirNext-Regular", size: 18))
                                        Spacer()
                                        Image(systemName: "chevron.right")
                                            .font(.system(size: 14))
                                    }
                                    .padding(.horizontal, 25)
                                    .padding(.vertical, 20)
                                    .background(Color.white.opacity(0.05))
                                    .cornerRadius(15)
                                    .overlay(
                                        RoundedRectangle(cornerRadius: 15)
                                            .stroke(Color.cosmicPrimary.opacity(0.1), lineWidth: 1)
                                    )
                                    .foregroundColor(.slate300)
                                }
                                .padding(.horizontal, 30)
                            }
                        }
                    }
                }
                .transition(.opacity)
            }
        }
        .onChange(of: isGameActive) { newValue in
            if newValue {
                GazeEngine.shared.start()
            } else {
                GazeEngine.shared.stop()
            }
        }
        .alert(item: Binding<AlertError?>(
            get: { gazeEngine.errorMessage.map { AlertError(message: $0) } },
            set: { _ in gazeEngine.errorMessage = nil }
        )) { error in
            Alert(title: Text("Tracking Error"), message: Text(error.message), dismissButton: .default(Text("OK")))
        }
    }
    
    struct AlertError: Identifiable {
        let id = UUID()
        let message: String
    }
    
    // --- Calibration Support Removed ---
    
    func createScene(for config: EpisodeConfig) -> SKScene {
        let size = UIScreen.main.bounds.size
        let scene: BaseEpisodeScene
        
        switch config.id {
        case 1, 2:
            scene = AvoidanceScene(size: size, config: config)
        case 3, 5:
            scene = TargetScene(size: size, config: config)
        case 4:
            scene = DragonScene(size: size, config: config)
        case 6:
            scene = HighwayScene(size: size, config: config)
        default:
            scene = BaseEpisodeScene(size: size, config: config)
        }
        
        scene.onQuit = {
            withAnimation {
                self.isGameActive = false
                self.selectedEpisode = nil
            }
        }
        
        return scene
    }
}

private struct AnimatedMenuBackdrop: View {
    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30.0, paused: false)) { timeline in
            GeometryReader { proxy in
                let size = proxy.size
                let t = timeline.date.timeIntervalSinceReferenceDate
                let slow = t * 0.34
                let medium = t * 0.52
                let fast = t * 0.78

                ZStack {
                    LinearGradient(
                        colors: [
                            Color(red: 0.02, green: 0.04, blue: 0.12),
                            Color.cosmicPrimary.opacity(0.22 + 0.12 * (sin(slow) + 1) / 2),
                            Color(red: 0.15, green: 0.32, blue: 0.92).opacity(0.18 + 0.08 * (cos(medium) + 1) / 2),
                            Color.nebulaRose.opacity(0.2 + 0.1 * (cos(fast) + 1) / 2),
                            Color(red: 0.11, green: 0.02, blue: 0.16)
                        ],
                        startPoint: UnitPoint(x: 0.15 + 0.18 * cos(slow), y: 0.1 + 0.16 * sin(medium)),
                        endPoint: UnitPoint(x: 0.85 + 0.16 * sin(medium), y: 0.9 + 0.14 * cos(fast))
                    )
                    .ignoresSafeArea()

                    Circle()
                        .fill(Color.cosmicPrimary.opacity(0.34))
                        .frame(width: 450 + 60 * sin(medium), height: 450 + 60 * sin(medium))
                        .blur(radius: 130)
                        .rotationEffect(.degrees(t * 18))
                        .position(
                            x: size.width * 0.5 + cos(slow) * size.width * 0.34,
                            y: size.height * 0.32 + sin(medium) * size.height * 0.2
                        )

                    Ellipse()
                        .fill(Color.nebulaRose.opacity(0.3))
                        .frame(width: 540 + 75 * cos(slow), height: 380 + 55 * sin(fast))
                        .blur(radius: 135)
                        .rotationEffect(.degrees(-24 + sin(slow) * 26 + t * 12))
                        .position(
                            x: size.width * 0.56 + cos(medium + .pi) * size.width * 0.3,
                            y: size.height * 0.66 + sin(slow + .pi / 3) * size.height * 0.22
                        )

                    Circle()
                        .fill(Color(red: 0.17, green: 0.65, blue: 1.0).opacity(0.22))
                        .frame(width: 260 + 55 * cos(fast), height: 260 + 55 * cos(fast))
                        .blur(radius: 95)
                        .rotationEffect(.degrees(-t * 28))
                        .position(
                            x: size.width * 0.76 + cos(fast + .pi / 4) * size.width * 0.18,
                            y: size.height * 0.24 + sin(slow + .pi / 2) * size.height * 0.15
                        )

                    RoundedRectangle(cornerRadius: 180)
                        .fill(
                            LinearGradient(
                                colors: [Color.cosmicPrimary.opacity(0.14), Color.nebulaRose.opacity(0.22)],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .frame(width: 320 + 55 * sin(fast), height: 300 + 36 * cos(medium))
                        .blur(radius: 105)
                        .rotationEffect(.degrees(22 + cos(medium) * 30 - t * 16))
                        .position(
                            x: size.width * 0.42 + cos(fast + .pi / 2) * size.width * 0.24,
                            y: size.height * 0.46 + sin(fast) * size.height * 0.18
                        )
                }
            }
        }
        .allowsHitTesting(false)
    }
}

// Helper for Frosted Glass Effect
struct VisualEffectView: UIViewRepresentable {
    var effect: UIVisualEffect?
    func makeUIView(context: Context) -> UIVisualEffectView { UIVisualEffectView() }
    func updateUIView(_ uiView: UIVisualEffectView, context: Context) { uiView.effect = effect }
}

// --- MainMenuView ---
