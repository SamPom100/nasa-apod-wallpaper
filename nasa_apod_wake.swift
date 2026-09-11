import AppKit

let notifications = NSWorkspace.shared.notificationCenter
let observer = notifications.addObserver(
    forName: NSWorkspace.screensDidWakeNotification,
    object: nil,
    queue: .main
) { _ in
    let updater = Process()
    updater.executableURL = URL(fileURLWithPath: "/bin/launchctl")
    updater.arguments = ["kickstart", "gui/\(getuid())/com.nasa.apod.wallpaper"]

    do {
        try updater.run()
        updater.waitUntilExit()
        if updater.terminationStatus == 0 {
            NSLog("Display woke. The wallpaper updater received a refresh request.")
        } else {
            NSLog("The wallpaper refresh request failed with exit code %d.", updater.terminationStatus)
        }
    } catch {
        NSLog("The wallpaper refresh request failed: %@", error.localizedDescription)
    }
}

NSLog("The wallpaper wake listener is ready.")
RunLoop.main.run()
