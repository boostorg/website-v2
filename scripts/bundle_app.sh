#!/bin/bash

APP_NAME="DeployQA"
APP_DIR="${APP_NAME}.app"
MACOS_DIR="${APP_DIR}/Contents/MacOS"

echo "Building $APP_NAME..."

# 1. Create the standard macOS app directory structure
mkdir -p "$MACOS_DIR"

# 2. Write the SwiftUI code to a temporary file
cat << 'SWIFT_EOF' > DeployApp.swift
import SwiftUI
import AppKit

@main
struct DeployApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .commands { CommandGroup(replacing: .newItem) { } }
    }
}

struct ContentView: View {
    @State private var prNumber: String = ""
    @State private var logs: String = "Ready to deploy. Enter a PR number above.\n"
    @State private var isDeploying: Bool = false
    @State private var deploymentFinished: Bool = false

    // Persist credentials in macOS UserDefaults
    @AppStorage("githubUsername") var githubUsername: String = ""
    @AppStorage("githubToken") var githubToken: String = ""

    @State private var showSettings: Bool = false

    var body: some View {
        VStack(spacing: 0) {
            // TOP: Controls
            HStack {
                TextField("PR number (e.g., 2240)", text: $prNumber)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .disabled(isDeploying)
                    .frame(width: 200)

                Button("Deploy") {
                    startDeployment()
                }
                .disabled(isDeploying || prNumber.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || githubUsername.isEmpty || githubToken.isEmpty)
                .keyboardShortcut(.defaultAction)

                Spacer()

                if isDeploying {
                    ProgressView()
                        .scaleEffect(0.5)
                        .padding(.trailing, 5)
                }

                Button(action: { showSettings = true }) {
                    Image(systemName: "gearshape.fill")
                        .foregroundColor(.secondary)
                }
                .disabled(isDeploying)
                .buttonStyle(PlainButtonStyle())
                .help("Update GitHub Credentials")
                .padding(.leading, 10)
            }
            .padding()
            .background(Color(NSColor.windowBackgroundColor))

            // MIDDLE: Real-time logs
            ScrollView {
                Text(logs)
                    .font(.system(.caption, design: .monospaced))
                    .frame(maxWidth: .infinity, alignment: .topLeading)
                    .padding()
            }
            .background(Color.black.opacity(0.85))
            .foregroundColor(.green)
            .frame(minHeight: 250)

            // BOTTOM: Actions
            if deploymentFinished {
                HStack(spacing: 20) {
                    Text("Deployment Complete!")
                        .fontWeight(.bold)

                    Button("Check GitHub Actions") {
                        NSWorkspace.shared.open(URL(string: "https://github.com/cppalliance/website-v2-qa/actions")!)
                    }
                    Button("Open Website") {
                        NSWorkspace.shared.open(URL(string: "https://www.cppal-dev.boost.org/")!)
                    }
                }
                .padding()
                .background(Color(NSColor.windowBackgroundColor))
            }
        }
        .frame(width: 600, height: 450)
        .onAppear {
            if githubUsername.isEmpty || githubToken.isEmpty {
                showSettings = true
            }
        }
        .sheet(isPresented: $showSettings) {
            SettingsView(isPresented: $showSettings)
        }
    }

