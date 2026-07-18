import Foundation

/// The JSON contract consumed by the report site (2D first, 3D later).
struct DayReport: Codable {
    struct Totals: Codable {
        var activeSeconds: Int64
        var idleSeconds: Int64
    }
    struct AppEntry: Codable {
        var bundleId: String
        var appName: String
        var category: String
        var activeSeconds: Int64
        var idleSeconds: Int64
    }
    struct CategoryEntry: Codable {
        var category: String
        var activeSeconds: Int64
        var idleSeconds: Int64
    }
    struct LongestSession: Codable {
        var bundleId: String
        var appName: String
        var startTs: Int64
        var endTs: Int64
        var seconds: Int64
    }
    struct HourEntry: Codable {
        var hour: Int
        var activeSeconds: Int64
        var idleSeconds: Int64
    }
    struct Breaks: Codable {
        var prompted: Int64
        var taken: Int64
        var skipped: Int64
        var snoozed: Int64
    }

    var day: String
    var generatedAt: String
    var totals: Totals
    var apps: [AppEntry]
    var categories: [CategoryEntry]
    var longestSession: LongestSession?
    var hourly: [HourEntry]
    var breaks: Breaks
}

enum Report {
    static func build(db: Database, day: String) throws -> DayReport {
        var apps: [DayReport.AppEntry] = []
        try db.query("""
            SELECT bundle_id, app_name, category, active_seconds, idle_seconds
            FROM daily_rollup WHERE day = ?
            ORDER BY active_seconds DESC
            """, [.text(day)]) { row in
            apps.append(.init(
                bundleId: row.text(0), appName: row.text(1), category: row.text(2),
                activeSeconds: row.int(3), idleSeconds: row.int(4)))
        }

        var categoryTotals: [String: (active: Int64, idle: Int64)] = [:]
        for app in apps {
            var t = categoryTotals[app.category] ?? (0, 0)
            t.active += app.activeSeconds
            t.idle += app.idleSeconds
            categoryTotals[app.category] = t
        }
        let categories = categoryTotals
            .map { DayReport.CategoryEntry(
                category: $0.key, activeSeconds: $0.value.active, idleSeconds: $0.value.idle) }
            .sorted { $0.activeSeconds > $1.activeSeconds }

        let totals = DayReport.Totals(
            activeSeconds: apps.reduce(0) { $0 + $1.activeSeconds },
            idleSeconds: apps.reduce(0) { $0 + $1.idleSeconds })

        let (dayStart, dayEnd) = try dayBounds(day)

        var longest: DayReport.LongestSession?
        try db.query("""
            SELECT bundle_id, app_name, start_ts, end_ts, (end_ts - start_ts) AS dur
            FROM sessions
            WHERE is_idle = 0 AND start_ts < ? AND end_ts > ?
            ORDER BY dur DESC LIMIT 1
            """, [.int(dayEnd), .int(dayStart)]) { row in
            longest = .init(
                bundleId: row.text(0), appName: row.text(1),
                startTs: row.int(2), endTs: row.int(3), seconds: row.int(4))
        }

        // Per-hour distribution: clip every session to the day, then spread
        // its duration across the hour buckets it overlaps.
        var hourly = (0..<24).map {
            DayReport.HourEntry(hour: $0, activeSeconds: 0, idleSeconds: 0)
        }
        try db.query("""
            SELECT start_ts, end_ts, is_idle FROM sessions
            WHERE start_ts < ? AND end_ts > ?
            """, [.int(dayEnd), .int(dayStart)]) { row in
            let start = max(row.int(0), dayStart)
            let end = min(row.int(1), dayEnd)
            let isIdle = row.int(2) == 1
            var cursor = start
            while cursor < end {
                let hour = Int((cursor - dayStart) / 3600)
                guard hour >= 0, hour < 24 else { break }
                let hourEnd = dayStart + Int64(hour + 1) * 3600
                let slice = min(hourEnd, end) - cursor
                if isIdle {
                    hourly[hour].idleSeconds += slice
                } else {
                    hourly[hour].activeSeconds += slice
                }
                cursor = min(hourEnd, end)
            }
        }

        var breaks = DayReport.Breaks(prompted: 0, taken: 0, skipped: 0, snoozed: 0)
        try db.query("""
            SELECT COUNT(*),
                   COALESCE(SUM(CASE WHEN taken = 1 THEN 1 ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN taken = 0 THEN 1 ELSE 0 END), 0),
                   COALESCE(SUM(snoozed), 0)
            FROM breaks WHERE prompted_ts >= ? AND prompted_ts < ?
            """, [.int(dayStart), .int(dayEnd)]) { row in
            breaks = .init(prompted: row.int(0), taken: row.int(1),
                           skipped: row.int(2), snoozed: row.int(3))
        }

        let iso = ISO8601DateFormatter()
        return DayReport(
            day: day,
            generatedAt: iso.string(from: Date()),
            totals: totals,
            apps: apps,
            categories: categories,
            longestSession: longest,
            hourly: hourly,
            breaks: breaks)
    }

    static func json(db: Database, day: String) throws -> String {
        let report = try build(db: db, day: day)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(report)
        return String(data: data, encoding: .utf8) ?? "{}"
    }

    static func today() -> String {
        Rollup.dayFormatter.string(from: Date())
    }

    private static func dayBounds(_ day: String) throws -> (Int64, Int64) {
        guard let start = Rollup.dayFormatter.date(from: day) else {
            throw UsageError("invalid day '\(day)', expected YYYY-MM-DD")
        }
        let end = Calendar.current.date(byAdding: .day, value: 1, to: start)!
        return (Int64(start.timeIntervalSince1970), Int64(end.timeIntervalSince1970))
    }

    static func printStatus(db: Database, day: String) throws {
        let report = try build(db: db, day: day)
        func fmt(_ s: Int64) -> String {
            String(format: "%dh %02dm", s / 3600, (s % 3600) / 60)
        }
        print("Screen time for \(report.day)")
        print("  Active: \(fmt(report.totals.activeSeconds))   Idle: \(fmt(report.totals.idleSeconds))")
        if let longest = report.longestSession {
            print("  Longest unbroken session: \(fmt(longest.seconds)) in \(longest.appName)")
        }
        print("")
        for app in report.apps.prefix(15) {
            let bar = String(repeating: "█",
                             count: max(1, Int(app.activeSeconds / 900)))
            print("  \(fmt(app.activeSeconds))  \(bar) \(app.appName) [\(app.category)]")
        }
        if report.breaks.prompted > 0 {
            print("")
            print("  Breaks: \(report.breaks.taken)/\(report.breaks.prompted) taken, \(report.breaks.snoozed) snoozed")
        }
    }
}
