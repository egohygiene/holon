"""Proposed deployment contracts and disposable local artifact canaries."""

from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples/deployment"
SPEC = importlib.util.spec_from_file_location("deployment_profiles", ROOT / "tools/deployment_profiles.py")
PROFILES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROFILES)


def selection(name):
    return json.loads((FIXTURES / name / "selection.json").read_text())


class DeploymentProfilesTests(unittest.TestCase):
    def test_three_distinct_profile_fixtures_validate(self):
        for name in ("static-vite", "static-docs", "service-node"):
            with self.subTest(name=name):
                self.assertEqual(PROFILES.validate_artifact(selection(name), FIXTURES / name), [])

    def test_static_rejects_runtime_secrets_services_and_wrong_adapter(self):
        for mutation in ("secret", "runtime", "server-adapter", "wrong-preview", "removed-route"):
            document = selection("static-vite")
            if mutation == "secret":
                document["configuration"][0].update(classification="server-secret", source="external-secret-store")
            elif mutation == "runtime":
                document["runtime"] = selection("service-node")["runtime"]
            elif mutation == "server-adapter":
                document["framework"] = "node-http"
            elif mutation == "wrong-preview":
                document["preview"]["same_artifact_as_ci"] = False
            else:
                document["routes"].remove("/intelligence/")
            with self.subTest(mutation=mutation):
                self.assertTrue(PROFILES.validate_selection(document))

    def test_service_requires_declared_operations_health_and_separate_authority(self):
        for mutation in ("health", "migrations", "iac", "public-secret", "inline-secret", "privilege"):
            document = selection("service-node")
            if mutation == "health":
                del document["runtime"]["health"]
            elif mutation == "migrations":
                document["runtime"]["migrations"] = "automatic"
            elif mutation == "iac":
                document["runtime"]["iac"]["apply_authority"] = "implicit"
            elif mutation == "public-secret":
                document["configuration"][0]["name"] = "VITE_SERVER_TOKEN"
            elif mutation == "inline-secret":
                document["configuration"][0]["value"] = "synthetic-rejected-secret"
            else:
                document["handoff"]["validation_permissions"] = ["contents:write"]
            with self.subTest(mutation=mutation):
                errors = PROFILES.validate_selection(document)
                self.assertTrue(errors)
                self.assertNotIn("synthetic-rejected-secret", " ".join(errors))

    def test_paths_urls_routes_and_configuration_fail_closed(self):
        for value in ("../public", "/absolute", "a//b", "a/./b", "C:\\private", "a/../b"):
            document = selection("static-vite")
            document["artifact"]["path"] = value
            self.assertTrue(PROFILES.validate_selection(document), value)
        for value in ("//evil", "/a/../b", "/a%2fb", "/a?secret", "/a\\b"):
            document = selection("static-vite")
            document["routes"].append(value)
            self.assertTrue(PROFILES.validate_selection(document), value)
        for value in ("http://synthetic.invalid/", "https://synthetic.invalid/other/", "https://user:pass@synthetic.invalid/"):
            document = selection("static-vite")
            document["static"]["canonical_url"] = value
            self.assertTrue(PROFILES.validate_selection(document), value)
        document = selection("static-vite")
        document["configuration"] *= 2
        self.assertTrue(PROFILES.validate_selection(document))

    def test_static_artifact_missing_routes_keys_and_symlinks_reject(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            shutil.copytree(FIXTURES / "static-vite/public", target / "public")
            shutil.copy(FIXTURES / "static-vite/selection.json", target / "selection.json")
            document = selection("static-vite")
            secret = target / "public/.env.local"
            secret.write_text("SYNTHETIC=not-a-real-secret")
            self.assertTrue(PROFILES.validate_artifact(document, target))
            secret.unlink()
            (target / "public/link").symlink_to(target / "public/index.html")
            self.assertTrue(PROFILES.validate_artifact(document, target))
            (target / "public/link").unlink()
            (target / "public/intelligence/index.html").unlink()
            self.assertTrue(PROFILES.validate_artifact(document, target))

    def test_missing_inputs_and_symlinked_artifact_ancestors_reject(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            shutil.copytree(FIXTURES / "static-vite/public", target / "public")
            document = selection("static-vite")
            self.assertTrue(PROFILES.validate_artifact(document, target))
            shutil.copy(FIXTURES / "static-vite/selection.json", target / "selection.json")
            self.assertEqual(PROFILES.validate_artifact(document, target), [])
            (target / "alias").symlink_to(target, target_is_directory=True)
            document["artifact"]["path"] = "alias/public"
            self.assertTrue(PROFILES.validate_artifact(document, target))

    def test_both_static_canaries_serve_same_artifact_under_selected_base(self):
        for name in ("static-vite", "static-docs"):
            with self.subTest(name=name):
                document = selection(name)
                output = FIXTURES / name / document["artifact"]["path"]
                before = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in output.rglob("*") if p.is_file()}
                base = document["static"]["base_path"]

                class Handler(SimpleHTTPRequestHandler):
                    def log_message(self, *args):
                        pass

                    def do_GET(self):
                        if not self.path.startswith(base):
                            self.send_error(404)
                            return
                        self.path = "/" + self.path[len(base):]
                        super().do_GET()

                server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(output)))
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    prefix = f"http://127.0.0.1:{server.server_port}"
                    for route in document["routes"]:
                        with urlopen(prefix + base + route.lstrip("/"), timeout=3) as response:
                            self.assertEqual(response.status, 200)
                            self.assertIn(b"<!doctype html>", response.read())
                    with self.assertRaises(HTTPError) as error:
                        urlopen(prefix + base + "not-present", timeout=3)
                    self.assertEqual(error.exception.code, 404)
                    error.exception.close()
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=2)
                after = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in output.rglob("*") if p.is_file()}
                self.assertEqual(before, after)

    def test_real_service_has_separate_health_readiness_and_no_binding_disclosure(self):
        self.assertIsNotNone(shutil.which("node"), "Node is required for the declared local service canary")
        for configured in (False, True):
            environment = {"PATH": os.environ.get("PATH", "")}
            if configured:
                environment["SERVER_TOKEN"] = "synthetic-runtime-canary"
            process = subprocess.Popen(["node", "app.mjs"], cwd=FIXTURES / "service-node",
                                       env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True)
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    self.assertTrue(selector.select(5), "Service did not declare its loopback port")
                port = json.loads(process.stdout.readline())["port"]
                prefix = f"http://127.0.0.1:{port}"
                with urlopen(prefix + "/health", timeout=3) as response:
                    self.assertEqual(json.load(response), {"healthy": True})
                if configured:
                    with urlopen(prefix + "/ready", timeout=3) as response:
                        self.assertEqual(json.load(response), {"ready": True})
                else:
                    with self.assertRaises(HTTPError) as error:
                        urlopen(prefix + "/ready", timeout=3)
                    self.assertEqual(error.exception.code, 503)
                    self.assertEqual(json.load(error.exception), {"ready": False})
                    error.exception.close()
                with urlopen(prefix + "/intelligence/", timeout=3) as response:
                    self.assertNotIn(b"synthetic-runtime-canary", response.read())
            finally:
                process.terminate()
                stdout, stderr = process.communicate(timeout=5)
                self.assertNotIn("synthetic-runtime-canary", stdout + stderr)


if __name__ == "__main__":
    unittest.main()