    func startDeployment() {
        isDeploying = true
        deploymentFinished = false

        let sanitizedPR = prNumber.replacingOccurrences(of: "#", with: "").trimmingCharacters(in: .whitespacesAndNewlines)
        logs = "Starting deployment for PR #\(sanitizedPR)...\n\n"

        let script = #"""
        export PATH=/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin
        export PROJECT_DIR="$HOME/projects/cpp_alliance/qa"
        export REPO_DIR="$PROJECT_DIR/website-v2"

        # --- THE HEADLESS GIT AUTHENTICATION FIX ---
        # 1. Prevent Git from trying to open a terminal prompt (which crashes the app)
        export GIT_TERMINAL_PROMPT=0

        # 2. Inject configuration securely via environment variables (inherited by deploy-qa.sh)
        export GIT_CONFIG_COUNT=4
        # Rewrite all GitHub URLs to use the Token automatically
        export GIT_CONFIG_KEY_0="url.https://${GITHUB_USERNAME}:${GITHUB_TOKEN}@github.com/.insteadOf"
        export GIT_CONFIG_VALUE_0="https://github.com/"
        # Completely disable the macOS Keychain credential helper so it ignores revoked tokens
        export GIT_CONFIG_KEY_1="credential.helper"
        export GIT_CONFIG_VALUE_1=""
        # Set committer info just in case a rebase/merge is triggered
        export GIT_CONFIG_KEY_2="user.name"
        export GIT_CONFIG_VALUE_2="${GITHUB_USERNAME}"
        export GIT_CONFIG_KEY_3="user.email"
        export GIT_CONFIG_VALUE_3="${GITHUB_USERNAME}@users.noreply.github.com"
        # ---------------------------------------------

        mkdir -p "$PROJECT_DIR"

        # Check for the .git folder specifically. If they still have the old unzipped version, trash it.
        if [ ! -d "$REPO_DIR/.git" ]; then
            echo "Cleaning up legacy unzipped folder..."
            rm -rf "$REPO_DIR"
            echo "Cloning 'develop' branch natively..."
            # The env vars above automatically handle the authentication for this!
            git clone -b develop "https://github.com/boostorg/website-v2.git" "$REPO_DIR"
        else
            echo "Repository already exists. Updating..."
            cd "$REPO_DIR" || exit 1
            git checkout develop
            git pull origin develop
        fi

        cd "$REPO_DIR/scripts" || { echo "Error: scripts directory not found."; exit 1; }

        echo "Executing: ./deploy-qa.sh \"\#(sanitizedPR)\" --yes --verbose"
        echo "----------------------------------------"

        # Run the deployment script natively. All inner git commands will inherit the Auth Env Vars.
        ./deploy-qa.sh "\#(sanitizedPR)" --yes --verbose 2>&1
        """#

        DispatchQueue.global(qos: .userInitiated).async {
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/bin/bash")
            process.arguments = ["-c", script]

            // Inject the credentials securely into the script's environment
            var env = ProcessInfo.processInfo.environment
            env["GITHUB_USERNAME"] = self.githubUsername
            env["GITHUB_TOKEN"] = self.githubToken
            process.environment = env

            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = pipe

            pipe.fileHandleForReading.readabilityHandler = { handle in
                let data = handle.availableData
                if data.isEmpty { return }
                if let str = String(data: data, encoding: .utf8) {
                    DispatchQueue.main.async {
                        self.logs += str
                    }
                }
            }

            do {
                try process.run()
                process.waitUntilExit()

                DispatchQueue.main.async {
                    self.isDeploying = false
                    self.deploymentFinished = true
                    self.logs += "\n----------------------------------------\n"
                    self.logs += "Process finished with exit code: \(process.terminationStatus)\n"
                }
            } catch {
                DispatchQueue.main.async {
                    self.isDeploying = false
                    self.logs += "\nError starting process: \(error.localizedDescription)\n"
                }
            }
            pipe.fileHandleForReading.readabilityHandler = nil
        }
    }
}

struct SettingsView: View {
    @Binding var isPresented: Bool
    @AppStorage("githubUsername") var githubUsername: String = ""
    @AppStorage("githubToken") var githubToken: String = ""

    @State private var tempUser: String = ""
    @State private var tempToken: String = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 15) {
            Text("GitHub Credentials")
                .font(.headline)
            Text("Please enter your GitHub credentials. These are required to trigger the deployment and will be saved securely on your Mac.")
                .font(.caption)
                .foregroundColor(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            TextField("GitHub Username", text: $tempUser)
                .textFieldStyle(RoundedBorderTextFieldStyle())
                .disableAutocorrection(true)

            SecureField("Personal Access Token", text: $tempToken)
                .textFieldStyle(RoundedBorderTextFieldStyle())

            HStack {
                Spacer()
                Button("Cancel") {
                    isPresented = false
                }
                .keyboardShortcut(.cancelAction)

                Button("Save") {
                    githubUsername = tempUser.trimmingCharacters(in: .whitespacesAndNewlines)
                    githubToken = tempToken.trimmingCharacters(in: .whitespacesAndNewlines)
                    isPresented = false
                }
                .disabled(tempUser.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || tempToken.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                .keyboardShortcut(.defaultAction)
            }
            .padding(.top, 10)
        }
        .padding()
        .frame(width: 400)
        .onAppear {
            tempUser = githubUsername
            tempToken = githubToken
        }
    }
}
SWIFT_EOF

# 3. Compile the Swift code into the app bundle executable
swiftc DeployApp.swift -parse-as-library -o "$MACOS_DIR/$APP_NAME" || { echo "Compilation failed! Aborting."; rm DeployApp.swift; exit 1; }
rm DeployApp.swift

# 4. Create an Info.plist so macOS recognizes it as a real GUI application
cat << 'PLIST_EOF' > "${APP_DIR}/Contents/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>DeployQA</string>
    <key>CFBundleIdentifier</key>
    <string>com.cppalliance.deployqa</string>
    <key>CFBundleName</key>
    <string>DeployQA</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
</dict>
</plist>
PLIST_EOF

# 5. Zip it for distribution
zip -r -q "${APP_NAME}.zip" "${APP_DIR}"

echo "Done! You can now send ${APP_NAME}.zip to the QA team."
