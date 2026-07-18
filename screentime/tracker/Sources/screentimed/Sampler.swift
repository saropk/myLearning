import AppKit
import ApplicationServices
import CoreGraphics
import Foundation

struct Sample {
    let date: Date
    let bundleID: String
    let appName: String
    let windowTitle: String?
    /// Seconds since the last keyboard/mouse event, at sample time.
    let idleSeconds: TimeInterval
}

/// Reads the frontmost application and system idle time.
/// Neither requires any permission prompt; window titles (optional,
/// off by default) require Accessibility.
struct Sampler {
    let captureTitles: Bool

    // CGEventType has no importable "any input" case in Swift, so take the
    // minimum across every input event class instead.
    private static let inputEventTypes: [CGEventType] = [
        .keyDown, .flagsChanged, .mouseMoved, .scrollWheel,
        .leftMouseDown, .rightMouseDown, .otherMouseDown,
        .leftMouseDragged, .rightMouseDragged,
    ]

    static func secondsSinceLastInput() -> TimeInterval {
        inputEventTypes
            .map {
                CGEventSource.secondsSinceLastEventType(
                    .hidSystemState, eventType: $0)
            }
            .min() ?? 0
    }

    func sample() -> Sample? {
        guard let app = NSWorkspace.shared.frontmostApplication else {
            return nil
        }
        let bundleID = app.bundleIdentifier ?? "unknown.\(app.processIdentifier)"
        let name = app.localizedName ?? bundleID

        var title: String?
        if captureTitles, AXIsProcessTrusted() {
            title = Sampler.focusedWindowTitle(pid: app.processIdentifier)
        }

        return Sample(
            date: Date(),
            bundleID: bundleID,
            appName: name,
            windowTitle: title,
            idleSeconds: Sampler.secondsSinceLastInput())
    }

    private static func focusedWindowTitle(pid: pid_t) -> String? {
        let appElement = AXUIElementCreateApplication(pid)
        var window: CFTypeRef?
        guard AXUIElementCopyAttributeValue(
            appElement, kAXFocusedWindowAttribute as CFString, &window) == .success,
            let window
        else { return nil }

        var title: CFTypeRef?
        guard AXUIElementCopyAttributeValue(
            window as! AXUIElement, kAXTitleAttribute as CFString, &title) == .success
        else { return nil }
        return title as? String
    }
}
