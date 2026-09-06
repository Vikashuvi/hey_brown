# Brown — Personal AI Computer Assistant
## Master Problem Statement, Architecture, Capabilities & Implementation Specification

> **Purpose:** This document is the master specification for building **Brown**, a voice-first personal AI assistant that can reason about tasks, choose efficient ways to accomplish them, safely operate two computers, use browsers and external AI services, work with files/projects, and communicate results naturally through voice.

---

## 1. Vision

Build a personal AI assistant called **Brown**, inspired by the concept of JARVIS.

Brown should not behave like a normal text chatbot. The primary interaction should be:

**Voice → Understanding → Planning → Action → Verification → Natural voice response**

Brown should be able to understand a goal, inspect the available environment, decide the most efficient and reliable way to accomplish it, execute the required actions through controlled tools, verify the result, and report back naturally.

The important concept is:

> **Do not teach Brown only how to execute commands. Teach Brown how to choose the best workflow for accomplishing a user's goal.**

---

# 2. Devices

## Paperball

Primary computer:

- Intel-based MacBook Pro
- macOS
- Voice interface / microphone / speaker
- macOS device agent
- Browser automation endpoint
- General desktop control

## Error Boy

Secondary computer:

- HP Victus
- Arch Linux
- Potential local AI inference machine
- Linux device agent
- Browser automation endpoint
- Heavier computation where hardware permits

**Important:** Do not assume Error Boy's exact CPU, GPU, VRAM, or RAM. Inspect the actual machine before selecting a local model.

---

# 3. High-Level Architecture

```text
                         ┌─────────────────────────┐
                         │          BROWN          │
                         │                         │
                         │ Voice / Context         │
                         │ Planning / Reasoning    │
                         │ Task Decomposition      │
                         │ Tool Selection          │
                         │ Memory / Preferences   │
                         │ Verification           │
                         └────────────┬────────────┘
                                      │
                              Secure communication
                                      │
                   ┌──────────────────┴──────────────────┐
                   │                                     │
          ┌────────▼────────┐                   ┌────────▼────────┐
          │    Paperball    │                   │    Error Boy    │
          │    macOS Agent  │                   │    Linux Agent  │
          └────────┬────────┘                   └────────┬────────┘
                   │                                     │
             OS / Apps / Browser                    OS / Apps / Browser
                   │                                     │
                   └──────────────────┬──────────────────┘
                                      │
                              External services
                                      │
                   ┌──────────────────┼──────────────────┐
                   │                  │                  │
                Gemini            ChatGPT          Other services
                                      │
                               Browser automation
                                      │
                                   Results
                                      │
                              Brown verifies,
                             interprets & speaks
```

Brown must **not** have unrestricted operating-system access.

The AI should request actions through typed, validated tools.

---

# 4. Core Design Principle: Goal-Oriented Agent

Brown should operate at the level of **goals**, not just commands.

For example:

> "Convert all the images in this folder to WebP."

Brown should not immediately assume that browser automation is necessary.

It should reason:

1. Where is the folder?
2. What files are present?
3. What are their current formats?
4. Is there a local conversion utility available?
5. Can the conversion be performed locally?
6. Is there a quality-preserving and efficient command-line/library solution?
7. How many files are there?
8. Is batch processing possible?
9. Is an external website actually beneficial?
10. What output format/options are required?
11. Should originals be preserved?
12. Are there naming conflicts?
13. How can the output be verified?

If a local script can process 500 files in seconds, Brown should prefer that over uploading 500 files individually to a website.

This is the intended meaning of:

> **Brown should think like a human and choose the efficient method.**

---

# 5. Task Planning Loop

For complex tasks Brown should use:

```text
USER GOAL
   ↓
UNDERSTAND
   ↓
INSPECT ENVIRONMENT
   ↓
DECOMPOSE TASK
   ↓
GENERATE POSSIBLE METHODS
   ↓
COMPARE METHODS
   ↓
SELECT BEST METHOD
   ↓
CHECK PERMISSIONS / RISKS
   ↓
EXECUTE
   ↓
VERIFY RESULT
   ↓
RECOVER IF NECESSARY
   ↓
REPORT NATURALLY
```

The planning system should consider:

- Time
- Reliability
- Output quality
- Privacy
- Cost
- Complexity
- Number of files/items
- Availability of local tools
- Availability of APIs
- Browser automation reliability
- Whether human confirmation is required

