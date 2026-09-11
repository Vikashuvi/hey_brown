import Cocoa
import WebKit

// ── Local Scheme Handler: Serves bundled assets over brown://app/ without CORS/file:// blocks ──
class LocalSchemeHandler: NSObject, WKURLSchemeHandler {
    let baseDirectory: URL

    init(baseDirectory: URL) {
        self.baseDirectory = baseDirectory
        super.init()
    }

    func webView(_ webView: WKWebView, start urlSchemeTask: WKURLSchemeTask) {
        guard let url = urlSchemeTask.request.url else { return }

        var path = url.path
        if path.isEmpty || path == "/" {
            path = "/index.html"
        }

        let relativePath = path.hasPrefix("/") ? String(path.dropFirst()) : path
        let fileUrl = baseDirectory.appendingPathComponent(relativePath)

        guard FileManager.default.fileExists(atPath: fileUrl.path),
              let data = try? Data(contentsOf: fileUrl) else {
            urlSchemeTask.didFailWithError(NSError(domain: NSURLErrorDomain, code: NSURLErrorFileDoesNotExist, userInfo: nil))
            return
        }

        let mimeType: String
        let ext = fileUrl.pathExtension.lowercased()
        switch ext {
        case "html": mimeType = "text/html"
        case "js": mimeType = "application/javascript"
        case "css": mimeType = "text/css"
        case "svg": mimeType = "image/svg+xml"
        case "png": mimeType = "image/png"
        case "json": mimeType = "application/json"
        case "woff2": mimeType = "font/woff2"
        default: mimeType = "application/octet-stream"
        }

        let response = HTTPURLResponse(
            url: url,
            statusCode: 200,
            httpVersion: "HTTP/1.1",
            headerFields: [
                "Content-Type": mimeType,
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "no-cache"
            ]
        )!

        urlSchemeTask.didReceive(response)
        urlSchemeTask.didReceive(data)
        urlSchemeTask.didFinish()
    }

    func webView(_ webView: WKWebView, stop urlSchemeTask: WKURLSchemeTask) {}
}

class AppDelegate: NSObject, NSApplicationDelegate, WKScriptMessageHandler, WKNavigationDelegate {
    var statusItem: NSStatusItem!
    var overlayPanel: NSPanel!
    var webView: WKWebView!
    var statusMenuItem: NSMenuItem!
    var currentState: String = "IDLE"
    var isConnected: Bool = false
    var wsTask: URLSessionWebSocketTask?
    var offlineTimer: Timer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Enforce single instance: prevent two menu bar icons
        let bundleID = Bundle.main.bundleIdentifier ?? "com.brown.desktop"
        let others = NSRunningApplication.runningApplications(withBundleIdentifier: bundleID).filter { $0.processIdentifier != getpid() }
        if !others.isEmpty {
            print("[BrownNative] Another instance is already running (PID: \(others.first!.processIdentifier)). Exiting duplicate.")
            NSApp.terminate(nil)
            return
        }

