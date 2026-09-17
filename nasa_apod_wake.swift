import AppKit

let app = NSApplication.shared
app.setActivationPolicy(.prohibited)

var pendingRefresh: DispatchWorkItem?

func scheduleRefresh(_ notification: Notification) {
    pendingRefresh?.cancel()
    let refresh = DispatchWorkItem { refreshWallpaper(notification) }
    pendingRefresh = refresh
    DispatchQueue.main.asyncAfter(deadline: .now() + 5, execute: refresh)
}

func refreshWallpaper(_ notification: Notification) {
    let status = Process()
    let output = Pipe()
    status.executableURL = URL(fileURLWithPath: "/bin/launchctl")
    status.arguments = ["print", "gui/\(getuid())/com.nasa.apod.wallpaper"]
    status.standardOutput = output
    status.standardError = output

    do {
        try status.run()
        let data = output.fileHandleForReading.readDataToEndOfFile()
        status.waitUntilExit()
        let details = String(decoding: data, as: UTF8.self)
        if status.terminationStatus != 0 || details.split(separator: "\n").contains(where: {
            $0.trimmingCharacters(in: .whitespaces).hasPrefix("pid = ")
        }) {
            NSLog("The wallpaper refresh is pending. The listener will retry.")
            scheduleRefresh(notification)
            return
        }
    } catch {
        NSLog("Cannot read the wallpaper updater status: %@", error.localizedDescription)
        scheduleRefresh(notification)
        return
    }

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
            scheduleRefresh(notification)
        }
    } catch {
        NSLog("The wallpaper refresh request failed: %@", error.localizedDescription)
        scheduleRefresh(notification)
    }
}

let wakeObserver = NSWorkspace.shared.notificationCenter.addObserver(
    forName: NSWorkspace.screensDidWakeNotification,
    object: nil,
    queue: .main,
    using: scheduleRefresh
)
let unlockObserver = DistributedNotificationCenter.default().addObserver(
    forName: Notification.Name("com.apple.screenIsUnlocked"),
    object: nil,
    queue: .main,
    using: scheduleRefresh
)
let screenObserver = NotificationCenter.default.addObserver(
    forName: NSApplication.didChangeScreenParametersNotification,
    object: nil,
    queue: .main,
    using: scheduleRefresh
)

NSLog("The wallpaper wake, unlock, and display listener is ready.")
app.run()
