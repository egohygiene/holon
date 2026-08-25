import { mountRepositoryIntelligence } from "../../packages/repository-intelligence/src/index.js";
import { createComparison, createScenario } from "./fixtures.mjs";

const root = document.querySelector("#intelligence");
const compare = document.querySelector("[data-compare]");
const buttons = [...document.querySelectorAll("[data-scenario]")];
let activeScenario = "blocked";
let controller = null;

const theme = {
  tokens: {
    primary: "#78f0c8",
    accent: "#ae9cff",
    canvas: "#070d14",
    surface: "#101d2a",
    radius: "1.15rem",
  },
};

function render() {
  const snapshot = createScenario(activeScenario);
  controller?.destroy();
  controller = mountRepositoryIntelligence(root, {
    snapshot,
    comparison: compare.checked ? createComparison(snapshot) : null,
    theme,
    homeUrl: "../../README.md",
  });
  for (const button of buttons) {
    button.setAttribute("aria-pressed", String(button.dataset.scenario === activeScenario));
  }
}

for (const button of buttons) {
  button.addEventListener("click", () => {
    activeScenario = button.dataset.scenario;
    render();
  });
}
compare.addEventListener("change", render);
render();
