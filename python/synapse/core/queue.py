"""
Synapse Command Queue

Thread-safe command queues for deterministic command processing.
"""

import logging
import threading
from typing import Optional, Dict, Any, List, Tuple
from collections import OrderedDict

from .protocol import SynapseCommand, SynapseResponse, MAX_PENDING_COMMANDS

logger = logging.getLogger("synapse.queue")


class DeterministicCommandQueue:
    """
    Thread-safe command queue with FIFO ordering guarantee.
    Commands are processed in strict sequence order.
    """

    def __init__(self, max_size: int = MAX_PENDING_COMMANDS):
        self._pending: OrderedDict[str, Tuple[SynapseCommand, Any]] = OrderedDict()
        self._lock = threading.RLock()
        self._sequence_counter = 0
        self._max_size = max_size
        self._condition = threading.Condition(self._lock)

    def enqueue(self, command: SynapseCommand, client: Any) -> int:
        """Add command with guaranteed sequence number."""
        with self._lock:
            if len(self._pending) >= self._max_size:
                self._evict_oldest()

            seq = self._sequence_counter
            self._sequence_counter += 1
            command.sequence = seq

            key = f"{seq}:{command.id}"
            self._pending[key] = (command, client)

            self._condition.notify_all()
            return seq

    def dequeue(self, timeout: float = 0.1) -> Optional[Tuple[SynapseCommand, Any]]:
        """Get next command in FIFO order."""
        with self._condition:
            if not self._pending:
                self._condition.wait(timeout=timeout)
                if not self._pending:
                    return None

            key, value = self._pending.popitem(last=False)
            return value

    def _evict_oldest(self):
        if self._pending:
            key, (cmd, client) = self._pending.popitem(last=False)
            logger.warning("Evicted command %s due to queue overflow", cmd.id)

    def size(self) -> int:
        with self._lock:
            return len(self._pending)

    def clear(self):
        with self._lock:
            self._pending.clear()


class ResponseDeliveryQueue:
    """Thread-safe queue for delivering responses to clients"""

    def __init__(self):
        self._responses: Dict[Any, List[SynapseResponse]] = {}
        self._lock = threading.Lock()

    def enqueue(self, response: SynapseResponse, client: Any):
        with self._lock:
            if client not in self._responses:
                self._responses[client] = []
            self._responses[client].append(response)

    def get_responses(self, client: Any) -> List[SynapseResponse]:
        with self._lock:
            responses = self._responses.pop(client, [])
            # He2025 batch invariance: deliver in sequence order regardless
            # of enqueue arrival order from concurrent threads
            return sorted(responses, key=lambda r: (r.sequence, r.id))

    def has_responses(self, client: Any) -> bool:
        with self._lock:
            return client in self._responses and len(self._responses[client]) > 0
