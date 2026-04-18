import SwiftUI

@main
struct Spacefall_iosApp: App {
    init() {
        // Prevent screen from turning off during eye-controlled gameplay
        UIApplication.shared.isIdleTimerDisabled = true
    }
    
    var body: some Scene {
        WindowGroup {
            MainMenuView()
        }
    }
}