---

# 6. Method Selection / Efficiency Engine

For a task, Brown should consider multiple possible approaches.

For example:

### Method A — Local script

Advantages:

- Fast
- Private
- Batch-friendly
- Repeatable
- Usually reliable

### Method B — Local application

Advantages:

- May provide better quality/control
- Useful when a specialised application is installed

### Method C — API

Advantages:

- Structured
- Usually more reliable than UI automation
- Easy to automate at scale

### Method D — Browser automation

Advantages:

- Works when no suitable local API/tool exists
- Can operate websites like a human

Disadvantages:

- Slower
- UI can change
- Authentication/session problems
- More fragile

### Method E — Manual interaction

Use only when automation cannot safely or reliably accomplish the task.

Brown should select the best method rather than blindly using the browser.

---

# 7. Example: Batch File Conversion

User:

> "Hey Brown, there are a bunch of PNG files in my project folder. Convert all of them to WebP."

Brown should potentially reason:

```text
Find project
   ↓
Inspect files
   ↓
Count images
   ↓
Check available conversion tools
   ↓
Determine requested quality/settings
   ↓
Choose local batch conversion
   ↓
Generate/use a safe script
   ↓
Execute
   ↓
Verify output
   ↓
Report
```

For example, Brown may create a temporary script using an installed image-processing library/tool rather than opening a website 100 times.

Brown should prefer local processing when:

- The task is deterministic.
- A suitable local tool exists.
- The data is private.
- The number of files is large.
- Local processing is faster.
- The requested output can be produced reliably.

If a specialised website provides substantially better output, Brown can consider it.

However, uploading private files to a website should require appropriate privacy handling and potentially confirmation.

---

# 8. Script Generation

Brown should be capable of creating scripts when that is the most efficient method.

Example:

> "Rename all these files based on their creation date."

Brown could:

1. Inspect the directory.
2. Determine the required naming convention.
3. Generate a temporary script.
4. Perform a dry run.
5. Show/summarise what would happen.
6. Ask for confirmation if the operation is destructive.
7. Execute.
8. Verify the results.
9. Clean up temporary files.

The generated script should not automatically receive unrestricted permissions.

It must execute inside the same security/permission model as every other tool.

---

# 9. Dry-Run Principle

For potentially destructive batch operations:

```text
PLAN
 ↓
DRY RUN
 ↓
SHOW SUMMARY
 ↓
CONFIRM
 ↓
EXECUTE
 ↓
VERIFY
```

Example:

> "Rename all files."

Brown:

> "I found 438 files. The rename would change their names but won't delete anything. Do you want me to proceed?"

For safer operations, confirmation may not be required.

---

# 10. Local Tool Discovery

Brown should inspect what is already installed before deciding how to accomplish a task.

Potential discovery mechanisms:

```text
ImageMagick
FFmpeg
Python
Node.js
Git
zip/unzip
tar
LibreOffice
Pandoc
Docker
specialised project tools
installed applications
```

Do not assume a tool is installed.

Use a capability registry:

```text
Capability:
    image_conversion
    video_conversion
    pdf_processing
    archive_creation
    code_building
    testing
    file_search
    browser_automation
```

Each capability can have several implementations.

Example:

```text
image_conversion
 ├── ImageMagick
 ├── Python/Pillow
 ├── macOS application
 └── Web API
```

Brown selects the best available implementation.

---

# 11. Tool Registry

Use strongly typed tools.

Example:

```text
get_system_info(device)
get_temperature(device)
get_running_apps(device)
open_application(device, application)
close_application(device, application)
get_browser_tabs(device, browser)
open_url(device, url)

find_project(project_name)
find_file(query)
read_file(path)
write_file(path, content)
create_directory(path)

run_safe_script(script, working_directory)
inspect_directory(path)
batch_convert_images(...)
batch_rename_files(...)
create_archive(...)

build_project(project)
find_build_artifact(project, artifact_type)

send_whatsapp_message(...)
send_whatsapp_file(...)

open_chatgpt(device)
ask_chatgpt(device, question)
ask_external_ai(...)
```

Tools should be validated before execution.

---

# 12. Project-Aware Operations

Brown should understand projects by name.

Example:

> "Hey Brown, go to my Weather App project."