        setupStatusItem()
        setupOverlayPanel()
        loadWebContent()
        connectNativeWebSocket()
    }

    // ── 1. macOS Menu Bar Setup ──────────────────────────────────────────
    private func setupStatusItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        updateStatusItemIcon(state: "IDLE")

        let menu = NSMenu()
        statusMenuItem = NSMenuItem(title: "Brown: Idle", action: nil, keyEquivalent: "")
        statusMenuItem.isEnabled = false
        menu.addItem(statusMenuItem)

        menu.addItem(NSMenuItem.separator())

        let wakeItem = NSMenuItem(title: "Wake Brown", action: #selector(wakeBrown), keyEquivalent: "w")
        wakeItem.target = self
        menu.addItem(wakeItem)

        let reloadItem = NSMenuItem(title: "Reload Overlay", action: #selector(reloadOverlay), keyEquivalent: "r")
        reloadItem.target = self
        menu.addItem(reloadItem)

        menu.addItem(NSMenuItem.separator())

        let quitItem = NSMenuItem(title: "Quit Brown", action: #selector(quitApp), keyEquivalent: "q")
        quitItem.target = self
        menu.addItem(quitItem)

        statusItem.menu = menu
    }

    private func updateStatusItemIcon(state: String) {
        guard let button = statusItem.button else { return }

        let size = NSSize(width: 18, height: 18)
        let image = NSImage(size: size, flipped: false) { rect in
            let path = NSBezierPath(ovalIn: NSRect(x: 2, y: 2, width: 14, height: 14))

            if state == "OFFLINE" {
                NSColor.systemGray.setFill()
            } else if state == "LISTENING" || state == "WAKE_DETECTED" || state == "SPEAKING" {
                // Luminous top violet glow
                NSColor(calibratedRed: 0.95, green: 0.79, blue: 1.0, alpha: 1.0).setFill()
            } else {
                // Built-in default violet jelly (#cb84f5)
                NSColor(calibratedRed: 0.80, green: 0.52, blue: 0.96, alpha: 1.0).setFill()
            }
            path.fill()

            // Draw two tiny expressive eyes
            let eyeColor = (state == "OFFLINE") ? NSColor.darkGray : NSColor(calibratedRed: 0.09, green: 0.05, blue: 0.15, alpha: 0.95)
            eyeColor.setFill()

            let leftEye = NSBezierPath(ovalIn: NSRect(x: 5.5, y: 7.5, width: 2.2, height: 2.2))
            let rightEye = NSBezierPath(ovalIn: NSRect(x: 10.3, y: 7.5, width: 2.2, height: 2.2))
            leftEye.fill()
            rightEye.fill()

            return true
        }

        image.isTemplate = false
        button.image = image

    }

    // ── 2. Floating Transparent Overlay Setup ────────────────────────────
    private func setupOverlayPanel() {
        let width: CGFloat = 280
        let height: CGFloat = 380

        let initialRect = NSRect(x: 0, y: 0, width: width, height: height)


        overlayPanel = NSPanel(
            contentRect: initialRect,
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )

        overlayPanel.isOpaque = false
        overlayPanel.backgroundColor = .clear
        overlayPanel.hasShadow = false
        overlayPanel.level = .statusBar
        overlayPanel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
        overlayPanel.ignoresMouseEvents = false
        overlayPanel.hidesOnDeactivate = false
        overlayPanel.alphaValue = 0.0 // starts invisible until wake

        // WebKit Configuration with custom URL scheme to bypass file:// CORS
        let config = WKWebViewConfiguration()

        let distDir = resolveDistDirectory()
        let schemeHandler = LocalSchemeHandler(baseDirectory: distDir)
        config.setURLSchemeHandler(schemeHandler, forURLScheme: "brown")

        let userContent = WKUserContentController()
        userContent.add(self, name: "brownNative")
        config.userContentController = userContent

        config.preferences.setValue(true, forKey: "developerExtrasEnabled")

        webView = WKWebView(frame: NSRect(x: 0, y: 0, width: width, height: height), configuration: config)
        webView.navigationDelegate = self
        webView.setValue(false, forKey: "drawsBackground")
        if #available(macOS 12.0, *) {
            webView.underPageBackgroundColor = .clear
        }
        webView.autoresizingMask = [.width, .height]

        overlayPanel.contentView = webView
    }

    private func resolveDistDirectory() -> URL {
        if let resUrl = Bundle.main.resourceURL?.appendingPathComponent("ui/dist"),
           FileManager.default.fileExists(atPath: resUrl.path) {
            return resUrl
        }
        let execPath = Bundle.main.bundlePath
        let projectRoot = URL(fileURLWithPath: execPath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        return projectRoot.appendingPathComponent("ui/dist")
    }

    // ── 3. Content Loading ────────────────────────────────────────────────
    private func loadWebContent() {
        if let appUrl = URL(string: "brown://app/index.html") {
            webView.load(URLRequest(url: appUrl))
        }
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        print("[BrownNative] Web content loaded successfully over brown://app/index.html")
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        print("[BrownNative] Failed to load web content: \(error.localizedDescription)")
    }

    // ── 4. Native WebSocket Connection (Direct Core State Sync) ───────────
    private func connectNativeWebSocket() {
        guard let url = URL(string: "ws://127.0.0.1:8766") else { return }
        let session = URLSession(configuration: .default)
        wsTask = session.webSocketTask(with: url)
        wsTask?.resume()
        receiveWebSocketMessage()
    }

    private func receiveWebSocketMessage() {
        wsTask?.receive { [weak self] result in
            switch result {
            case .success(let message):
                switch message {
                case .string(let text):
                    if let data = text.data(using: .utf8),
                       let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                       let event = json["event"] as? String {
                        DispatchQueue.main.async {
                            self?.handleCoreEvent(event: event, data: json["data"] as? [String: Any] ?? [:])
                        }
                    }
                default: break
                }
                self?.receiveWebSocketMessage()
            case .failure:
                DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
                    self?.connectNativeWebSocket()
                }
            }
        }
    }

    private func handleCoreEvent(event: String, data: [String: Any]) {
        if event == "state_change" {
            let state = (data["state"] as? String ?? "").uppercased()
            handleStateTransition(state: state, payload: data)
        } else if event == "tts_speaking" {
            let isSpeaking = (data["speaking"] as? Bool) ?? false
            if isSpeaking {
                handleStateTransition(state: "SPEAKING", payload: data)
            }
        }
    }

    // ── 5. Repositioning Overlay to Active Screen Top-Right ───────────────
    private func positionOverlay() {
        let mouseLocation = NSEvent.mouseLocation
        let targetScreen = NSScreen.screens.first(where: { NSMouseInRect(mouseLocation, $0.frame, false) }) ?? NSScreen.main ?? NSScreen.screens[0]

        let visibleFrame = targetScreen.visibleFrame
        let panelWidth = overlayPanel.frame.width
        let panelHeight = overlayPanel.frame.height

        let targetX = visibleFrame.maxX - panelWidth - 18
        let targetY = visibleFrame.maxY - panelHeight - 6

        overlayPanel.setFrameOrigin(NSPoint(x: targetX, y: targetY))
    }

    // ── 6. Script Message Handler (from React / feral-blob) ──────────────
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "brownNative",
              let body = message.body as? [String: Any],
              let state = body["state"] as? String else {
            return
        }

        DispatchQueue.main.async { [weak self] in
            self?.handleStateTransition(state: state, payload: body)
        }
    }

    private func handleStateTransition(state: String, payload: [String: Any]) {
        currentState = state
        updateStatusItemIcon(state: state)

        let formattedState = state.replacingOccurrences(of: "_", with: " ").capitalized
        statusMenuItem.title = "Brown: \(formattedState)"

        if state == "OFFLINE" {
            // Dismiss overlay after 12s if still offline
            offlineTimer?.invalidate()
            offlineTimer = Timer.scheduledTimer(withTimeInterval: 12.0, repeats: false) { [weak self] _ in
                if self?.currentState == "OFFLINE" {
                    NSAnimationContext.runAnimationGroup({ context in
                        context.duration = 0.35
                        self?.overlayPanel.animator().alphaValue = 0.0
                    }, completionHandler: {
                        self?.overlayPanel.orderOut(nil)
                    })
                }
            }
        } else if state == "IDLE" || state == "SLEEPING" {
            offlineTimer?.invalidate()
            // Smooth fade out back to menu bar presence
            NSAnimationContext.runAnimationGroup({ context in
                context.duration = 0.35
                overlayPanel.animator().alphaValue = 0.0
            }, completionHandler: { [weak self] in
                if self?.currentState == "IDLE" || self?.currentState == "SLEEPING" {
                    self?.overlayPanel.orderOut(nil)
                }
            })
        } else {
            offlineTimer?.invalidate()
            // Active state: position near top right and fade in
            positionOverlay()
            overlayPanel.orderFrontRegardless()
            NSAnimationContext.runAnimationGroup({ context in
                context.duration = 0.22
                overlayPanel.animator().alphaValue = 1.0
            })
        }

    }

    // ── 7. Menu Actions ──────────────────────────────────────────────────
    @objc func wakeBrown() {
        webView.evaluateJavaScript("window.dispatchEvent(new CustomEvent('brown-wake'))") { _, _ in }
        handleStateTransition(state: "WAKE_DETECTED", payload: [:])
    }

    @objc func reloadOverlay() {
        loadWebContent()
    }

    @objc func quitApp() {
        NSApplication.shared.terminate(nil)
    }
}

// ── Main Entrypoint ──────────────────────────────────────────────────────
let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory) // Menu-bar accessory (no Dock icon)
app.run()
