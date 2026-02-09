const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

function run(name, command) {
  const child = spawn(command, {
    shell: true,
    stdio: "inherit",
    windowsHide: false,
  });

  child.on("exit", (code) => {
    if (code !== 0) {
      console.error(`[${name}] exited with code ${code}`);
    }
  });

  child.on("error", (err) => {
    console.error(`[${name}] failed to start: ${err.message}`);
  });

  return child;
}

function prepareRendererHtml() {
  const distRenderer = path.join(process.cwd(), "dist", "renderer");
  fs.mkdirSync(distRenderer, { recursive: true });
  fs.copyFileSync(
    path.join(process.cwd(), "src", "renderer", "index.html"),
    path.join(distRenderer, "index.html")
  );
}

prepareRendererHtml();

const commands = [
  { name: "main", cmd: "npx tsc --watch --project tsconfig.json" },
  { name: "renderer", cmd: "bun build ./src/renderer/index.tsx --outfile ./dist/renderer/bundle.js --watch" },
  { name: "electron", cmd: "npx wait-on dist/main/main.js && electron ." },
];

const children = commands.map((item) => run(item.name, item.cmd));

function shutdown() {
  for (const child of children) {
    if (child && !child.killed) {
      child.kill();
    }
  }
  process.exit(0);
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
