from typing import Dict, List, Optional
import atexit
import http.client
import json
import os
import re
import requests
import socket
import subprocess
import threading
import time
import urllib.parse
from pathlib import Path

from .config_file import LanguageToolConfig
from .download_lt import download_lt, LTP_DOWNLOAD_VERSION
from .language_tag import LanguageTag
from .match import Match
from .utils import (
    correct,
    parse_url, get_locale_language,
    get_language_tool_directory, get_server_cmd,
    FAILSAFE_LANGUAGE, startupinfo,
    LanguageToolError, ServerError, PathError
)

DEBUG_MODE = False
MAX_STARTUP_ATTEMPTS = 3
STARTUP_TIMEOUT = 30  # seconds
PORT_RANGE = (8081, 8999)

# Keep track of running server PIDs
RUNNING_SERVER_PROCESSES: List[subprocess.Popen] = []

class LanguageTool:
    """Enhanced LanguageTool class with robust server initialization."""
    
    _TIMEOUT = 5 * 60
    _remote = False
    _PORT_RE = re.compile(r"(?:https?://.*:|port\s+)(\d+)", re.I)

    def __init__(
            self, language=None, motherTongue=None,
            remote_server=None, newSpellings=None,
            new_spellings_persist=True,
            host=None, config=None,
            language_tool_download_version: str = LTP_DOWNLOAD_VERSION,
            timeout: int = 60
    ):
        self.timeout = timeout
        self.language_tool_download_version = language_tool_download_version
        self._new_spellings = None
        self._new_spellings_persist = new_spellings_persist
        self._host = host or socket.gethostbyname('localhost')
        self._port = PORT_RANGE[0]
        self._server = None
        self._consumer_thread = None

        # Configure Java options if not set
        if 'JAVA_OPTS' not in os.environ:
            os.environ['JAVA_OPTS'] = "-Xms512m -Xmx1024m"

        if remote_server:
            assert config is None, "Cannot pass config file to remote server"
            self._init_remote_server(remote_server)
        else:
            self._init_local_server(config)

        if language is None:
            try:
                language = get_locale_language()
            except ValueError:
                language = FAILSAFE_LANGUAGE

        if newSpellings:
            self._new_spellings = newSpellings
            self._register_spellings(self._new_spellings)

        self._language = LanguageTag(language, self._get_languages())
        self.motherTongue = motherTongue
        self.disabled_rules = set()
        self.enabled_rules = set()
        self.disabled_categories = set()
        self.enabled_categories = set()
        self.enabled_rules_only = False
        self.preferred_variants = set()

    def _init_remote_server(self, remote_server):
        """Initialize connection to remote server."""
        self._remote = True
        self._url = parse_url(remote_server)
        self._url = urllib.parse.urljoin(self._url, 'v2/')

    def _init_local_server(self, config):
        """Initialize local server with retries and fallbacks."""
        self.config = LanguageToolConfig(config) if config else None
        if not self._server_is_alive():
            self._start_server_with_retry()

    def _start_server_with_retry(self):
        """Attempt to start server with multiple retries."""
        for attempt in range(MAX_STARTUP_ATTEMPTS):
            try:
                self._start_server_on_free_port()
                return
            except (ServerError, LanguageToolError) as e:
                if attempt == MAX_STARTUP_ATTEMPTS - 1:
                    raise LanguageToolError(
                        f"Failed to start server after {MAX_STARTUP_ATTEMPTS} attempts: {str(e)}"
                    )
                time.sleep(1)  # Wait before retrying

    def _start_server_on_free_port(self):
        """Find free port and start server."""
        for port in range(*PORT_RANGE):
            self._port = port
            try:
                self._start_local_server()
                return
            except ServerError as e:
                if "Port busy" not in str(e):
                    raise
                continue  # Try next port

        raise LanguageToolError(
            f"No available ports in range {PORT_RANGE[0]}-{PORT_RANGE[1]}"
        )

    def _start_local_server(self):
        """Start local LanguageTool server with proper resource management."""
        download_lt(self.language_tool_download_version)
        
        try:
            server_cmd = get_server_cmd(self._port, self.config)
            if DEBUG_MODE:
                print(f"Starting server with command: {' '.join(server_cmd)}")

            self._server = subprocess.Popen(
                server_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                startupinfo=startupinfo
            )
            RUNNING_SERVER_PROCESSES.append(self._server)

            # Wait for server to start
            start_time = time.time()
            while time.time() - start_time < STARTUP_TIMEOUT:
                line = self._server.stdout.readline()
                if not line:
                    time.sleep(0.1)
                    continue

                if DEBUG_MODE:
                    print(f"Server output: {line.strip()}")

                match = self._PORT_RE.search(line)
                if match:
                    port = int(match.group(1))
                    if port != self._port:
                        raise LanguageToolError(
                            f"Requested port {self._port}, but got {port}"
                        )
                    self._url = f'http://{self._host}:{self._port}/v2/'
                    break

            if not match:
                err_msg = self._terminate_server()
                if "Address already in use" in err_msg:
                    raise ServerError("Port busy")
                raise LanguageToolError(f"Server failed to start: {err_msg}")

            # Start output consumer thread
            self._consumer_thread = threading.Thread(
                target=self._consume_output,
                daemon=True
            )
            self._consumer_thread.start()

        except Exception as e:
            if self._server:
                self._terminate_server()
            raise LanguageToolError(f"Failed to start server: {str(e)}")

    def _consume_output(self):
        """Consume server output to prevent buffer blocking."""
        while True:
            line = self._server.stdout.readline()
            if not line:
                break
            if DEBUG_MODE:
                print(f"Server: {line.strip()}")

    # [Keep all other existing methods unchanged, including:
    # __enter__, __exit__, __del__, close, check, correct, etc.]
    # ...

    def _terminate_server(self):
        """Cleanly terminate server process."""
        err_msg = ''
        if self._server:
            try:
                self._server.terminate()
                _, stderr = self._server.communicate(timeout=5)
                err_msg = stderr.strip()
            except (OSError, subprocess.TimeoutExpired, ValueError):
                pass
            finally:
                self._server = None
        return err_msg

    def _server_is_alive(self):
        """Check if server process is still running."""
        return self._server and self._server.poll() is None

class LanguageToolPublicAPI(LanguageTool):
    """Language tool client for the official public API."""
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            remote_server='https://api.languagetool.org/api/',
            **kwargs
        )

@atexit.register
def terminate_server():
    """Cleanup function to terminate all server processes on exit."""
    for proc in RUNNING_SERVER_PROCESSES:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass