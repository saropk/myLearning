import AppKit
import ScreenTimeCore

// screentimebar — menu bar widget for the screen-time tracker.
//
// Reads the same SQLite file the daemon writes (no IPC): glanceable stats
// in the menu bar, a pause/resume toggle via the meta table, gentle
// 20-20-20 break nudges recorded to the breaks table, and a shortcut to
// the local report.
//
// Flags: --db <path>   --report-url <url>

let args = Array(CommandLine.arguments.dropFirst())
var reportURL = "http://127.0.0.1:5177"
var configArgs: [String] = []
var i = 0
while i < args.count {
    if args[i] == "--report-url", i + 1 < args.count {
        reportURL = args[i + 1]
        i += 2
    } else {
        configArgs.append(args[i])
        i += 1
    }
}

do {
    let (config, _) = try Config.parse(configArgs)
    let store = try Store(dbPath: config.dbPath)

    let app = NSApplication.shared
    // Accessory: no Dock icon, no main menu — menu bar presence only.
    app.setActivationPolicy(.accessory)

    let delegate = AppDelegate(store: store, reportURL: reportURL)
    app.delegate = delegate
    app.run()
} catch {
    FileHandle.standardError.write("error: \(error)\n".data(using: .utf8)!)
    exit(1)
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    private let store: Store
    private let reportURL: String
    private var statusController: StatusItemController?
    private var breakScheduler: BreakScheduler?

    init(store: Store, reportURL: String) {
        self.store = store
        self.reportURL = reportURL
        super.init()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let controller = StatusItemController(store: store, reportURL: reportURL)
        statusController = controller
        let scheduler = BreakScheduler(store: store) { [weak controller] in
            controller?.refreshNow()
        }
        breakScheduler = scheduler
        controller.onBreakNow = { [weak scheduler] in
            scheduler?.triggerNow()
        }
    }
}