Brown should search configured project locations and identify the project.

Potential project registry:

```text
Project
 ├── name
 ├── path
 ├── device
 ├── repository
 ├── technology
 ├── build commands
 ├── output locations
 └── notes
```

For example:

```text
Weather App
device: Error Boy
path: ~/Projects/weather-app
type: Android
build: ./gradlew assembleRelease
artifact: app/build/outputs/apk/release/app-release.apk
```

Do not hard-code these values before discovering the actual project.

---

# 13. Build-and-Share Workflow

Brown should support workflows such as:

> "Hey Brown, go to the Weather App project, build the APK, and send the APK to John on WhatsApp."

This is a **multi-step goal**, not one tool call.

Brown should plan:

```text
Identify project
      ↓
Identify target device
      ↓
Inspect project
      ↓
Determine build system
      ↓
Determine correct build command
      ↓
Check dependencies/environment
      ↓
Build
      ↓
Detect build success/failure
      ↓
Locate APK
      ↓
Verify APK
      ↓
Identify WhatsApp recipient
      ↓
Open/use WhatsApp Web
      ↓
Find correct conversation
      ↓
Attach APK
      ↓
Send
      ↓
Verify message/file was sent
      ↓
Tell user
```

Brown should not blindly run a guessed build command.

It should inspect the project.

---

# 14. Build System Detection

For software projects Brown should inspect files such as:

```text
package.json
pom.xml
build.gradle
build.gradle.kts
settings.gradle
settings.gradle.kts
Cargo.toml
pyproject.toml
requirements.txt
Makefile
CMakeLists.txt
Podfile
xcodeproj
xcworkspace
```

Then determine the likely build system.

For Android, it should identify:

- Gradle wrapper
- modules
- build variants
- APK/AAB outputs
- debug/release variants
- signing requirements

If a release build requires credentials or signing configuration that Brown cannot access, Brown should stop and explain what is missing rather than bypassing security.

---

# 15. APK Workflow

Example:

> "Take the build APK."

Brown should clarify or infer the intended artifact based on project context.

Potential artifacts:

```text
debug APK
release APK
signed release APK
AAB
IPA
```

Brown should identify the correct output and verify:

- File exists
- File is non-empty
- Expected format
- Build succeeded
- Timestamp/version is correct

If ambiguity exists:

> "I found both a debug APK and a release APK. Which one should I send?"

Unless previous context clearly resolves it.

---

# 16. WhatsApp Web

Brown should be able to use WhatsApp Web through browser automation where appropriate.

Example:

> "Send this APK to Arun on WhatsApp."

Workflow:

```text
Locate file
   ↓
Resolve recipient
   ↓
Open WhatsApp Web
   ↓
Authenticate using existing user session
   ↓
Find conversation
   ↓
Attach file
   ↓
Check recipient
   ↓
Send
   ↓
Verify
```

Because sending a file/message externally is a consequential action, the system should have a permission policy.

A possible policy:

```text
Prepare message/file:
    automatic

Actually send:
    confirmation required
```

Or allow the user to configure trusted workflows/recipients.

---

# 17. Recipient Safety

Never assume that a name uniquely identifies a person.

If there are:

```text
Arun Kumar
Arun
Arun - College
Arun - Work
```

Brown should ask which one unless the user has clearly specified the intended contact.

Before sending a consequential message/file, Brown should verify:

```text
recipient
file
message
```

Then send.

---

# 18. External Website vs Local Automation

Brown should decide dynamically.

Example:

> "Convert these 500 images to WebP."

Possible reasoning:

```text
500 images
+
local ImageMagick available
+
no special online processing needed
=
LOCAL BATCH SCRIPT
```

Another task:

> "Remove the background from these 50 product photos using the specific website I use."

If the website provides the desired output and no local equivalent is available:

```text
BROWSER AUTOMATION
```

Another task:

> "Compress this image using TinyPNG."

If the user explicitly names the website:

```text
Use requested website
```

The user's explicit preference can override Brown's normal method selection, subject to safety/privacy constraints.

---

# 19. Human-Like Planning

"Think like a human" should mean:

### Understand the objective

Not just the literal words.

### Inspect the environment

What files/apps/tools/projects are actually available?

### Consider alternatives

Can this be done locally, through an API, through a browser, or with a script?

### Optimise

Prefer the fastest reliable method.

