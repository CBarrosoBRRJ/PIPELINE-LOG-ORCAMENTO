"""Optional native TLS transport for Windows corporate network compatibility.

Token/body travel through stdin, never command-line arguments or temp files.
Certificate verification stays enabled. Default production transport: requests.
"""

import json as jsonlib
import shutil
import subprocess

import requests


class CurlSession:
    def __init__(self):
        self.headers = {}
        self.executable = shutil.which("curl.exe") or shutil.which("curl")
        if not self.executable:
            raise ValueError("Transporte curl selecionado, mas curl não está instalado")

    def post(self, url, json=None, timeout=60):
        quote = jsonlib.dumps
        config = [
            f"url = {quote(url)}",
            'request = "POST"',
            "silent",
            "show-error",
            "include",
            'write-out = "\\n%{http_code}"',
            f"max-time = {timeout}",
        ]
        config.extend(f"header = {quote(k + ': ' + v)}" for k, v in self.headers.items())
        config.append("data = " + quote(quote(json, ensure_ascii=True)))
        try:
            process = subprocess.run(
                [self.executable, "--config", "-"],
                input="\n".join(config),
                encoding="utf-8",
                capture_output=True,
                timeout=timeout + 5,
            )
        except subprocess.TimeoutExpired:
            raise requests.Timeout("curl timeout") from None
        if process.returncode:
            raise requests.ConnectionError(f"curl transport code {process.returncode}")
        body, code = process.stdout.rsplit("\n", 1)
        response = requests.Response()
        while body.startswith("HTTP/"):
            header_block, body = body.split("\n\n", 1)
            for line in header_block.splitlines()[1:]:
                if ":" in line:
                    name, value = line.split(":", 1)
                    response.headers[name.strip()] = value.strip()
        response.status_code = int(code)
        response._content = body.encode("utf-8")
        response.encoding = "utf-8"
        return response
