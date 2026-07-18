import Foundation
import SQLite3

// sqlite3_bind_text needs SQLITE_TRANSIENT so SQLite copies the Swift string
// before the buffer is deallocated.
private let SQLITE_TRANSIENT = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

enum DBError: Error, CustomStringConvertible {
    case openFailed(String)
    case execFailed(sql: String, message: String)

    var description: String {
        switch self {
        case .openFailed(let m): return "could not open database: \(m)"
        case .execFailed(let sql, let m): return "SQL failed (\(m)): \(sql)"
        }
    }
}

enum SQLValue {
    case int(Int64)
    case real(Double)
    case text(String)
    case null
}

final class Database {
    private var db: OpaquePointer?

    init(path: String) throws {
        let dir = (path as NSString).deletingLastPathComponent
        try FileManager.default.createDirectory(
            atPath: dir, withIntermediateDirectories: true)

        var handle: OpaquePointer?
        let flags = SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_FULLMUTEX
        guard sqlite3_open_v2(path, &handle, flags, nil) == SQLITE_OK else {
            let message = handle.map { String(cString: sqlite3_errmsg($0)) } ?? "unknown"
            sqlite3_close(handle)
            throw DBError.openFailed(message)
        }
        db = handle

        // WAL lets the report server read while the daemon writes.
        try exec("PRAGMA journal_mode=WAL;")
        try exec("PRAGMA busy_timeout=5000;")
        try migrate()
    }

    deinit {
        sqlite3_close(db)
    }

    private func migrate() throws {
        try exec("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bundle_id TEXT NOT NULL,
            app_name TEXT NOT NULL,
            window_title TEXT,
            category TEXT NOT NULL,
            start_ts INTEGER NOT NULL,
            end_ts INTEGER NOT NULL,
            is_idle INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start_ts);

        CREATE TABLE IF NOT EXISTS daily_rollup (
            day TEXT NOT NULL,
            bundle_id TEXT NOT NULL,
            app_name TEXT NOT NULL,
            category TEXT NOT NULL,
            active_seconds INTEGER NOT NULL DEFAULT 0,
            idle_seconds INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (day, bundle_id)
        );

        CREATE TABLE IF NOT EXISTS breaks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompted_ts INTEGER NOT NULL,
            taken INTEGER,
            snoozed INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS categories (
            bundle_id TEXT PRIMARY KEY,
            app_name TEXT,
            category TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)
    }

    func exec(_ sql: String) throws {
        var errMsg: UnsafeMutablePointer<CChar>?
        guard sqlite3_exec(db, sql, nil, nil, &errMsg) == SQLITE_OK else {
            let message = errMsg.map { String(cString: $0) } ?? "unknown"
            sqlite3_free(errMsg)
            throw DBError.execFailed(sql: sql, message: message)
        }
    }

    /// Runs a statement with bindings; returns lastInsertRowID.
    @discardableResult
    func run(_ sql: String, _ binds: [SQLValue] = []) throws -> Int64 {
        let stmt = try prepare(sql, binds)
        defer { sqlite3_finalize(stmt) }
        guard sqlite3_step(stmt) == SQLITE_DONE else {
            throw DBError.execFailed(sql: sql, message: String(cString: sqlite3_errmsg(db)))
        }
        return sqlite3_last_insert_rowid(db)
    }

    /// Runs a query, invoking `row` for each result row.
    func query(_ sql: String, _ binds: [SQLValue] = [],
               row: (Row) throws -> Void) throws {
        let stmt = try prepare(sql, binds)
        defer { sqlite3_finalize(stmt) }
        while true {
            let rc = sqlite3_step(stmt)
            if rc == SQLITE_ROW {
                try row(Row(stmt: stmt))
            } else if rc == SQLITE_DONE {
                break
            } else {
                throw DBError.execFailed(sql: sql, message: String(cString: sqlite3_errmsg(db)))
            }
        }
    }

    private func prepare(_ sql: String, _ binds: [SQLValue]) throws -> OpaquePointer {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK, let stmt else {
            throw DBError.execFailed(sql: sql, message: String(cString: sqlite3_errmsg(db)))
        }
        for (i, value) in binds.enumerated() {
            let idx = Int32(i + 1)
            switch value {
            case .int(let v): sqlite3_bind_int64(stmt, idx, v)
            case .real(let v): sqlite3_bind_double(stmt, idx, v)
            case .text(let v): sqlite3_bind_text(stmt, idx, v, -1, SQLITE_TRANSIENT)
            case .null: sqlite3_bind_null(stmt, idx)
            }
        }
        return stmt
    }

    struct Row {
        let stmt: OpaquePointer

        func int(_ i: Int32) -> Int64 { sqlite3_column_int64(stmt, i) }
        func double(_ i: Int32) -> Double { sqlite3_column_double(stmt, i) }
        func text(_ i: Int32) -> String {
            guard let c = sqlite3_column_text(stmt, i) else { return "" }
            return String(cString: c)
        }
        func textOrNil(_ i: Int32) -> String? {
            guard sqlite3_column_type(stmt, i) != SQLITE_NULL else { return nil }
            return text(i)
        }
    }
}