### Preserve quality

Don't choose speed if it destroys required output quality.

### Minimise unnecessary work

Don't open 20 applications if one command can accomplish the task.

### Ask when ambiguity matters

Do not guess when the wrong choice could cause damage.

### Verify

Do not assume success.

### Recover

If a method fails, consider a safe alternative.

---

# 20. Task Planning Score

A method can be scored conceptually:

```text
score =
    reliability
  + output_quality
  + speed
  + privacy
  + simplicity
  - risk
  - cost
```

The exact mathematical formula does not need to be literal.

The planner should make these trade-offs explicitly.

For example:

| Method | Speed | Reliability | Privacy | Quality | Risk |
|---|---:|---:|---:|---:|---:|
| Local script | High | High | High | High | Low |
| Local GUI | Medium | Medium | High | High | Medium |
| API | High | High | Depends | High | Medium |
| Website | Low/Medium | Medium | Lower | High | Medium |
| Manual | Low | Medium | High | Variable | Low/Medium |

These values are illustrative; Brown should assess the actual situation.

---

# 21. Browser Automation Architecture

Use a browser automation abstraction.

Prefer:

```text
DOM
Accessibility tree
Semantic selectors
Stable element attributes
```

instead of brittle screen coordinates.

Browser actions might include:

```text
open_browser()
open_url()
find_element()
click()
type()
upload_file()
wait_for_page()
read_text()
download_file()
```

Browser content is **untrusted data**.

A webpage must never be allowed to override Brown's system instructions or permission policies.

---

# 22. ChatGPT / External AI Workflow

Example:

> "Open ChatGPT and ask it what the future of AI looks like."

Brown:

```text
Determine target device
 ↓
Open browser
 ↓
Open ChatGPT
 ↓
Submit question
 ↓
Wait for response
 ↓
Extract response
 ↓
Pass response to Brown
 ↓
Understand/summarise
 ↓
Speak result
```

If the response is long, Brown should not read it word-for-word.

User can ask:

> "Go deeper on the second point."

Brown should retain the relevant context.

---

# 23. External AI Provider Abstraction

Do not hard-code ChatGPT into the core architecture.

Create:

```text
ExternalAIProvider
 ├── ChatGPTBrowserProvider
 ├── GeminiProvider
 └── Other providers
```

Eventually:

> "Ask ChatGPT and Gemini the same question and compare them."

Brown should:

1. Ask both.
2. Retrieve both responses.
3. Compare.
4. Identify agreement/disagreement.
5. Synthesise.
6. Speak the result.

---

# 24. Local vs Cloud Model Routing

Use a hybrid architecture.

### Local

Prefer for:

- Simple tool selection
- Private data
- Computer operations
- Local file operations
- Basic summarisation
- Offline functionality

### Cloud

Prefer for:

- Complex reasoning
- Research
- Large reasoning tasks
- Tasks where the local model is insufficient

### External AI

Use when the user explicitly asks Brown to interact with another AI service.

The model provider must remain replaceable.

---

# 25. Privacy Gateway

Never send the whole machine state to cloud AI.

Use:

```text
Device Agent
   ↓
Privacy Gateway
   ↓
Minimal required data
   ↓
Cloud Model
```

Sensitive information to protect:

```text
passwords
API keys
private keys
authentication tokens
.env files
SSH credentials
browser cookies
session tokens
credit-card information
private documents
private messages
```

---

# 26. Privacy Modes

### Normal

Cloud AI available where appropriate.

### Private

Sensitive information is redacted before cloud processing.

### Local-only

No cloud AI.

Brown should be able to report which mode is active.

---

# 27. Security Model

Never use:

```text
LLM → unrestricted shell → operating system
```

Use:

```text
LLM
 ↓
Typed tool
 ↓
Validation
 ↓
Permission
 ↓
Device agent
 ↓
Operating system
```

Potential permission levels:

### Safe

Examples:

- CPU usage
- temperature
- list apps
- open applications
- inspect non-sensitive files

### Confirmation

Examples:

- delete files
- send messages
- send files
- modify system settings
- install software
- execute generated scripts with meaningful effects

### Blocked/restricted

Examples:

- passwords
- private keys
- authentication secrets
- browser cookies
- arbitrary credential extraction

---

# 28. Script Execution Security

Generated scripts are potentially dangerous.

