import Foundation
import ScreenTimeCore

struct Snapshot {
    var todayActiveSeconds: Int64 = 0
    var todayIdleSeconds: Int64 = 0
    var currentAppName: String?
    var currentSessionSeconds: Int64 = 0
    var currentIsIdle = false
    /// True when the daemon updated the open session within the last ~15s.
    var trackerAlive = false
    var paused = false
}

/// The widget's view of the shared database. Reads stats, toggles the
/// pause flag, records break prompts — no IPC with the daemon needed.
final class Store {
    private let db: Database

    init(dbPath: String) throws {
        db = try Database(path: dbPath)
    }

    func snapshot(now: Date = Date()) -> Snapshot {
        var snap = Snapshot()
        snap.paused = isPaused()

        let day = Rollup.dayFormatter.string(from: now)
        try? db.query("""
            SELECT COALESCE(SUM(active_seconds), 0), COALESCE(SUM(idle_seconds), 0)
            FROM daily_rollup WHERE day = ?
            """, [.text(day)]) { row in
            snap.todayActiveSeconds = row.int(0)
            snap.todayIdleSeconds = row.int(1)
        }

        // The open session is not in the rollup until it closes — read the
        // latest session row and, if fresh, add its today-portion on top.
        let nowTs = Int64(now.timeIntervalSince1970)
        try? db.query("""
            SELECT app_name, start_ts, end_ts, is_idle
            FROM sessions ORDER BY id DESC LIMIT 1
            """) { row in
            let start = row.int(1)
            let end = row.int(2)
            let isIdle = row.int(3) == 1
            guard nowTs - end <= 15 else { return }
            snap.trackerAlive = true
            snap.currentAppName = row.text(0)
            snap.currentIsIdle = isIdle
            snap.currentSessionSeconds = max(0, end - start)

            let dayStart = Int64(
                Calendar.current.startOfDay(for: now).timeIntervalSince1970)
            let todayPortion = max(0, end - max(start, dayStart))
            if isIdle {
                snap.todayIdleSeconds += todayPortion
            } else {
                snap.todayActiveSeconds += todayPortion
            }
        }
        return snap
    }

    func isPaused() -> Bool {
        var paused = false
        try? db.query("SELECT value FROM meta WHERE key = 'paused'") {
            paused = $0.text(0) == "1"
        }
        return paused
    }

    func setPaused(_ paused: Bool) {
        try? db.run(
            "INSERT INTO meta (key, value) VALUES ('paused', ?) "
            + "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            [.text(paused ? "1" : "0")])
    }

    /// Records a break prompt; returns the row id so the outcome can be
    /// filled in when the user responds.
    func insertBreakPrompt(at date: Date = Date()) -> Int64? {
        try? db.run(
            "INSERT INTO breaks (prompted_ts, taken, snoozed) VALUES (?, NULL, 0)",
            [.int(Int64(date.timeIntervalSince1970))])
    }

    func resolveBreak(id: Int64, taken: Bool) {
        try? db.run("UPDATE breaks SET taken = ? WHERE id = ?",
                    [.int(taken ? 1 : 0), .int(id)])
    }

    func markSnoozed(id: Int64) {
        try? db.run("UPDATE breaks SET snoozed = 1 WHERE id = ?", [.int(id)])
    }
}
