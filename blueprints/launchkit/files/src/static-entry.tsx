import { renderToStaticMarkup } from "react-dom/server";

import { App } from "./app";

const BASE_PATH = "{{parameter.site_base_path}}";

export function render(): string {
  return renderToStaticMarkup(<App basePath={BASE_PATH} pathname={BASE_PATH} />);
}