Use:

```text
generated script
 ↓
static inspection
 ↓
working-directory restriction
 ↓
allowed command policy
 ↓
resource/time limit
 ↓
permission check
 ↓
execution
 ↓
verification
```

Avoid allowing arbitrary generated scripts to run as administrator/root.

---

# 29. Cross-Device Operations

Brown should coordinate both computers.

Example:

> "Find the project on Error Boy and open it on Paperball."

Workflow:

```text
Error Boy
 ↓
Search
 ↓
Locate project
 ↓
Return information
 ↓
Paperball
 ↓
Open/access project
```

Another:

> "Build this on Error Boy and send the result to Paperball."

Brown orchestrates both agents.

---

# 30. Memory

Start with SQLite.

Store structured information such as:

```text
device names
device capabilities
project locations
user preferences
assistant settings
conversation context
trusted contacts/preferences
tool permissions
```

Do not store sensitive credentials in ordinary memory.

Semantic/vector memory can be added later.

---

# 31. Project Registry

Brown should maintain an optional project registry.

Example:

```text
projects:
  weather-app:
    device: Error Boy
    path: ~/Projects/weather-app
    type: Android

  personal-site:
    device: Paperball
    path: ~/Projects/personal-site
    type: Web
```

Brown can learn this from discovery and user confirmation.

---

# 32. Voice System

```text
Microphone
 ↓
Wake word
 ↓
STT
 ↓
Brown
 ↓
Planning / Tools
 ↓
Response
 ↓
TTS
 ↓
Speaker
```

Required eventually:

- Wake word
- Streaming STT
- Streaming/low-latency TTS
- Barge-in
- Conversation continuation
- Interruption handling

---

# 33. Natural Voice Behaviour

Instead of:

> "Command executed successfully."

Say:

> "Done. VS Code is open on Error Boy."

Instead of reading raw metrics:

> "CPU temperature: 68 degrees."

Say:

> "Paperball's CPU is sitting around 68 degrees, which looks normal."

Brown should choose concise spoken responses unless the user asks for detail.

---

# 34. Error Handling

Never claim success without verification.

Bad:

> "Done."

when the operation failed.

Good:

> "The build failed because Gradle couldn't resolve a dependency. I haven't sent anything to WhatsApp."

If Brown cannot determine the correct action:

> "I found two APKs: debug and release. Which one do you want?"

---

# 35. Verification

Every meaningful workflow should have a verification step.

Examples:

### File conversion

Verify:

- expected number of files
- expected extension
- readable outputs
- no unexpected overwrites

### Build

Verify:

- build exit status
- artifact existence
- file size
- expected variant

### WhatsApp

Verify:

- intended conversation
- file attachment
- successful send state where detectable

### Browser

Verify:

- correct page
- correct account/session
- expected result

---

# 36. Recovery / Alternative Methods

If the first method fails, Brown should evaluate alternatives.

Example:

```text
Try local converter
 ↓
Fails
 ↓
Check alternative local library
 ↓
If suitable → use it
 ↓
Otherwise consider API/website
 ↓
Ask user if privacy/cost implications matter
```

Do not repeatedly retry a broken method indefinitely.

---

# 37. Human Confirmation Policy

Brown should distinguish between:

### Reversible / harmless

Can usually execute automatically.

Examples:

- Open app
- Read CPU usage
- Search a folder
- Create a new output folder

### Potentially destructive

Ask first.

Examples:

- Delete
- Overwrite
- Bulk rename
- Modify source files

### External communication

Usually require confirmation unless the user has explicitly authorised the workflow.

Examples:

- Send WhatsApp message
- Send APK
- Send email
- Post publicly

### High privilege

Require explicit confirmation and strong restrictions.

---

# 38. Example End-to-End Workflow

User:

> "Hey Brown, go to my Android project, build the release APK, and send it to Arun on WhatsApp."

Brown's internal conceptual process:

```text
1. Identify project
2. Identify project device
3. Inspect project
4. Detect Android/Gradle
5. Find release build configuration
6. Check whether required environment is available
7. Build
8. Verify build
9. Locate release APK
10. Verify APK
11. Resolve Arun
12. Open WhatsApp Web
13. Confirm correct conversation
14. Attach APK
15. Ask for confirmation if required by policy
16. Send
17. Verify
18. Speak result
```

