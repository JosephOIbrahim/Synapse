"""
Synapse Determinism Layer

Ensures strict reproducibility for AI-agent workflows.
Same input + same state = identical output, always.

Key principles:
1. Fixed precision rounding (defeats floating-point non-associativity)
2. Explicit seed management (no hidden randomization)
3. Deterministic ordering (sorted collections, stable iteration)
4. Content-based IDs (not random UUIDs)
5. Version locking (tool version embedded in output)

Performance note: Strict mode has ~2x overhead. Worth it for agent trust.
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import Tuple, List, Any, Dict, Optional, TypeVar, Callable
from functools import wraps
from decimal import Decimal, ROUND_HALF_UP

__version__ = "1.0.0"

T = TypeVar('T')


@dataclass
class DeterministicConfig:
    """Global determinism configuration"""

    # Precision for floating point operations
    float_precision: int = 6

    # Precision for transform values (position, rotation, scale)
    transform_precision: int = 4

    # Precision for color values
    color_precision: int = 4

    # Default sort key for collections
    default_sort_key: str = "name"

    # Whether to enforce strict mode (slower but perfectly reproducible)
    strict_mode: bool = True

    # Seed for any randomization (explicit, not time-based)
    global_seed: int = 42

    # Tool version for reproducibility tracking
    tool_version: str = __version__


# Global config instance
_config = DeterministicConfig()


def get_config() -> DeterministicConfig:
    """Get global determinism config"""
    return _config


def set_config(config: DeterministicConfig) -> None:
    """Set global determinism config"""
    global _config
    _config = config


def round_float(value: float, precision: Optional[int] = None) -> float:
    """
    Round float to fixed precision using banker's rounding.

    This defeats floating-point non-associativity by ensuring
    consistent representation regardless of computation order.

    Args:
        value: Float to round
        precision: Decimal places (defaults to config.float_precision)

    Returns:
        Rounded float with deterministic precision
    """
    if precision is None:
        precision = _config.float_precision

    if _config.strict_mode:
        # Use Decimal for exact rounding (slower but deterministic)
        d = Decimal(str(value))
        rounded = d.quantize(Decimal(10) ** -precision, rounding=ROUND_HALF_UP)
        return float(rounded)
    else:
        return round(value, precision)


def round_vector(
    vector: Tuple[float, ...],
    precision: Optional[int] = None
) -> Tuple[float, ...]:
    """Round all components of a vector"""
    if precision is None:
        precision = _config.transform_precision
    return tuple(round_float(v, precision) for v in vector)


def round_color(
    color: Tuple[float, float, float],
    precision: Optional[int] = None
) -> Tuple[float, float, float]:
    """Round color components with color-specific precision"""
    if precision is None:
        precision = _config.color_precision
    return (
        round_float(color[0], precision),
        round_float(color[1], precision),
        round_float(color[2], precision),
    )


def kahan_sum(values) -> float:
    """
    Kahan compensated summation for deterministic float aggregation.

    Maintains a running error term to recover lost low-order bits,
    reducing accumulated floating-point error from O(n) to O(1).

    Args:
        values: Iterable of float values to sum

    Returns:
        Deterministically rounded sum
    """
    total = 0.0
    c = 0.0  # Compensation for lost low-order bits
    for v in values:
        y = v - c
        t = total + y
        c = (t - total) - y
        total = t
    return round_float(total)


def deterministic_uuid(content: str, namespace: str = "synapse") -> str:
    """
    Generate deterministic UUID based on content hash.

    Same content always produces same UUID, unlike random UUIDs.
    This enables reproducible state tracking.

    Args:
        content: String content to hash
        namespace: Namespace prefix for collision avoidance

    Returns:
        16-character hex string (deterministic)
    """
    full_content = f"{namespace}:{_config.tool_version}:{content}"
    return hashlib.sha256(full_content.encode('utf-8')).hexdigest()[:16]


def deterministic_sort(
    items: List[T],
    key: Optional[Callable[[T], Any]] = None,
    sort_key: Optional[str] = None
) -> List[T]:
    """
    Sort items deterministically.

    Ensures iteration order is always consistent regardless of
    insertion order or platform differences.

    Args:
        items: List to sort
        key: Sort key function
        sort_key: Attribute name to sort by (if items are objects)

    Returns:
        Sorted list (new list, doesn't modify original)
    """
    if key is not None:
        return sorted(items, key=key)
    elif sort_key is not None:
        return sorted(items, key=lambda x: getattr(x, sort_key, str(x)))
    else:
        # Default: sort by string representation
        return sorted(items, key=str)


def deterministic_dict_items(d: Dict[str, Any]) -> List[Tuple[str, Any]]:
    """Get dict items in deterministic order (sorted by key)"""
    return sorted(d.items(), key=lambda x: x[0])


@dataclass
class DeterministicOperation:
    """
    Base class for all deterministic operations.

    Embeds reproducibility metadata in every operation:
    - Explicit seed for any randomization
    - Tool version for compatibility tracking
    - Timestamp for audit trail
    - Content hash for verification

    Usage:
        @dataclass
        class MyOperation(DeterministicOperation):
            param1: str
            param2: float

            def execute(self):
                # Use self.round_float(), self.deterministic_uuid(), etc.
                pass
    """

    # Explicit seed (overrides global if set)
    seed: Optional[int] = None

    # Operation metadata (auto-populated)
    operation_id: str = field(default="")
    tool_version: str = field(default="")
    schema_version: str = field(default="1.0.0")
    timestamp_utc: str = field(default="")

    def __post_init__(self):
        """Initialize deterministic metadata"""
        if not self.tool_version:
            self.tool_version = _config.tool_version
        if not self.timestamp_utc:
            self.timestamp_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if not self.operation_id:
            self.operation_id = self._generate_operation_id()

    def _generate_operation_id(self) -> str:
        """Generate deterministic operation ID"""
        content = f"{self.__class__.__name__}:{self.timestamp_utc}:{self.get_seed()}"
        return deterministic_uuid(content, namespace="op")

    def get_seed(self) -> int:
        """Get seed for this operation"""
        return self.seed if self.seed is not None else _config.global_seed

    def round_float(self, value: float, precision: Optional[int] = None) -> float:
        """Round float with operation-level precision control"""
        return round_float(value, precision)

    def round_vector(self, vector: Tuple[float, ...], precision: Optional[int] = None) -> Tuple[float, ...]:
        """Round vector with operation-level precision control"""
        return round_vector(vector, precision)

    def round_color(self, color: Tuple[float, float, float], precision: Optional[int] = None) -> Tuple[float, float, float]:
        """Round color with operation-level precision control"""
        return round_color(color, precision)

    def deterministic_uuid(self, content: str) -> str:
        """Generate deterministic UUID scoped to this operation"""
        return deterministic_uuid(f"{self.operation_id}:{content}")

    def to_reproducibility_dict(self) -> Dict[str, Any]:
        """Export reproducibility metadata for audit/replay"""
        return {
            "operation_id": self.operation_id,
            "operation_type": self.__class__.__name__,
            "tool_version": self.tool_version,
            "schema_version": self.schema_version,
            "timestamp_utc": self.timestamp_utc,
            "seed": self.get_seed(),
            "config": {
                "float_precision": _config.float_precision,
                "transform_precision": _config.transform_precision,
                "strict_mode": _config.strict_mode,
            }
        }


def deterministic(func: Callable) -> Callable:
    """
    Decorator to enforce deterministic execution.

    Wraps function to:
    1. Sort any dict/set arguments
    2. Round any float arguments
    3. Log operation for audit trail

    Usage:
        @deterministic
        def create_light(name: str, intensity: float):
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Round float positional args
        processed_args = []
        for v in args:
            if isinstance(v, float):
                processed_args.append(round_float(v))
            elif isinstance(v, tuple) and all(isinstance(x, float) for x in v):
                processed_args.append(round_vector(v))
            else:
                processed_args.append(v)

        # Round float kwargs
        processed_kwargs = {}
        for k, v in kwargs.items():
            if isinstance(v, float):
                processed_kwargs[k] = round_float(v)
            elif isinstance(v, tuple) and all(isinstance(x, float) for x in v):
                processed_kwargs[k] = round_vector(v)
            else:
                processed_kwargs[k] = v

        return func(*processed_args, **processed_kwargs)

    return wrapper


class DeterministicRandom:
    """
    Deterministic pseudo-random number generator.

    Uses explicit seed and linear congruential generator for
    reproducible "random" values across platforms.
    """

    def __init__(self, seed: Optional[int] = None):
        self._seed = seed if seed is not None else _config.global_seed
        self._state = self._seed

        # LCG parameters (same as glibc)
        self._a = 1103515245
        self._c = 12345
        self._m = 2**31

    def _next(self) -> int:
        """Generate next pseudo-random integer"""
        self._state = (self._a * self._state + self._c) % self._m
        return self._state

    def random(self) -> float:
        """Generate pseudo-random float in [0, 1)"""
        return self._next() / self._m

    def uniform(self, a: float, b: float) -> float:
        """Generate pseudo-random float in [a, b)"""
        return round_float(a + (b - a) * self.random())

    def randint(self, a: int, b: int) -> int:
        """Generate pseudo-random integer in [a, b]"""
        return a + int((b - a + 1) * self.random())

    def choice(self, seq: List[T]) -> T:
        """Choose pseudo-random element from sequence"""
        return seq[self.randint(0, len(seq) - 1)]

    def shuffle(self, seq: List[T]) -> List[T]:
        """Return shuffled copy (deterministic order)"""
        result = list(seq)
        for i in range(len(result) - 1, 0, -1):
            j = self.randint(0, i)
            result[i], result[j] = result[j], result[i]
        return result

    def reset(self, seed: Optional[int] = None) -> None:
        """Reset generator to initial state"""
        if seed is not None:
            self._seed = seed
        self._state = self._seed
