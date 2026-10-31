"""Asynchronous native build and framed local-socket runtime integration."""
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import uuid
from PySide6.QtCore import QObject, QProcess, Signal, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from .core.registry import ROOT
from .core.document import save_json
from .core.node_code import parse_compiler_diagnostic


class BuildService(QObject):
    output = Signal(str)
    finished = Signal(bool)
    busy_changed = Signal(bool)
    diagnostic = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._error)
        self.busy = False
        self.cancelled = False
        self._diagnostic_buffer = ''

    def start(self, project_path, graph, scene, snapshot=None):
        if self.busy:
            return
        request = Path(project_path).parent / "generated/build-request.json"
        save_json(request, snapshot if snapshot is not None else {"graph": graph, "scene": scene})
        self.busy, self.cancelled = True, False
        self._diagnostic_buffer = ''
        self.busy_changed.emit(True)
        self.process.setWorkingDirectory(str(ROOT))
        self.process.start(sys.executable, ["-u", "-m", "editor.build_worker", "--request", str(request),
                                            "--project", str(project_path)])

    def _read(self):
        text = bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace")
        self.output.emit(text)
        self._parse_output(text)

    def _parse_output(self, text, final=False):
        self._diagnostic_buffer += text
        lines = self._diagnostic_buffer.split('\n')
        self._diagnostic_buffer = lines.pop()
        if final:
            lines.append(self._diagnostic_buffer)
            self._diagnostic_buffer = ''
        for line in lines:
            diagnostic = parse_compiler_diagnostic(line)
            if diagnostic:
                self.diagnostic.emit(diagnostic)

    def _error(self, error):
        self.output.emit(self.process.errorString())
        if error == QProcess.ProcessError.FailedToStart:
            self._finished(-1, QProcess.ExitStatus.CrashExit)

    def _finished(self, code, status):
        self._read()
        self._parse_output('', final=True)
        self.busy = False
        self.busy_changed.emit(False)
        self.finished.emit(code == 0 and not self.cancelled)

    def cancel(self):
        if not self.busy:
            return
        self.cancelled = True
        pid = self.process.processId()
        if os.name == "nt" and pid:
            subprocess.Popen(["taskkill", "/PID", str(pid), "/T", "/F"],
                             creationflags=subprocess.CREATE_NO_WINDOW,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            self.process.terminate()


class RuntimeClient(QObject):
    message = Signal(dict)
    log = Signal(str)
    stopped = Signal(int)
    connected = Signal()
    MAX_FRAME = 16 * 1024 * 1024

    def __init__(self, parent=None):
        super().__init__(parent)
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self._accept)
        self.process = QProcess(self)
        self.process.readyReadStandardError.connect(
            lambda: self.log.emit(bytes(self.process.readAllStandardError()).decode("utf-8", "replace")))
        self.process.readyReadStandardOutput.connect(
            lambda: self.log.emit(bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace")))
        self.process.finished.connect(self._closed)
        self.process.errorOccurred.connect(self._error)
        self.socket = None
        self.buffer = bytearray()
        self.serial = 0
        self.ready = False
        self.state = "stopped"

    @property
    def active(self):
        return self.process.state() != QProcess.ProcessState.NotRunning

    def _error(self, error):
        self.log.emit(self.process.errorString())
        if error == QProcess.ProcessError.FailedToStart:
            self._closed(-1, QProcess.ExitStatus.CrashExit)

    def start(self, executable, ir_path, project_root):
        if self.active:
            raise RuntimeError("Runtime is already active")
        self.server.close()
        name = "node-engine-" + uuid.uuid4().hex
        if not self.server.listen(name):
            raise RuntimeError(self.server.errorString())
        self.buffer.clear()
        self.ready = False
        self.process.setWorkingDirectory(str(project_root))
        self.process.start(str(executable), ["--ir", str(ir_path), "--project-root", str(project_root),
                                             "--socket", self.server.fullServerName()])

    def _accept(self):
        if self.socket:
            extra = self.server.nextPendingConnection()
            extra.abort()
            extra.deleteLater()
            return
        self.socket = self.server.nextPendingConnection()
        self.socket.readyRead.connect(self._read)
        self._read()

    def _read(self):
        self.buffer.extend(bytes(self.socket.readAll()))
        try:
            while len(self.buffer) >= 4:
                length = struct.unpack_from("<I", self.buffer)[0]
                if length > self.MAX_FRAME:
                    raise ValueError("Runtime frame exceeds 16 MiB")
                if len(self.buffer) < length + 4:
                    break
                msg = json.loads(bytes(self.buffer[4:4+length]))
                del self.buffer[:4+length]
                if not isinstance(msg, dict):
                    raise ValueError("Runtime message must be an object")
                if msg.get("protocol_version") != 1:
                    raise ValueError("Runtime protocol mismatch")
                if msg.get("event") == "hello":
                    self.ready = True
                    self.connected.emit()
                if msg.get("event") == "state":
                    self.state = msg["state"]
                self.message.emit(msg)
        except (ValueError, UnicodeError) as error:
            self.log.emit(str(error))
            self.shutdown()

    def send(self, command, **data):
        if not self.socket or not self.ready:
            raise RuntimeError("Runtime connection is not ready")
        self.serial += 1
        raw = json.dumps({"protocol_version": 1, "id": self.serial, "command": command, **data},
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(raw) > self.MAX_FRAME:
            raise ValueError("Runtime command too large")
        self.socket.write(struct.pack("<I", len(raw)) + raw)
        return self.serial

    def shutdown(self):
        if self.ready:
            try:
                self.send("quit")
            except RuntimeError:
                pass
        process_id = self.process.processId()
        def kill_if_same():
            if process_id and self.active and self.process.processId() == process_id:
                self.log.emit('Runtime shutdown exceeded 10 seconds; terminating the process. Pending game saves may be incomplete.')
                self.process.kill()
        QTimer.singleShot(10000, self, kill_if_same)

    def _closed(self, code, _):
        self.ready = False
        self.state = "stopped"
        self.server.close()
        if self.socket:
            self.socket.deleteLater()
            self.socket = None
        self.stopped.emit(code)
