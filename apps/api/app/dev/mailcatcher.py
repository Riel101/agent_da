"""A local SMTP sink for development.

Accepts real SMTP and writes each message to an ``.eml`` file, so the whole email
path — rendering, the SMTP conversation, delivery accounting — can be exercised
with no provider account at all. It is the difference between "the reminder was
logged" and "the reminder was actually handed to a mail server".

    python -m app.cli mail-catcher              # 127.0.0.1:1025, .eml files under /tmp
    python -m app.cli mail-catcher --port 2525

Point the API at it in ``.env`` and restart:

    SMTP_HOST=127.0.0.1
    SMTP_PORT=1025
    SMTP_STARTTLS=false
    SMTP_USER=
    SMTP_PASSWORD=

then ``python -m app.cli send-test`` should report ``outcome: sent``.

It deliberately accepts no credentials: if ``SMTP_USER`` is set, the handshake
fails with a message saying so, rather than pretending the credentials worked.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from email.parser import BytesParser
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

CRLF = "\r\n"
#: ``MAIL FROM:<someone@example.com>`` -> ``someone@example.com``
ADDRESS = re.compile(rb"<([^>]*)>")
DATA_TERMINATOR = (b".\r\n", b".\n")

NO_CREDENTIALS = (
    "504 5.5.4 the catcher takes no credentials; leave SMTP_USER and SMTP_PASSWORD empty"
)


def _address_of(line: bytes) -> str:
    match = ADDRESS.search(line)
    if match:
        return match.group(1).decode("utf-8", "replace")
    _, _, tail = line.partition(b":")
    return tail.strip().decode("utf-8", "replace")


class MailCatcher:
    """A minimal, single-purpose SMTP server that saves instead of sending."""

    def __init__(self, out_dir: Path) -> None:
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.received = 0

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await self._session(reader, writer)
        except (ConnectionResetError, BrokenPipeError, asyncio.IncompleteReadError):
            pass  # the client hung up; not interesting
        except Exception:  # noqa: BLE001 - one bad session must not stop the server
            logger.exception("mail catcher session failed")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except (ConnectionResetError, BrokenPipeError):
                pass

    async def _reply(self, writer: asyncio.StreamWriter, text: str) -> None:
        writer.write((text + CRLF).encode())
        await writer.drain()

    async def _session(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await self._reply(writer, "220 AgentDa mail catcher - messages are saved, not delivered")
        sender = ""
        recipients: list[str] = []

        while True:
            raw = await reader.readline()
            if not raw:
                return
            command = raw.strip()
            upper = command.upper()

            if upper.startswith(b"EHLO"):
                await self._reply(writer, "250-AgentDa mail catcher")
                await self._reply(writer, "250-8BITMIME")
                await self._reply(writer, "250 SIZE 26214400")
            elif upper.startswith(b"HELO"):
                await self._reply(writer, "250 AgentDa mail catcher")
            elif upper.startswith(b"MAIL FROM"):
                sender = _address_of(command)
                await self._reply(writer, "250 2.1.0 OK")
            elif upper.startswith(b"RCPT TO"):
                recipients.append(_address_of(command))
                await self._reply(writer, "250 2.1.5 OK")
            elif upper == b"DATA":
                await self._reply(writer, "354 End data with <CR><LF>.<CR><LF>")
                payload = await self._read_data(reader)
                path = self._store(payload, sender, recipients)
                await self._reply(writer, "250 2.0.0 Saved")
                self._announce(path, payload, sender, recipients)
                sender, recipients = "", []
            elif upper.startswith(b"AUTH"):
                await self._reply(writer, NO_CREDENTIALS)
            elif upper == b"RSET":
                sender, recipients = "", []
                await self._reply(writer, "250 2.0.0 OK")
            elif upper == b"NOOP":
                await self._reply(writer, "250 2.0.0 OK")
            elif upper == b"QUIT":
                await self._reply(writer, "221 2.0.0 Bye")
                return
            else:
                await self._reply(writer, "502 5.5.2 Command not implemented")

    async def _read_data(self, reader: asyncio.StreamReader) -> bytes:
        chunks: list[bytes] = []
        while True:
            line = await reader.readline()
            if not line or line in DATA_TERMINATOR:
                break
            if line.startswith(b".."):
                line = line[1:]  # undo SMTP dot-stuffing
            chunks.append(line)
        return b"".join(chunks)

    def _store(self, payload: bytes, sender: str, recipients: list[str]) -> Path:
        self.received += 1
        # The directory can vanish under a long-running catcher; recreate it
        # rather than dropping a message and killing the session.
        self.out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.out_dir / f"{stamp}-{self.received:04d}.eml"
        path.write_bytes(payload)
        return path

    def _announce(self, path: Path, payload: bytes, sender: str, recipients: list[str]) -> None:
        parsed = BytesParser().parsebytes(payload)
        print(
            f"[catcher] {len(payload)} bytes from {sender or '?'} to "
            f"{', '.join(recipients) or '?'}\n"
            f"          subject: {parsed.get('Subject', '(none)')}\n"
            f"          saved:   {path}",
            flush=True,
        )


async def serve(host: str, port: int, out_dir: Path) -> None:
    catcher = MailCatcher(out_dir)
    server = await asyncio.start_server(catcher.handle, host, port)
    print(f"AgentDa mail catcher listening on {host}:{port}", flush=True)
    print(f"saving messages to {catcher.out_dir}", flush=True)
    print(
        "point the API at it:\n"
        f"  SMTP_HOST={host}\n"
        f"  SMTP_PORT={port}\n"
        "  SMTP_STARTTLS=false\n"
        "  SMTP_USER=\n"
        "  SMTP_PASSWORD=",
        flush=True,
    )
    print("Ctrl-C to stop.", flush=True)
    async with server:
        await server.serve_forever()
