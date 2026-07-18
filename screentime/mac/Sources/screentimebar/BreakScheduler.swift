import AppKit
import Foundation

/// Drives the 20-20-20 rhythm: after ~20 minutes of continuous active use,
/// show a gentle nudge. Idle time, pausing, or a tracker gap resets the
/// clock — a natural break already happened.
final class BreakScheduler {
    static let activeTarget: TimeInterval = 20 * 60
    static let snoozeInterval: TimeInterval = 5 * 60
    private static let tick: TimeInterval = 30

    private let store: Store
    private let onStateChange: () -> Void
    private var timer: Timer?
    private var accumulatedActive: TimeInterval = 0
    private var snoozeUntil: Date?
    private var panel: NudgePanel?

    init(store: Store, onStateChange: @escaping () -> Void) {
        self.store = store
        self.onStateChange = onStateChange
        timer = Timer.scheduledTimer(
            withTimeInterval: Self.tick, repeats: true
        ) { [weak self] _ in
            self?.tick()
        }
    }

    private func tick() {
        guard panel == nil else { return }

        let snap = store.snapshot()
        guard snap.trackerAlive, !snap.paused, !snap.currentIsIdle else {
            // Idle or paused: the eyes are resting; start the count over.
            accumulatedActive = 0
            return
        }

        accumulatedActive += Self.tick
        if let until = snoozeUntil, Date() < until { return }

        if accumulatedActive >= Self.activeTarget {
            showNudge()
        }
    }

    /// "Take a Break Now" from the menu.
    func triggerNow() {
        guard panel == nil else { return }
        showNudge()
    }

    private func showNudge() {
        let breakID = store.insertBreakPrompt()
        let nudge = NudgePanel(
            onDone: { [weak self] in
                if let id = breakID { self?.store.resolveBreak(id: id, taken: true) }
                self?.reset()
            },
            onSnooze: { [weak self] in
                if let id = breakID { self?.store.markSnoozed(id: id) }
                self?.snoozeUntil = Date().addingTimeInterval(Self.snoozeInterval)
                self?.closePanel()
            },
            onSkip: { [weak self] in
                if let id = breakID { self?.store.resolveBreak(id: id, taken: false) }
                self?.reset()
            },
            onTimeout: { [weak self] in
                // No response: leave taken NULL — an honest "dismissed."
                self?.reset()
            })
        panel = nudge
        nudge.show()
    }

    private func reset() {
        accumulatedActive = 0
        snoozeUntil = nil
        closePanel()
    }

    private func closePanel() {
        panel?.close()
        panel = nil
        onStateChange()
    }
}
