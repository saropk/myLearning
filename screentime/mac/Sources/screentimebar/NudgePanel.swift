import AppKit

/// The 20-20-20 nudge: a small floating panel in the top-right corner.
/// Non-activating (never steals focus), never modal, auto-dismisses after
/// 60 seconds if ignored.
final class NudgePanel: NSPanel {
    private let onDone: () -> Void
    private let onSnooze: () -> Void
    private let onSkip: () -> Void
    private let onTimeout: () -> Void

    private var countdownLabel: NSTextField!
    private var countdown = 20
    private var countdownTimer: Timer?
    private var timeoutTimer: Timer?

    init(onDone: @escaping () -> Void,
         onSnooze: @escaping () -> Void,
         onSkip: @escaping () -> Void,
         onTimeout: @escaping () -> Void) {
        self.onDone = onDone
        self.onSnooze = onSnooze
        self.onSkip = onSkip
        self.onTimeout = onTimeout

        super.init(
            contentRect: NSRect(x: 0, y: 0, width: 320, height: 150),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered, defer: false)

        isFloatingPanel = true
        level = .floating
        collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        isOpaque = false
        backgroundColor = .clear
        hidesOnDeactivate = false
        isMovableByWindowBackground = true
        isReleasedWhenClosed = false

        contentView = buildContent()
    }

    override var canBecomeKey: Bool { false }

    private func buildContent() -> NSView {
        let effect = NSVisualEffectView()
        effect.material = .hudWindow
        effect.state = .active
        effect.blendingMode = .behindWindow
        effect.wantsLayer = true
        effect.layer?.cornerRadius = 14
        effect.layer?.masksToBounds = true

        let title = NSTextField(labelWithString: "Rest your eyes")
        title.font = .systemFont(ofSize: 15, weight: .semibold)

        let body = NSTextField(
            wrappingLabelWithString:
                "Look at something 20 feet away for 20 seconds.")
        body.font = .systemFont(ofSize: 12)
        body.textColor = .secondaryLabelColor
        body.preferredMaxLayoutWidth = 280

        countdownLabel = NSTextField(labelWithString: "20 s")
        countdownLabel.font = .monospacedDigitSystemFont(ofSize: 22, weight: .light)
        countdownLabel.textColor = .systemTeal

        let done = NSButton(
            title: "I looked away", target: self, action: #selector(doneTapped))
        done.bezelStyle = .rounded
        done.keyEquivalent = "\r"
        let snooze = NSButton(
            title: "Snooze 5 min", target: self, action: #selector(snoozeTapped))
        snooze.bezelStyle = .rounded
        let skip = NSButton(
            title: "Skip", target: self, action: #selector(skipTapped))
        skip.bezelStyle = .rounded

        let buttons = NSStackView(views: [done, snooze, skip])
        buttons.orientation = .horizontal
        buttons.spacing = 8

        let stack = NSStackView(views: [title, body, countdownLabel, buttons])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 8
        stack.edgeInsets = NSEdgeInsets(top: 16, left: 18, bottom: 16, right: 18)
        stack.translatesAutoresizingMaskIntoConstraints = false

        effect.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.topAnchor.constraint(equalTo: effect.topAnchor),
            stack.bottomAnchor.constraint(equalTo: effect.bottomAnchor),
            stack.leadingAnchor.constraint(equalTo: effect.leadingAnchor),
            stack.trailingAnchor.constraint(equalTo: effect.trailingAnchor),
        ])
        return effect
    }

    func show() {
        if let screen = NSScreen.main {
            let visible = screen.visibleFrame
            let size = contentView?.fittingSize ?? frame.size
            setContentSize(size)
            setFrameOrigin(NSPoint(
                x: visible.maxX - size.width - 16,
                y: visible.maxY - size.height - 16))
        }

        alphaValue = 0
        orderFrontRegardless()
        NSAnimationContext.runAnimationGroup { ctx in
            ctx.duration = 0.35
            animator().alphaValue = 1
        }

        countdownTimer = Timer.scheduledTimer(
            withTimeInterval: 1, repeats: true
        ) { [weak self] _ in
            guard let self else { return }
            self.countdown -= 1
            if self.countdown <= 0 {
                self.countdownLabel.stringValue = "✓ that's 20 seconds"
                self.countdownTimer?.invalidate()
            } else {
                self.countdownLabel.stringValue = "\(self.countdown) s"
            }
        }

        timeoutTimer = Timer.scheduledTimer(
            withTimeInterval: 60, repeats: false
        ) { [weak self] _ in
            self?.onTimeout()
        }
    }

    override func close() {
        countdownTimer?.invalidate()
        timeoutTimer?.invalidate()
        NSAnimationContext.runAnimationGroup({ ctx in
            ctx.duration = 0.25
            animator().alphaValue = 0
        }, completionHandler: {
            super.close()
        })
    }

    @objc private func doneTapped() { onDone() }
    @objc private func snoozeTapped() { onSnooze() }
    @objc private func skipTapped() { onSkip() }
}
