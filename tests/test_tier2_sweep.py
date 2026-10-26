"""Offline tests of the actual Nano batch launcher and shared sweep keeper."""

import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1]


class TestTier2Sweep(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "bench"
        for rel in ("scripts/tier2_sweep.py", "scripts/tier2_sweep.sh", "t2/nanocodex/run_batch.sh", "t2/pi/task.txt"):
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SRC / rel, target)
        spec = importlib.util.spec_from_file_location("isolated_sweep", self.root / "scripts/tier2_sweep.py")
        self.keeper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.keeper)
        self.out = self.root / "t2" / "nanocodex"
        self.key = "sk-synthetic-1234567890"

    def start(self, sweep="offline"):
        self.keeper.ledger.write(self.root, sweep, status="running")
        return sweep

    def trial(self, sweep, name, credential="primary", body=None, err="", rc=0):
        (self.out / (name + ".jsonl")).write_text(body if body is not None else '{"type":"run.completed"}\n')
        (self.out / (name + ".err")).write_text(err)
        args = SimpleNamespace(sweep=sweep, out=str(self.out), name=name, subject="nanocodex", credential=credential, rc=rc)
        with patch.object(self.keeper, "secret_values", return_value=[(self.key, "SYNTHETIC_KEY")]):
            self.keeper.record(args)
        return json.loads((self.root / "data/sweeps" / (sweep + ".json")).read_text())

    def test_auth_null_scores_reset_credential_scope_and_partial_durability(self):
        sweep = self.start()
        first = self.trial(sweep, "a", err="401 Unauthorized " + self.key)
        self.assertEqual(first["records"][0]["error"]["type"], "auth")
        self.assertIsNone(first["records"][0]["score"])
        self.assertNotIn(self.key, (self.out / "a.err").read_text())
        self.assertEqual(first["counts"]["records"], 1)
        self.trial(sweep, "b", credential="other", err="HTTP 401 Unauthorized")
        self.trial(sweep, "c", err="invalid API key")
        self.assertEqual(self.trial(sweep, "d", body='{"type":"run.completed"}\n')["status"], "running")
        self.trial(sweep, "e", err="bad credentials")
        self.trial(sweep, "f", err="401 Unauthorized")
        final = self.trial(sweep, "g", err="authentication_error")
        self.assertEqual(final["status"], "halted")
        self.assertEqual(final["counts"]["auth_errors"], 6)
        self.assertEqual(final["records"][-1]["status"], "errored")

    def test_target_401_in_model_output_is_not_provider_auth(self):
        sweep = self.start()
        result = self.trial(sweep, "target", body=json.dumps({"type": "assistant.message", "message": "target endpoint returned HTTP 401 Unauthorized"}))
        self.assertIsNone(result["records"][0]["error"])
        self.assertEqual(result["records"][0]["status"], "skipped")
        result = self.trial(sweep, "provider", body=json.dumps({"type": "run.error", "error": {"message": "HTTP 401 Unauthorized"}}))
        self.assertEqual(result["counts"]["auth_errors"], 1)

    def test_scrubs_on_error_and_finalizes_inflight_leftovers(self):
        sweep = self.start()
        self.trial(sweep, "failure", body="leaked " + self.key, rc=42)
        self.assertNotIn(self.key, (self.out / "failure.jsonl").read_text())
        self.assertEqual(json.loads((self.root / "data/sweeps/offline.json").read_text())["records"][0]["error"]["type"], "process")
        (self.out / "interrupted.err").write_text(self.key)
        with patch.object(self.keeper, "secret_values", return_value=[(self.key, "SYNTHETIC_KEY")]):
            self.keeper.finish(SimpleNamespace(sweep=sweep, out=str(self.out), rc=1))
        self.assertNotIn(self.key, (self.out / "interrupted.err").read_text())
        self.assertEqual(json.loads((self.root / "data/sweeps/offline.json").read_text())["status"], "stopped")

    def test_pi_error_field_not_assistant_content_or_trace_input(self):
        sweep = self.start()
        pi_error = {"type": "message_end", "message": {"role": "assistant", "stopReason": "error", "errorMessage": "401: {\"code\":401}"}}
        result = self.trial(sweep, "pi", body=json.dumps(pi_error) + "\n")
        self.assertEqual(result["records"][0]["error"]["type"], "auth")
        benign = {"type": "message_end", "message": {"role": "assistant", "stopReason": "end", "content": "HTTP 401 Unauthorized"}}
        trace = 'INFO agent.turn:model.call: trace content_kind="model.input" content="HTTP 401 Unauthorized"\n'
        result = self.trial(sweep, "quoted", body=json.dumps(benign) + "\n", err=trace)
        self.assertIsNone(next(row for row in result["records"] if row["sample_id"] == "quoted")["error"])


    def test_offline_batch(self):
        """Real shell scheduler, Python keeper, synthetic provider, no network/model."""
        stub = self.root / "stub.py"
        stub.write_text("#!/usr/bin/env python3\nimport json,os,sys\nfrom pathlib import Path\n"
                        "with Path(os.environ['STUB_CALLS']).open('a') as f: f.write('call\\n')\n"
                        "print(json.dumps({'type':'run.error','error':{'message':'HTTP 401 Unauthorized'}}))\n"
                        "print(os.environ.get('OPENAI_API_KEY',''),file=sys.stderr)\n")
        stub.chmod(0o755)
        calls = self.root / "calls.txt"
        env = {"PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""),
               "HOME": str(self.root / "home"), "NX": str(stub),
               "WORK": str(self.root / "work"), "OPENROUTER_API_KEY": self.key,
               "STUB_CALLS": str(calls)}
        result = subprocess.run(["bash", str(self.out / "run_batch.sh")], env=env, capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(len(calls.read_text().splitlines()), 7)  # one bounded pre-dispatched wave
        files = list((self.root / "data/sweeps").glob("*.json"))
        self.assertEqual(len(files), 1)
        ledger = json.loads(files[0].read_text())
        self.assertEqual(ledger["status"], "halted")
        self.assertEqual(ledger["counts"]["records"], 7)
        self.assertEqual(ledger["counts"]["auth_errors"], 7)
        self.assertNotIn(self.key, files[0].read_text())
        for file in self.out.glob("*.err"):
            self.assertNotIn(self.key, file.read_text())

    def test_fx_interrupt_persists_and_scrubs_captured_output(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node is required for the FX launcher")
        out = self.root / "t2" / "fx"
        out.mkdir()
        shutil.copy2(SRC / "t2/fx/t6.js", out / "t6.js")
        bindir = self.root / "bin"
        bindir.mkdir()
        stub = bindir / "fx"
        stub.write_text(
            "#!/usr/bin/env python3\nimport json,os,signal,socket,sys\n"
            "print(json.dumps({'type':'assistant.message','message':os.environ['OPENROUTER_API_KEY']}),flush=True)\n"
            "print(os.environ['OPENROUTER_API_KEY'],file=sys.stderr,flush=True)\n"
            "s=socket.socket(socket.AF_UNIX);s.connect(os.environ['READY_SOCKET']);"
            "s.sendall(b'ready');s.close()\nsignal.pause()\n"
        )
        stub.chmod(0o755)
        for name in ("pgrep", "pkill"):
            path = bindir / name
            path.write_text("#!/bin/sh\nexit 1\n")
            path.chmod(0o755)
        (self.root / "base/fixture").mkdir(parents=True)
        with tempfile.TemporaryDirectory(dir="/tmp") as sockets:
            address = str(Path(sockets) / "ready.sock")
            env = {"PATH": str(bindir) + os.pathsep + str(Path(sys.executable).parent)
                   + os.pathsep + os.environ.get("PATH", ""),
                   "HOME": str(self.root / "home"), "H2": str(self.root / "home"),
                   "BASE": str(self.root / "base"), "READY_SOCKET": address,
                   "OPENROUTER_API_KEY": self.key}
            with socket.socket(socket.AF_UNIX) as listener:
                listener.bind(address)
                listener.listen(1)
                listener.settimeout(15)
                child = subprocess.Popen([node, str(out / "t6.js")], env=env,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    connection, _ = listener.accept()
                    with connection:
                        self.assertEqual(connection.recv(5), b"ready")
                    child.terminate()
                    _, stderr = child.communicate(timeout=15)
                finally:
                    if child.poll() is None:
                        child.kill()
                        child.wait()
        self.assertEqual(child.returncode, 143, stderr)
        data = json.loads(next((self.root / "data/sweeps").glob("*.json")).read_text())
        self.assertEqual(data["status"], "stopped")
        self.assertEqual(data["counts"]["records"], 1)
        self.assertIsNone(data["records"][0]["score"])
        self.assertIn("<redacted:OPENROUTER_API_KEY>", (out / "t6.err").read_text())
        self.assertNotIn(self.key, (out / "t6.err").read_text())
        self.assertNotIn(self.key, (out / "t6.out").read_text())


if __name__ == "__main__":
    unittest.main()
