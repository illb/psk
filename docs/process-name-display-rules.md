# Process Name Display Rules

Rules applied when displaying process names in the process killer.

## Rule Overview

The full path of a process is abbreviated for readability. The following rules are applied in priority order.

## Detailed Rules

### 1. Mac Application Path (`/Applications/`)

#### 1.1 `Contents/MacOS/` Path

**Pattern**: `/Applications/AppName.app/Contents/MacOS/ExecName`

- **When AppName and ExecName are the same**:
  - Format: `Applications / AppName.app`
  - Examples:
    - `/Applications/Cursor.app/Contents/MacOS/Cursor` → `Applications / Cursor.app`
    - `/Applications/ChatGPT.app/Contents/MacOS/ChatGPT` → `Applications / ChatGPT.app`

- **When AppName and ExecName are different**:
  - Format: `Applications / AppName / ExecName`
  - Examples:
    - `/Applications/Visual Studio Code.app/Contents/MacOS/Electron` → `Applications / Visual Studio Code / Electron`
    - `/Applications/iTerm.app/Contents/MacOS/iTerm2` → `Applications / iTerm / iTerm2`

#### 1.2 Other Sub-paths (`Frameworks`, `Resources`, etc.)

**Pattern**: `/Applications/AppName.app/Contents/{SubPath}/ExecName`

- Format: `Applications / AppName.app / ExecName`
- Examples:
  - `/Applications/ChatGPT.app/Contents/Frameworks/Sparkle.framework/Versions/B/Autoupdate` → `Applications / ChatGPT.app / Autoupdate`
  - `/Applications/ChatGPT.app/Contents/Resources/ChatGPTHelper` → `Applications / ChatGPT.app / ChatGPTHelper`

### 2. Homebrew Path

**Pattern**: `/opt/homebrew/{...}/command`

- Format: `homebrew / {command}`
- Examples:
  - `/opt/homebrew/bin/python` → `homebrew / python`
  - `/opt/homebrew/bin/node` → `homebrew / node`
  - `/opt/homebrew/Cellar/node@22/22.17.0/bin/node` → `homebrew / node`

### 3. System Paths

#### 3.1 `/usr/bin/`, `/usr/sbin/`

- Format: `usr / {command}`
- Examples:
  - `/usr/bin/python3` → `usr / python3`
  - `/usr/sbin/nginx` → `usr / nginx`

#### 3.2 `/bin/`, `/sbin/`

- Format: `bin / {command}`
- Examples:
  - `/bin/zsh` → `bin / zsh`
  - `/sbin/launchd` → `bin / launchd`

#### 3.3 `/usr/local/bin/`

- Format: `local / {command}`
- Examples:
  - `/usr/local/bin/my-script` → `local / my-script`

### 4. Executed Without Path

**Pattern**: Executable name only without path (e.g., `node`, `npm`, `python`)

- Format: `(no path) / {command}`
- Examples:
  - `node script.js` (command field starts with `node`) → `(no path) / node`
  - `npm run start` (command field starts with `npm`) → `(no path) / npm`
  - `python app.py` (command field starts with `python`) → `(no path) / python`

### 5. Other Paths

**Pattern**: All paths that don't match the above rules

- Format: `{parent directory} / {executable name}`
- Examples:
  - `/Users/illb/project/script.sh` → `project / script.sh`
  - `/var/www/html/server.js` → `html / server.js`
  - `/Applications/Claude.app/Contents/Frameworks/Claude` → `Frameworks / Claude`

## Length Limit

- Maximum length: **50 characters**
- When exceeded:
  - Preserve executable name first
  - Abbreviate parent directory name
  - Example: `very-long-parent-directory-name / script.sh` (exceeds 50 chars) → `very-long-parent-directory... / script.sh`

## Priority

Rules are applied in the following order:

1. Mac Application path (`/Applications/AppName.app/`)
2. Homebrew path (`/opt/homebrew/`)
3. System paths (`/usr/bin/`, `/bin/`, `/usr/local/bin/`)
4. No path check
5. Other paths (parent directory / executable name)

## Implementation Location

- File: `src/process_killer/__init__.py`
- Method: `_format_process_name(command: str) -> str`

## Example Table

| Input Path | Output Format |
|-----------|---------------|
| `/Applications/Cursor.app/Contents/MacOS/Cursor` | `Applications / Cursor.app` |
| `/Applications/Visual Studio Code.app/Contents/MacOS/Electron` | `Applications / Visual Studio Code / Electron` |
| `/Applications/ChatGPT.app/Contents/Frameworks/Sparkle.framework/Versions/B/Autoupdate` | `Applications / ChatGPT.app / Autoupdate` |
| `/opt/homebrew/bin/python` | `homebrew / python` |
| `/opt/homebrew/Cellar/node@22/22.17.0/bin/node` | `homebrew / node` |
| `/usr/bin/python3` | `usr / python3` |
| `/bin/zsh` | `bin / zsh` |
| `/usr/local/bin/my-script` | `local / my-script` |
| `node script.js` | `(no path) / node` |
| `/Users/illb/project/script.sh` | `project / script.sh` |
