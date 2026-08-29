import hashlib


def _derive_seed(master_seed: int, label: str) -> int:
    """Derives a deterministic uint32 seed from a master seed and a string label."""
    key = f"{master_seed}:{label}".encode('utf-8')
    h = hashlib.sha256(key).digest()
    val = int.from_bytes(h[:4], byteorder='big')
    return val % (2**31 - 1)


def make_seeds(master_seed: int, cell_id: str) -> dict:
    """
    Returns deterministic, independent random seed streams for a given master_seed and cell_id.

    Pairing Invariant:
    'market', 'oracle', 'exchange', 'background', and 'latency' seeds depend ONLY on master_seed.
    They are identical across all conditions (C1..C5) for the same master_seed.
    Only 'policy' depends on both master_seed and cell_id.
    """
    return {
        'market': _derive_seed(master_seed, 'market'),
        'oracle': _derive_seed(master_seed, 'oracle'),
        'exchange': _derive_seed(master_seed, 'exchange'),
        'background': _derive_seed(master_seed, 'background'),
        'latency': _derive_seed(master_seed, 'latency'),
        'policy': _derive_seed(master_seed, f"policy:{cell_id}")
    }
