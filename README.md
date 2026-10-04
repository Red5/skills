# skills

Repository of Agent skills that provide ease of use to users and developers interested in Red5.

A skill is a folder containing a `SKILL.md` (instructions plus a short description of when to use it) and, optionally, scripts and reference files. Your coding agent reads the description, and loads the rest only when a task matches. Adding a skill to your agent means putting its folder where the agent looks for skills.

## Available skills

| Skill | What it does | Needs |
| --- | --- | --- |
| `red5-start-server` | Pulls the latest `red5pro/server` Docker release and starts a running Red5 container. | Docker, Python 3 |
| `red5-log-triage` | Summarizes a `red5.log` (plain, `.gz` or `.zip`) into ranked findings with likely causes and next steps, so support can diagnose from the log alone. | Python 3 |

Each skill lives in `.github/skills/<skill-name>/`.

## Add a skill to your agent

### 1. Get the skills

```bash
git clone https://github.com/Red5/skills.git
cd skills
```

To update later, run `git pull` in this folder.

### 2. Pick where it goes

Every agent has two kinds of location. Use a personal location to have the skill in every project on your machine, or a project location to have it only in one repository (and shared with your team if you commit it).

| Agent | Personal (all your projects) | Project (one repository) | Reload |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/skills/<skill-name>/` | `.claude/skills/<skill-name>/` | Picked up in the running session |
| GitHub Copilot (CLI, VS Code, cloud agent) | `~/.copilot/skills/<skill-name>/` or `~/.agents/skills/<skill-name>/` | `.github/skills/<skill-name>/` (also reads `.claude/skills/` and `.agents/skills/`) | `/skills reload` in the CLI |
| OpenAI Codex | `~/.agents/skills/<skill-name>/` | `.agents/skills/<skill-name>/` | Restart Codex if it does not appear |

On Windows, `~` is your user profile folder (for example `%USERPROFILE%\.claude\skills`).

Paths are current as of the agents' documentation at the time of writing. If an agent does not find the skill, check its documentation: [Claude Code](https://code.claude.com/docs/en/skills), [GitHub Copilot](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-skills), [Codex](https://learn.chatgpt.com/docs/build-skills).

### 3. Copy or link the skill folder

Copy the whole folder, not just `SKILL.md`, because the scripts and reference files are part of the skill. The examples below use `red5-log-triage`; swap in `red5-start-server` for the other skill.

**Claude Code, for all your projects:**

```bash
mkdir -p ~/.claude/skills
cp -r .github/skills/red5-log-triage ~/.claude/skills/
```

**Claude Code, for one project** (run from that project's root):

```bash
mkdir -p .claude/skills
cp -r /path/to/skills/.github/skills/red5-log-triage .claude/skills/
```

**GitHub Copilot, for all your projects:**

```bash
mkdir -p ~/.copilot/skills
cp -r .github/skills/red5-log-triage ~/.copilot/skills/
```

**GitHub Copilot, for one project:** the skills in this repository already sit in `.github/skills/`, which is where Copilot looks. To use one in another repository, copy it there:

```bash
mkdir -p .github/skills
cp -r /path/to/skills/.github/skills/red5-log-triage .github/skills/
```

**Codex, for all your projects:**

```bash
mkdir -p ~/.agents/skills
cp -r .github/skills/red5-log-triage ~/.agents/skills/
```

**Codex, for one project:** use `.agents/skills/` in that project's root instead.

To install every skill in this repository at once, replace `red5-log-triage` with `*`, for example `cp -r .github/skills/* ~/.claude/skills/`.

**Prefer a link so `git pull` updates your skills?** Link the folder instead of copying it:

```bash
ln -s "$PWD/.github/skills/red5-log-triage" ~/.claude/skills/red5-log-triage
```

(Use the matching folder from the table for your agent.)

### 4. Check that the agent sees it

- **Claude Code:** type `/` and look for the skill name in the list, or ask "what skills do you have?".
- **GitHub Copilot CLI:** run `/skills reload`, then `/skills list`. In VS Code, ask "what skills do you have?".
- **Codex:** restart Codex if the skill is missing, then ask which skills are available.

### 5. Use it

Your agent will use a skill on its own when your request matches the skill's description. You can also name it directly:

| Agent | Direct call |
| --- | --- |
| Claude Code | `/red5-log-triage` |
| GitHub Copilot | `/red5-log-triage` |
| Codex | `$red5-log-triage` |

Examples:

- `red5-log-triage`: "Here is a red5.log from a customer, `~/Downloads/red5.log`. Viewers kept freezing around 09:53. What is going on?"
- `red5-start-server`: "Start the latest Red5 Pro server in Docker."

## Skill notes

### red5-log-triage

Requires Python 3 and nothing else. The agent runs a bundled script that collapses repeated messages, ranks them, and prints findings and likely causes, then explains the result. The script reads the log locally and does not upload it, but the agent can see what the script prints and anything it searches out of the log.

Logs often contain IP addresses, usernames and, in some versions, the license key. Redact before sharing a log or the agent's report widely.

To teach it a new pattern, add an entry to `references/knowledge.json` in the skill folder. Its `_about` field explains the format.

### red5-start-server

Requires Docker running and permission to run Docker commands as your user, plus Python 3. It replaces any existing container named `red5-server`. See the skill's `SKILL.md` for the port and image overrides.

## Troubleshooting

- **The agent does not mention the skill.** Confirm the folder is named exactly like the skill and contains `SKILL.md` directly inside it (`~/.claude/skills/red5-log-triage/SKILL.md`, not one level deeper). Then reload or restart as in the table above.
- **The skill is found but its script is not.** Some skills refer to scripts by a path inside this repository, such as `.github/skills/red5-start-server/scripts/start-red5-server.sh`. If you installed the skill somewhere else, tell the agent the folder it was installed in, or install it as a project skill in `.github/skills/`.
- **A skill runs when you did not want it.** Tell the agent to skip it, or remove the folder to uninstall.
- **Uninstall.** Delete the skill's folder from the location you copied it to.

## Adding a skill to this repository

Create `.github/skills/<skill-name>/SKILL.md` with a `name` and a `description` that says what the skill does and when to use it, put any scripts in `scripts/` and reference material in `references/`, and add a row to the table above.
