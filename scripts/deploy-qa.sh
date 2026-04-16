#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Bundle mode: build the DeployQA macOS app
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--bundle" ]]; then
    APP_NAME="DeployQA"
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    BUILD_DIR="${SCRIPT_DIR}/build"
    APP_DIR="${BUILD_DIR}/${APP_NAME}.app"
    MACOS_DIR="${APP_DIR}/Contents/MacOS"
    RESOURCES_DIR="${APP_DIR}/Contents/Resources"
    SCRIPT_PATH="${SCRIPT_DIR}/$(basename "$0")"

    echo "Building $APP_NAME..."

    # 1. Create the standard macOS app directory structure
    mkdir -p "$MACOS_DIR" "$RESOURCES_DIR"

    # 2. Embed this script into the app bundle so the Swift app can call it
    cp "$SCRIPT_PATH" "$RESOURCES_DIR/deploy-qa.sh"
    chmod +x "$RESOURCES_DIR/deploy-qa.sh"

    # 3. Write the SwiftUI code to a temporary file
    cat << 'SWIFT_EOF' > "${BUILD_DIR}/DeployApp.swift"
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

        // Locate the bundled deploy-qa.sh inside the app's Resources
        guard let scriptURL = Bundle.main.url(forResource: "deploy-qa", withExtension: "sh") else {
            logs += "Error: Could not find bundled deploy-qa.sh\n"
            isDeploying = false
            return
        }

        DispatchQueue.global(qos: .userInitiated).async {
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/bin/bash")
            process.arguments = [scriptURL.path, "--yes", sanitizedPR]

            // Inject credentials and git auth config into the environment
            var env = ProcessInfo.processInfo.environment
            env["PATH"] = "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
            env["GITHUB_USERNAME"] = self.githubUsername
            env["GITHUB_TOKEN"] = self.githubToken
            env["GIT_TERMINAL_PROMPT"] = "0"
            env["GIT_CONFIG_COUNT"] = "4"
            env["GIT_CONFIG_KEY_0"] = "url.https://\(self.githubUsername):\(self.githubToken)@github.com/.insteadOf"
            env["GIT_CONFIG_VALUE_0"] = "https://github.com/"
            env["GIT_CONFIG_KEY_1"] = "credential.helper"
            env["GIT_CONFIG_VALUE_1"] = ""
            env["GIT_CONFIG_KEY_2"] = "user.name"
            env["GIT_CONFIG_VALUE_2"] = self.githubUsername
            env["GIT_CONFIG_KEY_3"] = "user.email"
            env["GIT_CONFIG_VALUE_3"] = "\(self.githubUsername)@users.noreply.github.com"
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

    # 4. Compile the Swift code into the app bundle executable
    swiftc "${BUILD_DIR}/DeployApp.swift" -parse-as-library -o "$MACOS_DIR/$APP_NAME" || { echo "Compilation failed! Aborting."; rm "${BUILD_DIR}/DeployApp.swift"; exit 1; }
    rm "${BUILD_DIR}/DeployApp.swift"

    # 5. Create an Info.plist so macOS recognizes it as a real GUI application
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

    # 6. Zip it for distribution
    (cd "${BUILD_DIR}" && zip -r -q "${APP_NAME}.zip" "${APP_NAME}.app")

    echo "Done! You can now send scripts/build/${APP_NAME}.zip to the QA team."
    exit 0
fi

# =============================================================================
# Configuration — adjust these variables as needed
# =============================================================================
MAIN_ORG="boostorg"
MAIN_REPO="website-v2"
QA_ORG="cppalliance"
QA_REPO="website-v2-qa"
TARGET_QA_BRANCH="cppal-dev"            # the important branch we merge/reset into

MAIN_REMOTE_NAME="upstream"   # name given to the mainorg/mainrepo remote locally
QA_REMOTE_URL="https://github.com/${QA_ORG}/${QA_REPO}.git"
MAIN_REMOTE_URL="https://github.com/${MAIN_ORG}/${MAIN_REPO}.git"

QA_ROOT="${HOME}/qa-automation"
WORK_DIR="${QA_ROOT}/${QA_ORG}/${QA_REPO}"
# =============================================================================

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <PR_NUMBER>

Check out a pull request from ${MAIN_ORG}/${MAIN_REPO} and apply it to the
local '${TARGET_QA_BRANCH}' branch in ${QA_ORG}/${QA_REPO}.

Arguments:
  PR_NUMBER          The pull request number from ${MAIN_ORG}/${MAIN_REPO}

Options:
  --bundle           Build the DeployQA macOS GUI app and exit.
  --yes              Skip the confirmation prompt before force-pushing.
  --verbose          Show Git error/warning messages (suppressed by default).
  --help             Show this help message and exit.

Workflow:
  1. Ensures \$HOME/qa-automation directory structure exists and the repo is cloned.
  2. Fetches the PR from ${MAIN_ORG}/${MAIN_REPO} into a local tracking branch.
  3. Switches to '${TARGET_QA_BRANCH}'.
  4. Hard-resets '${TARGET_QA_BRANCH}' to the PR commit SHA, then force-pushes
     to origin.
  5. Prompts before force-pushing so you stay in control.

Examples:
  $(basename "$0") 42              # Hard-reset + force-push PR #42
  $(basename "$0") --bundle        # Build the DeployQA macOS app
EOF
}

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
PUSH_AUTO=false
VERBOSE=false
PR_NUMBER=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            usage
            exit 0
            ;;
        --yes)
            PUSH_AUTO=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        -*)
            echo "Error: Unknown option '$1'" >&2
            echo "Run '$(basename "$0") --help' for usage." >&2
            exit 1
            ;;
        *)
            if [[ -n "$PR_NUMBER" ]]; then
                echo "Error: Unexpected extra argument '$1'" >&2
                echo "Run '$(basename "$0") --help' for usage." >&2
                exit 1
            fi
            PR_NUMBER="$1"
            shift
            ;;
    esac
