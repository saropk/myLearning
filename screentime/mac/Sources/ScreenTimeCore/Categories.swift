import Foundation

/// App categorisation. Seed defaults are inserted into the categories table
/// on first run so that all edits (CLI or future UI) live in one place.
public struct Categories {
    public static let fallback = "Uncategorised"

    static let seed: [(bundleID: String, category: String)] = [
        // Work
        ("com.apple.dt.Xcode", "Work"),
        ("com.microsoft.VSCode", "Work"),
        ("com.jetbrains.intellij", "Work"),
        ("com.jetbrains.pycharm", "Work"),
        ("com.apple.Terminal", "Work"),
        ("com.googlecode.iterm2", "Work"),
        ("com.figma.Desktop", "Work"),
        ("com.apple.Notes", "Work"),
        ("md.obsidian", "Work"),
        ("notion.id", "Work"),
        // Communication
        ("com.tinyspeck.slackmacgap", "Communication"),
        ("com.apple.MobileSMS", "Communication"),
        ("com.apple.mail", "Communication"),
        ("com.microsoft.teams2", "Communication"),
        ("us.zoom.xos", "Communication"),
        ("com.hnc.Discord", "Communication"),
        ("net.whatsapp.WhatsApp", "Communication"),
        // Browsing
        ("com.apple.Safari", "Browsing"),
        ("com.google.Chrome", "Browsing"),
        ("org.mozilla.firefox", "Browsing"),
        ("company.thebrowser.Browser", "Browsing"),
        ("com.brave.Browser", "Browsing"),
        // Entertainment
        ("com.spotify.client", "Entertainment"),
        ("com.apple.Music", "Entertainment"),
        ("com.apple.TV", "Entertainment"),
        ("com.colliderli.iina", "Entertainment"),
        ("org.videolan.vlc", "Entertainment"),
    ]

    private let db: Database
    private var cache: [String: String] = [:]

    public init(db: Database) throws {
        self.db = db
        try seedIfEmpty()
        try reload()
    }

    private func seedIfEmpty() throws {
        var count: Int64 = 0
        try db.query("SELECT COUNT(*) FROM categories") { count = $0.int(0) }
        guard count == 0 else { return }
        for entry in Categories.seed {
            try db.run(
                "INSERT INTO categories (bundle_id, category) VALUES (?, ?)",
                [.text(entry.bundleID), .text(entry.category)])
        }
    }

    private mutating func reload() throws {
        var map: [String: String] = [:]
        try db.query("SELECT bundle_id, category FROM categories") {
            map[$0.text(0)] = $0.text(1)
        }
        cache = map
    }

    public func category(for bundleID: String) -> String {
        cache[bundleID] ?? Categories.fallback
    }

    public mutating func set(bundleID: String, appName: String?, category: String) throws {
        try db.run("""
            INSERT INTO categories (bundle_id, app_name, category)
            VALUES (?, ?, ?)
            ON CONFLICT(bundle_id) DO UPDATE
            SET category = excluded.category,
                app_name = COALESCE(excluded.app_name, categories.app_name)
            """,
            [.text(bundleID),
             appName.map { .text($0) } ?? .null,
             .text(category)])
        cache[bundleID] = category
    }

    public func list() throws -> [(bundleID: String, appName: String?, category: String)] {
        var rows: [(String, String?, String)] = []
        try db.query(
            "SELECT bundle_id, app_name, category FROM categories ORDER BY category, bundle_id"
        ) {
            rows.append(($0.text(0), $0.textOrNil(1), $0.text(2)))
        }
        return rows
    }
}
