// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "screentime-mac",
    platforms: [.macOS(.v13)],
    targets: [
        // Shared: SQLite access, schema, rollups, report building, categories.
        .target(
            name: "ScreenTimeCore",
            path: "Sources/ScreenTimeCore"
        ),
        // Background tracker daemon.
        .executableTarget(
            name: "screentimed",
            dependencies: ["ScreenTimeCore"],
            path: "Sources/screentimed"
        ),
        // Menu bar widget: glanceable stats, pause toggle, 20-20-20 nudges.
        .executableTarget(
            name: "screentimebar",
            dependencies: ["ScreenTimeCore"],
            path: "Sources/screentimebar"
        ),
    ]
)