done

if [[ -z "$PR_NUMBER" ]]; then
    echo "Error: PR_NUMBER is required." >&2
    echo "Run '$(basename "$0") --help' for usage." >&2
    exit 1
fi

if ! [[ "$PR_NUMBER" =~ ^[0-9]+$ ]]; then
    echo "Error: PR_NUMBER must be a positive integer (got '${PR_NUMBER}')." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Error redirection setup
# ---------------------------------------------------------------------------
if [[ "$VERBOSE" == true ]]; then
    ERR_REDIRECT=""
else
    ERR_REDIRECT="2>/dev/null"
fi

# ---------------------------------------------------------------------------
# Helper: ensure the working repo exists
# ---------------------------------------------------------------------------
ensure_repo() {
    mkdir -p "${QA_ROOT}"

    if [[ ! -d "${WORK_DIR}/.git" ]]; then
        echo "==> Cloning ${QA_ORG}/${QA_REPO} into ${WORK_DIR} …"
        mkdir -p "$(dirname "${WORK_DIR}")"
        eval "git clone \"${QA_REMOTE_URL}\" \"${WORK_DIR}\" ${ERR_REDIRECT}"
    fi

    cd "${WORK_DIR}"

    # Make sure the upstream remote exists
    if ! git remote get-url "${MAIN_REMOTE_NAME}" &>/dev/null; then
        echo "==> Adding remote '${MAIN_REMOTE_NAME}' → ${MAIN_REMOTE_URL}"
        eval "git remote add \"${MAIN_REMOTE_NAME}\" \"${MAIN_REMOTE_URL}\" ${ERR_REDIRECT}"
    fi
}

# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------
ensure_repo
cd "${WORK_DIR}"

PR_REF="refs/pull/${PR_NUMBER}/head"
LOCAL_PR_BRANCH="pr/${PR_NUMBER}"

echo "==> Switching to '${TARGET_QA_BRANCH}' before fetching ..."
if git show-ref --quiet "refs/heads/${TARGET_QA_BRANCH}"; then
    eval "git checkout \"${TARGET_QA_BRANCH}\" ${ERR_REDIRECT}"

    # Check if local branch has diverged from remote (rebased scenario)
    if git ls-remote --exit-code origin "refs/heads/${TARGET_QA_BRANCH}" &>/dev/null; then
        # Get the commit SHAs for comparison
        LOCAL_SHA=$(git rev-parse "HEAD")
        REMOTE_SHA=$(git rev-parse "origin/${TARGET_QA_BRANCH}" 2>/dev/null || echo "")

        if [[ -n "$REMOTE_SHA" && "$LOCAL_SHA" != "$REMOTE_SHA" ]]; then
            echo "==> Local branch has diverged from remote (likely rebased). Resetting to remote..."
            eval "git reset --hard \"origin/${TARGET_QA_BRANCH}\" ${ERR_REDIRECT}"
        fi
    fi
else
    if git ls-remote --exit-code origin "refs/heads/${TARGET_QA_BRANCH}" &>/dev/null; then
        eval "git checkout -b \"${TARGET_QA_BRANCH}\" \"origin/${TARGET_QA_BRANCH}\" ${ERR_REDIRECT}"
    else
        eval "git checkout -b \"${TARGET_QA_BRANCH}\" ${ERR_REDIRECT}"
    fi
fi

echo "==> Fetching PR #${PR_NUMBER} from ${MAIN_REMOTE_NAME} …"
eval "git fetch \"${MAIN_REMOTE_NAME}\" \"${PR_REF}:${LOCAL_PR_BRANCH}\" ${ERR_REDIRECT}"

PR_SHA=$(git rev-parse "${LOCAL_PR_BRANCH}")
echo "    PR commit SHA: ${PR_SHA}"

echo "==> Hard-resetting '${TARGET_QA_BRANCH}' to PR commit ${PR_SHA} …"
eval "git reset --hard \"${PR_SHA}\" ${ERR_REDIRECT}"

SHOULD_PUSH=false
if [[ "$PUSH_AUTO" == true ]]; then
    SHOULD_PUSH=true
else
    printf "\nForce push the PR to the branch '%s'? (y/n) " "${TARGET_QA_BRANCH}"
    read -r ANSWER
    if [[ "$ANSWER" =~ ^[Yy]$ ]]; then
        SHOULD_PUSH=true
    fi
fi

if [[ "$SHOULD_PUSH" == true ]]; then
    echo "==> Force-pushing to origin/${TARGET_QA_BRANCH} …"
    eval "git push --force origin \"${TARGET_QA_BRANCH}\" ${ERR_REDIRECT}"
    echo "Done."
else
    echo "Force push skipped."
fi
