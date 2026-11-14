// Synthetic consumer-owned fixture, not a production runtime adapter.
import { createServer } from "node:http";

const server = createServer((request, response) => {
  const ready = Boolean(process.env.SERVER_TOKEN);
  response.setHeader("Content-Type", "application/json");
  if (request.url === "/health") {
    response.end(JSON.stringify({ healthy: true }));
  } else if (request.url === "/ready") {
    response.statusCode = ready ? 200 : 503;
    response.end(JSON.stringify({ ready }));
  } else if (request.url === "/" || request.url === "/intelligence/") {
    response.end(JSON.stringify({ fixture: "synthetic-service" }));
  } else {
    response.statusCode = 404;
    response.end(JSON.stringify({ error: "not-found" }));
  }
});
server.listen(0, "127.0.0.1", () => {
  process.stdout.write(JSON.stringify({ port: server.address().port }) + "\n");
});
process.on("SIGTERM", () => server.close());
