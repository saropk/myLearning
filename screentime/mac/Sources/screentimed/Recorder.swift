import Foundation
import ScreenTimeCore

/// Turns the poll stream into sessions rows. A session is an unbroken run of
/// the same (app, active-vs-idle) state. The open session's end_ts is kept
/// current on every poll, so a crash loses at most one poll interval.
final class Recorder {
    private struct OpenSession {
        let rowID: Int64
        let bundleID: String
        let appName: String
        let category: String
        let isIdle: Bool
        let start: Date
        var lastSeen: Date
    }

    private let db: Database
    private let config: Config
    private var categories: Categories
    private var current: OpenSession?

    init(db: Database, config: Config, categories: Categories) {
        self.db = db
        self.config = config
        self.categories = categories
    }

    func record(_ sample: Sample) throws {
        let isIdle = sample.idleSeconds >= config.idleThreshold
        let now = sample.date

        if var open = current {
            // Machine slept or the process was stalled: close at the last
            // sample we actually saw, and start fresh.
            let gap = now.timeIntervalSince(open.lastSeen)
            if gap > max(config.pollInterval * 3, 30) {
                try close(open, at: open.lastSeen)
                current = nil
            } else if open.bundleID == sample.bundleID, open.isIdle == isIdle {
                open.lastSeen = now
                current = open
                try db.run(
                    "UPDATE sessions SET end_ts = ? WHERE id = ?",
                    [.int(Int64(now.timeIntervalSince1970)), .int(open.rowID)])
                return
            } else {
                // The idle threshold means the first `idleSeconds` of an idle
                // stretch were logged as active — backdate the transition so
                // the active session ends when input actually stopped.
                var boundary = now
                if isIdle && !open.isIdle {
                    let idleBegan = now.addingTimeInterval(-sample.idleSeconds)
                    boundary = max(idleBegan, open.start)
                }
                try close(open, at: boundary)
                current = nil
                try openSession(sample, isIdle: isIdle, at: boundary)
                return
            }
        }

        try openSession(sample, isIdle: isIdle, at: now)
    }

    /// Closes the open session; call on shutdown or pause.
    func flush(at date: Date = Date()) throws {
        if let open = current {
            try close(open, at: min(date, open.lastSeen))
            current = nil
        }
    }

    private func openSession(_ sample: Sample, isIdle: Bool, at start: Date) throws {
        let category = categories.category(for: sample.bundleID)
        let ts = Int64(start.timeIntervalSince1970)
        let rowID = try db.run("""
            INSERT INTO sessions
                (bundle_id, app_name, window_title, category, start_ts, end_ts, is_idle)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [.text(sample.bundleID),
             .text(sample.appName),
             sample.windowTitle.map { .text($0) } ?? .null,
             .text(category),
             .int(ts), .int(ts),
             .int(isIdle ? 1 : 0)])
        current = OpenSession(
            rowID: rowID, bundleID: sample.bundleID, appName: sample.appName,
            category: category, isIdle: isIdle, start: start, lastSeen: sample.date)
    }

    private func close(_ session: OpenSession, at end: Date) throws {
        let end = max(end, session.start)
        try db.run(
            "UPDATE sessions SET end_ts = ? WHERE id = ?",
            [.int(Int64(end.timeIntervalSince1970)), .int(session.rowID)])
        try Rollup.add(
            db: db, bundleID: session.bundleID, appName: session.appName,
            category: session.category, isIdle: session.isIdle,
            start: session.start, end: end)
    }
}
