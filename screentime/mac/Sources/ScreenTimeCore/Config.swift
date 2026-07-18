import Foundation

public struct Config {
    /// Seconds between frontmost-app samples.
    public var pollInterval: TimeInterval = 2.0
    /// Seconds of no input before the user counts as idle.
    public var idleThreshold: TimeInterval = 120.0
    /// Window-title capture is off by default: titles are sensitive and
    /// capturing them requires the Accessibility permission.
    public var captureTitles = false
    public var dbPath: String = Config.defaultDBPath

    public init() {}

    public static var defaultDBPath: String {
        let appSupport = FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask)[0]
        return appSupport
            .appendingPathComponent("ScreenTime/screentime.sqlite3").path
    }

    /// Parses flags shared by all subcommands. Returns unconsumed arguments.
    public static func parse(_ args: [String]) throws -> (Config, [String]) {
        var config = Config()
        var rest: [String] = []
        var i = 0
        while i < args.count {
            let arg = args[i]
            func value(_ flag: String) throws -> String {
                i += 1
                guard i < args.count else {
                    throw UsageError("missing value for \(flag)")
                }
                return args[i]
            }
            switch arg {
            case "--db":
                config.dbPath = try value(arg)
            case "--interval":
                guard let v = TimeInterval(try value(arg)), v >= 0.5 else {
                    throw UsageError("--interval must be a number >= 0.5")
                }
                config.pollInterval = v
            case "--idle-threshold":
                guard let v = TimeInterval(try value(arg)), v >= 5 else {
                    throw UsageError("--idle-threshold must be a number >= 5")
                }
                config.idleThreshold = v
            case "--capture-titles":
                config.captureTitles = true
            default:
                rest.append(arg)
            }
            i += 1
        }
        return (config, rest)
    }
}

public struct UsageError: Error, CustomStringConvertible {
    public let message: String
    public init(_ message: String) { self.message = message }
    public var description: String { message }
}
