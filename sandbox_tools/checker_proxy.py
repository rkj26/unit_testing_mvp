"""Typed proxy injected into checker code as the candidate entry point."""

from __future__ import annotations

import builtins
import json
import os
import socket
import struct

from codec import decode_value, encode_value

MAX_MESSAGE_BYTES = 1_000_000
ALLOWED_EXCEPTIONS = {
    name: value
    for name, value in vars(builtins).items()
    if isinstance(value, type) and issubclass(value, Exception)
}


def _recv_exact(connection: socket.socket, size: int) -> bytes:
    value = bytearray()
    while len(value) < size:
        chunk = connection.recv(size - len(value))
        if not chunk:
            raise RuntimeError("candidate RPC response was truncated")
        value.extend(chunk)
    return bytes(value)


def _sync_mutable(original, updated) -> None:
    if isinstance(original, list) and isinstance(updated, list):
        original[:] = updated
    elif isinstance(original, dict) and isinstance(updated, dict):
        original.clear()
        original.update(updated)
    elif isinstance(original, set) and isinstance(updated, set):
        original.clear()
        original.update(updated)
    elif isinstance(original, bytearray) and isinstance(updated, (bytes, bytearray)):
        original[:] = updated


def call_candidate(*args, **kwargs):
    request = json.dumps(
        {"args": encode_value(tuple(args)), "kwargs": encode_value(dict(kwargs))},
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    if len(request) > MAX_MESSAGE_BYTES:
        raise ValueError("candidate RPC request exceeded limit")
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(15)
    client.connect(os.environ["PBT_RPC_SOCKET"])
    with client:
        client.sendall(struct.pack("!I", len(request)) + request)
        header = _recv_exact(client, 4)
        size = struct.unpack("!I", header)[0]
        if size > MAX_MESSAGE_BYTES:
            raise RuntimeError("candidate RPC response exceeded limit")
        body = _recv_exact(client, size)
    response = json.loads(body)
    if not isinstance(response, dict) or not isinstance(response.get("ok"), bool):
        raise RuntimeError("candidate RPC returned an invalid response")
    if not response["ok"]:
        exception = ALLOWED_EXCEPTIONS.get(response.get("exception"), RuntimeError)
        raise exception(response.get("message", "candidate call failed"))
    updated_args = decode_value(response["args_after"])
    updated_kwargs = decode_value(response["kwargs_after"])
    for original, updated in zip(args, updated_args):
        _sync_mutable(original, updated)
    for key, original in kwargs.items():
        if key in updated_kwargs:
            _sync_mutable(original, updated_kwargs[key])
    return decode_value(response["result"])