Possible final response:

> "The release APK built successfully. It's about 18 MB. I found Arun's WhatsApp conversation and attached it. Do you want me to send it?"

After confirmation:

> "Sent. The release APK is in Arun's chat."

---

# 39. Another Example — Image Processing

User:

> "Convert every image in this folder to WebP and keep the originals."

Brown:

```text
Inspect folder
 ↓
Count images
 ↓
Check formats
 ↓
Check local tools
 ↓
Select local batch processing
 ↓
Create output directory
 ↓
Convert
 ↓
Verify count
 ↓
Report
```

Response:

> "Done. I converted 286 images to WebP and kept all the originals untouched."

---

# 40. Another Example — Website Preference

User:

> "Use this website to convert all these images."

Brown should respect the explicit website instruction.

However:

- It should inspect whether the website supports batch uploads.
- It should avoid uploading sensitive data without appropriate permission.
- It should verify the outputs.
- It should handle failures.

If the website only supports one file at a time and there are 500 files, Brown should recognise that this is inefficient and tell the user:

> "The site only processes one image at a time. I can still automate it, but a local batch conversion would be substantially faster. Do you want me to use the local method instead?"

The user's explicit instruction remains important, but Brown should surface meaningful efficiency trade-offs.

---

# 41. Tool Capability Discovery

Brown should be able to ask:

```text
What tools exist?
What applications are installed?
What browser is available?
What project build systems exist?
What local libraries are installed?
What GPU is available?
What device is online?
```

This prevents hard-coded assumptions.

---

# 42. Performance

Simple tasks should be extremely fast.

Do not unnecessarily perform:

```text
STT
 → Cloud LLM
 → second LLM
 → tool
 → third LLM
 → TTS
```

for:

> "Open Safari."

Use deterministic routing whenever possible.

Complex tasks can use deeper planning.

---

# 43. Planner Depth

Use different planning levels.

### Level 0 — Direct action

```text
"Open Safari."
```

### Level 1 — Small workflow

```text
"Find my Downloads folder and open it."
```

### Level 2 — Multi-step task

```text
"Convert all images in this folder."
```

### Level 3 — Complex workflow

```text
"Build my Android project and send the release APK to Arun."
```

The system should avoid expensive reasoning for Level 0 tasks.

---

# 44. Observability

Maintain structured logs:

```text
USER_REQUEST
INTENT
TARGET_DEVICE
PLAN
METHOD_SELECTION
PERMISSION_CHECK
TOOL_CALL
TOOL_RESULT
VERIFICATION
FINAL_RESPONSE
```

Never log:

- passwords
- API keys
- tokens
- private credentials

---

# 45. Failure Independence

If Paperball is offline:

Brown should still work through Error Boy where possible.

If Error Boy is offline:

Brown should still work through Paperball where possible.

The controller should know:

```text
Paperball = online/offline
Error Boy = online/offline
```

and adapt.

---

# 46. Recommended Initial Technology Direction

A reasonable starting stack:

```text
Core:
Python or TypeScript

Backend:
FastAPI or equivalent

Device communication:
Authenticated HTTPS/WebSocket

Browser:
Playwright

Memory:
SQLite

Voice:
Wake-word + STT + TTS abstraction

AI:
Local model + cloud provider abstraction

macOS:
Controlled native/system APIs

Linux:
Controlled Linux tools/APIs

Security:
Tool permissions + authentication + secret management
```

Antigravity should verify the best choices against the actual environment rather than treating this list as mandatory.

---

# 47. Suggested Repository

```text
brown/
│
├── core/
│   ├── orchestrator/
│   ├── planner/
│   ├── router/
│   ├── conversation/
│   ├── verification/
│   └── memory/
│
├── models/
│   ├── providers/
│   ├── local/
│   └── cloud/
│
├── voice/
│   ├── wakeword/
│   ├── stt/
│   ├── tts/
│   └── audio/
│
├── tools/
│   ├── system/
│   ├── filesystem/
│   ├── scripts/
│   ├── applications/
│   ├── browser/
│   ├── projects/
│   ├── builds/
│   └── communication/
│
├── agents/
│   ├── paperball/
│   └── error_boy/
│
├── browser/
│   ├── core/
│   └── providers/
│
├── security/
│   ├── permissions/
│   ├── secrets/
│   ├── privacy/
│   └── sandbox/
│
├── config/
│
└── tests/
```

