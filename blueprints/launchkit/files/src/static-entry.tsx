import { renderToString } from "react-dom/server";

import { App } from "./app";

const BASE_PATH = {{parameter_json.site_base_path}};

export function render(): string {
  return renderToString(<App basePath={BASE_PATH} pathname={BASE_PATH} />);
}
