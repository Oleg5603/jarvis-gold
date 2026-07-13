#!/usr/bin/env node
/**
 * PreToolUse hook — hard-denies the operations the "Как работает защита" slide
 * deck labels 🔴 (red) plus reads of secret files, regardless of the
 * `--dangerously-skip-permissions` flag the agent bot spawns Claude Code with.
 *
 * Wired via AGENT_HOME/.claude/settings.json (see ../claude-settings/settings.json
 * in this repo for the config to deploy). Claude Code runs PreToolUse hooks even
 * when permissions are skipped — hooks are a separate gate, not part of the
 * permission-prompt system that --dangerously-skip-permissions turns off.
 *
 * Protocol: reads the tool-call JSON from stdin, exits 0 to allow, exits 2
 * (with a reason on stderr) to block. This is a hard deny, not the interactive
 * Telegram ✔/✖ confirmation described in the slides — building a real
 * mid-tool-call pause that round-trips through Telegram is a separate, larger
 * follow-up (see PROGRESS notes).
 */

const DENY_FILE_PATTERNS = [
  /\.env(\.|$)/i,
  /\.ssh\//i,
  /\bbot\/index\.js$/,
  /\bbot\/secrets-menu\.js$/,
  /\.agent\/\.env$/,
];

const DENY_BASH_PATTERNS = [
  { re: /\bsudo\b/i, reason: "sudo запрещён для агента" },
  { re: /\bprintenv\b/i, reason: "просмотр переменных окружения запрещён" },
  { re: /\brm\s+-rf\b/i, reason: "рекурсивное удаление (rm -rf) требует подтверждения человека" },
  { re: /\bgit\s+push\b[^\n]*--force/i, reason: "принудительный push (перезапись истории) требует подтверждения человека" },
  { re: /\bdrop\s+table\b/i, reason: "удаление таблицы БД требует подтверждения человека" },
  { re: /\b(shutdown|reboot)\b/i, reason: "перезагрузка/выключение сервера требует подтверждения человека" },
  { re: /\bkill\b\s+-9|\bkillall\b/i, reason: "принудительное завершение процессов запрещено" },
];

function deny(reason) {
  process.stderr.write(reason + "\n");
  process.exit(2);
}

function allow() {
  process.exit(0);
}

let raw = "";
process.stdin.on("data", (d) => (raw += d));
process.stdin.on("end", () => {
  let event;
  try {
    event = JSON.parse(raw);
  } catch {
    // Malformed input from Claude Code itself — fail open rather than break
    // every tool call over a hook bug.
    allow();
    return;
  }

  const toolName = event.tool_name || "";
  const input = event.tool_input || {};

  if (["Read", "Edit", "Write"].includes(toolName)) {
    const path = input.file_path || input.path || "";
    if (DENY_FILE_PATTERNS.some((re) => re.test(path))) {
      deny(`Заблокировано: доступ к "${path}" запрещён политикой агента (секреты/исходники бота).`);
      return;
    }
  }

  if (toolName === "Bash") {
    const command = input.command || "";
    for (const { re, reason } of DENY_BASH_PATTERNS) {
      if (re.test(command)) {
        deny(`Заблокировано: ${reason}. Команда: ${command}`);
        return;
      }
    }
  }

  allow();
});
