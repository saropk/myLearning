import Foundation

/// Maintains daily_rollup: per-day, per-app totals split active/idle.
/// Sessions that cross midnight are split across the days they touch.
public enum Rollup {
    public static let dayFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        f.timeZone = .current
        return f
    }()

    public static func add(db: Database, bundleID: String, appName: String,
                           category: String, isIdle: Bool,
                           start: Date, end: Date) throws {
        for (day, seconds) in splitByDay(start: start, end: end) where seconds > 0 {
            try db.run("""
                INSERT INTO daily_rollup
                    (day, bundle_id, app_name, category, active_seconds, idle_seconds)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(day, bundle_id) DO UPDATE SET
                    active_seconds = active_seconds + excluded.active_seconds,
                    idle_seconds = idle_seconds + excluded.idle_seconds,
                    app_name = excluded.app_name,
                    category = excluded.category
                """,
                [.text(day), .text(bundleID), .text(appName), .text(category),
                 .int(isIdle ? 0 : seconds),
                 .int(isIdle ? seconds : 0)])
        }
    }

    /// Rebuilds the whole rollup table from the sessions table.
    public static func rebuild(db: Database) throws {
        try db.exec("DELETE FROM daily_rollup;")
        struct Sess {
            let bundleID: String, appName: String, category: String
            let start: Date, end: Date, isIdle: Bool
        }
        var sessions: [Sess] = []
        try db.query("""
            SELECT bundle_id, app_name, category, start_ts, end_ts, is_idle
            FROM sessions ORDER BY start_ts
            """) { row in
            sessions.append(Sess(
                bundleID: row.text(0), appName: row.text(1), category: row.text(2),
                start: Date(timeIntervalSince1970: TimeInterval(row.int(3))),
                end: Date(timeIntervalSince1970: TimeInterval(row.int(4))),
                isIdle: row.int(5) == 1))
        }
        for s in sessions {
            try add(db: db, bundleID: s.bundleID, appName: s.appName,
                    category: s.category, isIdle: s.isIdle,
                    start: s.start, end: s.end)
        }
    }

    public static func splitByDay(start: Date, end: Date) -> [(day: String, seconds: Int64)] {
        guard end > start else { return [] }
        var result: [(String, Int64)] = []
        let calendar = Calendar.current
        var cursor = start
        while cursor < end {
            guard let nextMidnight = calendar.nextDate(
                after: cursor, matching: DateComponents(hour: 0, minute: 0, second: 0),
                matchingPolicy: .nextTime)
            else { break }
            let sliceEnd = min(nextMidnight, end)
            result.append((
                dayFormatter.string(from: cursor),
                Int64(sliceEnd.timeIntervalSince(cursor).rounded())))
            cursor = sliceEnd
        }
        return result
    }
}