---

# 48. Development Phases

## Phase 1 — Hardware discovery

Inspect both machines.

Record:

```text
CPU
RAM
GPU
VRAM
OS
kernel/version
available storage
installed runtimes
```

Do not choose a large local model before this.

---

## Phase 2 — Device agents

Build:

```text
Paperball Agent
Error Boy Agent
```

Test system information and safe application operations.

---

## Phase 3 — Secure communication

Connect the controller to both agents.

---

## Phase 4 — Tool registry

Implement 5–10 safe deterministic tools.

---

## Phase 5 — Local model

Install a suitably sized local model based on Error Boy's actual hardware.

Test function/tool calling.

---

## Phase 6 — Planner

Implement goal decomposition and method selection.

---

## Phase 7 — Voice

Add wake word, STT, TTS, and interruption.

---

## Phase 8 — File/project automation

Implement:

- file discovery
- batch processing
- safe script generation
- project discovery
- build detection
- artifact detection

---

## Phase 9 — Browser automation

Implement Playwright-based browser control.

---

## Phase 10 — External AI

Implement ChatGPT/Gemini/provider abstraction.

---

## Phase 11 — Communication

Implement WhatsApp Web workflows with strong recipient/file verification.

---

## Phase 12 — Memory

Add persistent project/device/preferences memory.

---

## Phase 13 — Security hardening

Test:

- prompt injection
- malicious websites
- arbitrary command attempts
- secret leakage
- privilege escalation
- unsafe generated scripts
- accidental external communication

---

## Phase 14 — Optimisation

Improve:

- latency
- voice naturalness
- interruption
- reliability
- planning quality
- method selection
- recovery

---

# 49. First Demo

The first complete vertical slice should be:

```text
"Hey Brown."
        ↓
"What's running on Paperball?"
        ↓
Brown speaks result.
        ↓
"Open ChatGPT."
        ↓
Brown opens it.
        ↓
"Ask it what the future of AI looks like."
        ↓
Brown asks ChatGPT.
        ↓
Brown understands response.
        ↓
Brown speaks summary.
        ↓
"What does that mean for developers?"
        ↓
Brown answers using context.
        ↓
"Open VS Code on Error Boy."
        ↓
Brown performs action.
```

Then build the more advanced workflow:

```text
"Brown, go to my Android project,
build the release APK,
and send it to Arun on WhatsApp."
```

---

# 50. Antigravity Instructions

Before writing substantial code:

1. Inspect the repository.
2. Inspect the actual hardware of Paperball and Error Boy.
3. Identify OS versions.
4. Identify installed runtimes and tools.
5. Identify available GPUs/VRAM.
6. Identify browser installations.
7. Identify existing project directories.
8. Propose the architecture.
9. Propose the exact technology stack.
10. Propose the local model based on actual hardware.
11. Propose the security model.
12. Propose the permission model.
13. Propose the planner/method-selection architecture.
14. Propose the first vertical slice.
15. Produce a test plan.
16. **Do not implement the whole system immediately.**
17. Wait for approval before making large architectural changes.

---

# 51. Critical Architectural Rule

Brown should be:

```text
                    GOAL
                     ↓
                 UNDERSTAND
                     ↓
                  INSPECT
                     ↓
                MAKE A PLAN
                     ↓
             CONSIDER ALTERNATIVES
                     ↓
               CHOOSE METHOD
                     ↓
              CHECK PERMISSIONS
                     ↓
                  EXECUTE
                     ↓
                 VERIFY
                     ↓
              RECOVER IF NEEDED
                     ↓
                REPORT RESULT
```

This is the core behaviour that differentiates Brown from a simple voice command system.

---

# 52. Ultimate Goal

The long-term goal is to build:

> **A personal, voice-first AI operating layer that understands goals, reasons about the environment, selects efficient and reliable workflows, safely operates multiple computers, works with local applications and files, automates browsers and external services, builds and processes projects, communicates through authorised channels, remembers useful context, verifies its actions, and communicates naturally through voice.**

Brown should not merely ask:

> "What command did the user give me?"

It should ask:

> **"What is the user trying to accomplish, what is the safest and most efficient way to accomplish it with the resources available, and how can I verify that I actually accomplished it?"**

That principle should guide the entire implementation.
