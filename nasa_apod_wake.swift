import AppKit

let app = NSApplication.shared
app.setActivationPolicy(.prohibited)

func refreshWallpaper(_ notification: Notification) {
    let updater = Process()
    updater.executableURL = URL(fileURLWithPath: "/bin/launchctl")
    updater.arguments = ["kickstart", "gui/\(getuid())/com.nasa.apod.wallpaper"]

    do {
        try updater.run()
        updater.waitUntilExit()
        if updater.terminationStatus == 0 {
            NSLog("The wallpaper updater received a refresh request: %@.", notification.name.rawValue)
        } else {
            NSLog("The wallpaper refresh request failed with exit code %d.", updater.terminationStatus)
        }
    } catch {
        NSLog("The wallpaper refresh request failed: %@", error.localizedDescription)
    }
}

let wakeObserver = NSWorkspace.shared.notificationCenter.addObserver(
    forName: NSWorkspace.screensDidWakeNotification,
    object: nil,
    queue: .main,
    using: refreshWallpaper
)
let unlockObserver = DistributedNotificationCenter.default().addObserver(
    forName: Notification.Name("com.apple.screenIsUnlocked"),
    object: nil,
    queue: .main,
    using: refreshWallpaper
)

NSLog("The wallpaper wake and unlock listener is ready.")
app.run()
