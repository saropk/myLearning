import AppKit
import ScreenTimeCore

func formatHM(_ seconds: Int64) -> String {
    let h = seconds / 3600
    let m = (seconds % 3600) / 60
    return h > 0 ? "\(h)h \(String(format: "%02d", m))m" : "\(m)m"
}

/// The NSStatusItem: eye glyph + today's active total in the menu bar,
/// and a menu with the glanceable stats, pause toggle, and report link.
final class StatusItemController: NSObject, NSMenuDelegate {
    private let store: Store
    private let reportURL: String
    private let statusItem: NSStatusItem
    private var refreshTimer: Timer?

    /// Wired by the app delegate to BreakScheduler.triggerNow().
    var onBreakNow: (() -> Void)?

    init(store: Store, reportURL: String) {
        self.store = store
        self.reportURL = reportURL
        statusItem = NSStatusBar.system.statusItem(
            withLength: NSStatusItem.variableLength)
        super.init()

        if let button = statusItem.button {
            button.image = NSImage(
                systemSymbolName: "eye", accessibilityDescription: "Screen Time")
            button.imagePosition = .imageLeading
        }

        let menu = NSMenu()
        menu.delegate = self
        statusItem.menu = menu

        refreshNow()
        refreshTimer = Timer.scheduledTimer(
            withTimeInterval: 30, repeats: true
        ) { [weak self] _ in
            self?.refreshNow()
        }
    }

    func refreshNow() {
        let snap = store.snapshot()
        guard let button = statusItem.button else { return }
        if snap.paused {
            button.image = NSImage(
                systemSymbolName: "eye.slash",
                accessibilityDescription: "Screen Time (paused)")
            button.title = " paused"
        } else {
            button.image = NSImage(
                systemSymbolName: "eye", accessibilityDescription: "Screen Time")
            button.title = " " + formatHM(snap.todayActiveSeconds)
        }
    }

    // Rebuild the menu each time it opens so the numbers are current.
    func menuNeedsUpdate(_ menu: NSMenu) {
        let snap = store.snapshot()
        menu.removeAllItems()

        menu.addItem(disabled(
            "Today: \(formatHM(snap.todayActiveSeconds)) active · "
            + "\(formatHM(snap.todayIdleSeconds)) idle"))

        if snap.trackerAlive, let app = snap.currentAppName {
            let state = snap.currentIsIdle ? "idle" : "session"
            menu.addItem(disabled(
                "Now: \(app) — \(formatHM(snap.currentSessionSeconds)) \(state)"))
        } else if !snap.paused {
            menu.addItem(disabled("Tracker not running"))
        }

        menu.addItem(.separator())

        let pauseItem = NSMenuItem(
            title: snap.paused ? "Resume Tracking" : "Pause Tracking",
            action: #selector(togglePause), keyEquivalent: "")
        pauseItem.target = self
        menu.addItem(pauseItem)

        let breakItem = NSMenuItem(
            title: "Take a Break Now",
            action: #selector(breakNow), keyEquivalent: "")
        breakItem.target = self
        menu.addItem(breakItem)

        menu.addItem(.separator())

        let reportItem = NSMenuItem(
            title: "Open Report…",
            action: #selector(openReport), keyEquivalent: "r")
        reportItem.target = self
        menu.addItem(reportItem)

        menu.addItem(.separator())

        let quitItem = NSMenuItem(
            title: "Quit Screen Time Widget",
            action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        menu.addItem(quitItem)
    }

    private func disabled(_ title: String) -> NSMenuItem {
        let item = NSMenuItem(title: title, action: nil, keyEquivalent: "")
        item.isEnabled = false
        return item
    }

    @objc private func togglePause() {
        store.setPaused(!store.isPaused())
        refreshNow()
    }

    @objc private func breakNow() {
        onBreakNow?()
    }

    @objc private func openReport() {
        if let url = URL(string: reportURL) {
            NSWorkspace.shared.open(url)
        }
    }
}
