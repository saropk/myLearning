import AppKit
import Foundation
import ScreenTimeCore

let usage = """
screentimed — screen-time tracker daemon (macOS)

USAGE: screentimed [SUBCOMMAND] [OPTIONS]

SUBCOMMANDS:
  run                       Start tracking (default). Ctrl-C to stop.
  status [YYYY-MM-DD]       Print a summary for a day (default: today).
  export [YYYY-MM-DD]       Print the day's report as JSON (default: today).
  rollup                    Rebuild daily_rollup from raw sessions.
  category list             List app → category mappings.
  category set <bundle-id> <category>
                            Set a mapping (e.g. Work, Communication,
                            Browsing, Entertainment).
  pause | resume            Pause/resume tracking (works while the daemon
                            runs; state is stored in the database).

OPTIONS:
  --db <path>               Database path
                            (default: ~/Library/Application Support/ScreenTime/screentime.sqlite3)
  --interval <seconds>      Poll interval, default 2
  --idle-threshold <secs>   Idle threshold, default 120
  --capture-titles          Capture window titles (requires Accessibility
                            permission; off by default)
"""

func main() {
    do {
        let (config, rest) = try Config.parse(Array(CommandLine.arguments.dropFirst()))
        let subcommand = rest.first ?? "run"

        switch subcommand {
        case "run":
            try runDaemon(config)
        case "status":
            let db = try Database(path: config.dbPath)
            try Report.printStatus(db: db, day: rest.count > 1 ? rest[1] : Report.today())
        case "export":
            let db = try Database(path: config.dbPath)
            print(try Report.json(db: db, day: rest.count > 1 ? rest[1] : Report.today()))
        case "rollup":
            let db = try Database(path: config.dbPath)
            try Rollup.rebuild(db: db)
            print("daily_rollup rebuilt")
        case "category":
            try runCategory(config, args: Array(rest.dropFirst()))
        case "pause", "resume":
            let db = try Database(path: config.dbPath)
            try db.run(
                "INSERT INTO meta (key, value) VALUES ('paused', ?) "
                + "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                [.text(subcommand == "pause" ? "1" : "0")])
            print("tracking \(subcommand)d")
        case "help", "--help", "-h":
            print(usage)
        default:
            throw UsageError("unknown subcommand '\(subcommand)'\n\n\(usage)")
        }
    } catch {
        FileHandle.standardError.write("error: \(error)\n".data(using: .utf8)!)
        exit(1)
    }
}

func runCategory(_ config: Config, args: [String]) throws {
    let db = try Database(path: config.dbPath)
    var categories = try Categories(db: db)
    switch args.first {
    case "list", nil:
        for row in try categories.list() {
            let name = row.appName.map { " (\($0))" } ?? ""
            print("\(row.category)\t\(row.bundleID)\(name)")
        }
    case "set":
        guard args.count == 3 else {
            throw UsageError("usage: screentimed category set <bundle-id> <category>")
        }
        try categories.set(bundleID: args[1], appName: nil, category: args[2])
        print("\(args[1]) → \(args[2])")
    default:
        throw UsageError("usage: screentimed category [list | set <bundle-id> <category>]")
    }
}

var signalSources: [DispatchSourceSignal] = []

func runDaemon(_ config: Config) throws {
    let db = try Database(path: config.dbPath)
    let categories = try Categories(db: db)
    let sampler = Sampler(captureTitles: config.captureTitles)
    let recorder = Recorder(db: db, config: config, categories: categories)

    func isPaused() -> Bool {
        var paused = false
        try? db.query("SELECT value FROM meta WHERE key = 'paused'") {
            paused = $0.text(0) == "1"
        }
        return paused
    }

    let timer = DispatchSource.makeTimerSource(queue: .main)
    timer.schedule(deadline: .now(), repeating: config.pollInterval)
    timer.setEventHandler {
        do {
            if isPaused() {
                try recorder.flush()
            } else if let sample = sampler.sample() {
                try recorder.record(sample)
            }
        } catch {
            FileHandle.standardError.write(
                "record error: \(error)\n".data(using: .utf8)!)
        }
    }
    timer.resume()

    // Close the open session cleanly on Ctrl-C / SIGTERM.
    // Sources are held in a global so they stay alive for the process.
    for sig in [SIGINT, SIGTERM] {
        signal(sig, SIG_IGN)
        let source = DispatchSource.makeSignalSource(signal: sig, queue: .main)
        source.setEventHandler {
            try? recorder.flush()
            exit(0)
        }
        source.resume()
        signalSources.append(source)
    }

    FileHandle.standardError.write(
        "screentimed tracking → \(config.dbPath)\n".data(using: .utf8)!)
    dispatchMain()
}

main()
