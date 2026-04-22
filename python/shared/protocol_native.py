from __future__ import annotations

import hashlib
from dataclasses import dataclass

import base58
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils


_KECCAK_ROUNDS = (
    0x0000000000000001,
    0x0000000000008082,
    0x800000000000808A,
    0x8000000080008000,
    0x000000000000808B,
    0x0000000080000001,
    0x8000000080008081,
    0x8000000000008009,
    0x000000000000008A,
    0x0000000000000088,
    0x0000000080008009,
    0x000000008000000A,
    0x000000008000808B,
    0x800000000000008B,
    0x8000000000008089,
    0x8000000000008003,
    0x8000000000008002,
    0x8000000000000080,
    0x000000000000800A,
    0x800000008000000A,
    0x8000000080008081,
    0x8000000000008080,
    0x0000000080000001,
    0x8000000080008008,
)
_KECCAK_ROTATIONS = (
    (0, 36, 3, 41, 18),
    (1, 44, 10, 45, 2),
    (62, 6, 43, 15, 61),
    (28, 55, 25, 21, 56),
    (27, 20, 39, 8, 14),
)
_MASK_64 = (1 << 64) - 1

_SECP256K1_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_SECP256K1_G = (
    55066263022277343669578718895168534326250603453777594175500187360389116729240,
    32670510020758816978083085130507043184471273380659243275938904335757337482424,
)

VOUCHER_DOMAIN = None


@dataclass(frozen=True, slots=True)
class PaymentVoucherPayload:
    request_digest: str
    voucher_digest: str
    buyer_signature: str


def normalize_tron_address(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("address is required")
    raw = value.strip()
    if raw.startswith("0x") and len(raw) == 42:
        int(raw[2:], 16)
        return f"0x{raw[2:].lower()}"
    if len(raw) == 42 and raw.startswith("41"):
        int(raw, 16)
        return f"0x{raw[2:].lower()}"
    decoded = base58.b58decode(raw)
    if len(decoded) != 25:
        raise ValueError(f"invalid Tron address: {value}")
    payload, checksum = decoded[:-4], decoded[-4:]
    expected = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    if checksum != expected or len(payload) != 21 or payload[0] != 0x41:
        raise ValueError(f"invalid Tron address: {value}")
    return f"0x{payload[1:].hex()}"


def channel_id_of(*, buyer_address: str, seller_address: str, token_address: str) -> str:
    packed = (
        _address_bytes(buyer_address)
        + _address_bytes(seller_address)
        + _address_bytes(token_address)
    )
    return f"0x{keccak256(packed).hex()}"


def build_request_digest(*, method: str, path: str, body: str | bytes, request_deadline: int) -> str:
    normalized_method = method.upper().strip()
    if not normalized_method:
        raise ValueError("method is required")
    if not path.startswith("/"):
        raise ValueError("path must start with '/'")
    method_bytes = normalized_method.encode("ascii")
    path_bytes = path.encode("utf-8")
    body_bytes = body if isinstance(body, bytes) else (body or "").encode("utf-8")
    payload = b"".join(
        [
            len(method_bytes).to_bytes(2, "little"),
            method_bytes,
            len(path_bytes).to_bytes(2, "little"),
            path_bytes,
            _ethers_twos_be_bytes(int(request_deadline), bits=64),
            hashlib.sha256(body_bytes).digest(),
        ]
    )
    return f"0x{hashlib.sha256(payload).hexdigest()}"


def voucher_digest(
    *,
    contract_address: str,
    chain_id: int,
    channel_id: str,
    buyer_address: str,
    seller_address: str,
    token_address: str,
    amount_atomic: int,
    voucher_nonce: int,
    expires_at: int,
    request_deadline: int,
    request_digest: str,
) -> str:
    encoded = b"".join(
        [
            _bytes32(_voucher_domain()),
            _uint256(chain_id),
            _abi_address(contract_address),
            _bytes32(channel_id),
            _abi_address(buyer_address),
            _abi_address(seller_address),
            _abi_address(token_address),
            _uint256(amount_atomic),
            _uint256(voucher_nonce),
            _uint256(expires_at),
            _uint256(request_deadline),
            _bytes32(request_digest),
        ]
    )
    return f"0x{keccak256(encoded).hex()}"


def sign_digest(private_key: str, digest: str) -> str:
    digest_bytes = _bytes32(digest)
    private_value = int(private_key[2:] if private_key.startswith("0x") else private_key, 16)
    signer = ec.derive_private_key(private_value, ec.SECP256K1())
    der_signature = signer.sign(digest_bytes, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
    r, s = utils.decode_dss_signature(der_signature)
    if s > _SECP256K1_N // 2:
        s = _SECP256K1_N - s
    public_numbers = signer.public_key().public_numbers()
    recovery_id = _recover_id(
        r=r,
        s=s,
        digest_int=int.from_bytes(digest_bytes, "big"),
        public_key=(public_numbers.x, public_numbers.y),
    )
    v = 27 + recovery_id
    return f"0x{r.to_bytes(32, 'big').hex()}{s.to_bytes(32, 'big').hex()}{v:02x}"


def private_key_to_tron_address(private_key: str) -> str:
    private_value = int(private_key[2:] if private_key.startswith("0x") else private_key, 16)
    signer = ec.derive_private_key(private_value, ec.SECP256K1())
    public_numbers = signer.public_key().public_numbers()
    return _public_key_to_tron_address((public_numbers.x, public_numbers.y))


def recover_signer_address(*, digest: str, signature: str) -> str:
    signature_hex = signature[2:] if signature.startswith("0x") else signature
    if len(signature_hex) != 130:
        raise ValueError("signature must be 65 bytes long")
    r = int(signature_hex[:64], 16)
    s = int(signature_hex[64:128], 16)
    v = int(signature_hex[128:130], 16)
    recovery_id = v - 27 if v >= 27 else v
    if recovery_id not in {0, 1, 2, 3}:
        raise ValueError("invalid recovery id")
    digest_int = int.from_bytes(_bytes32(digest), "big")
    public_key = _recover_public_key(recovery_id=recovery_id, r=r, s=s, digest_int=digest_int)
    if public_key is None:
        raise ValueError("could not recover signer public key")
    return _public_key_to_tron_address(public_key)


def verify_digest_signature(*, digest: str, signature: str, signer_address: str) -> bool:
    recovered = recover_signer_address(digest=digest, signature=signature)
    return normalize_tron_address(recovered) == normalize_tron_address(signer_address)


def build_payment_voucher(
    *,
    buyer_private_key: str,
    chain_id: int,
    contract_address: str,
    channel_id: str,
    buyer_address: str,
    seller_address: str,
    token_address: str,
    amount_atomic: int,
    voucher_nonce: int,
    expires_at: int,
    request_deadline: int,
    method: str,
    path: str,
    body: str,
    request_digest: str | None = None,
) -> PaymentVoucherPayload:
    resolved_request_digest = request_digest or build_request_digest(
        method=method,
        path=path,
        body=body,
        request_deadline=request_deadline,
    )
    digest = voucher_digest(
        contract_address=contract_address,
        chain_id=chain_id,
        channel_id=channel_id,
        buyer_address=buyer_address,
        seller_address=seller_address,
        token_address=token_address,
        amount_atomic=amount_atomic,
        voucher_nonce=voucher_nonce,
        expires_at=expires_at,
        request_deadline=request_deadline,
        request_digest=resolved_request_digest,
    )
    return PaymentVoucherPayload(
        request_digest=resolved_request_digest,
        voucher_digest=digest,
        buyer_signature=sign_digest(buyer_private_key, digest),
    )


def keccak256(data: bytes) -> bytes:
    state = [0] * 25
    rate = 136
    padded = bytearray(data)
    padded.append(0x01)
    while len(padded) % rate != rate - 1:
        padded.append(0x00)
    padded.append(0x80)
    for offset in range(0, len(padded), rate):
        block = padded[offset : offset + rate]
        for lane in range(rate // 8):
            state[lane] ^= int.from_bytes(block[lane * 8 : (lane + 1) * 8], "little")
        _keccak_f1600(state)
    output = bytearray()
    while len(output) < 32:
        for lane in range(rate // 8):
            output.extend(state[lane].to_bytes(8, "little"))
        if len(output) >= 32:
            break
        _keccak_f1600(state)
    return bytes(output[:32])


def _voucher_domain() -> bytes:
    global VOUCHER_DOMAIN
    if VOUCHER_DOMAIN is None:
        VOUCHER_DOMAIN = keccak256(b"AIMICROPAY_V1")
    return VOUCHER_DOMAIN


def _keccak_f1600(state: list[int]) -> None:
    for rc in _KECCAK_ROUNDS:
        c = [state[x] ^ state[x + 5] ^ state[x + 10] ^ state[x + 15] ^ state[x + 20] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rotl(c[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                state[x + 5 * y] ^= d[x]

        b = [0] * 25
        for x in range(5):
            for y in range(5):
                b[y + 5 * ((2 * x + 3 * y) % 5)] = _rotl(state[x + 5 * y], _KECCAK_ROTATIONS[x][y])

        for x in range(5):
            for y in range(5):
                state[x + 5 * y] = b[x + 5 * y] ^ ((~b[((x + 1) % 5) + 5 * y]) & b[((x + 2) % 5) + 5 * y])

        state[0] ^= rc


def _rotl(value: int, shift: int) -> int:
    if shift == 0:
        return value
    return ((value << shift) | (value >> (64 - shift))) & _MASK_64


def _address_bytes(value: str) -> bytes:
    return bytes.fromhex(normalize_tron_address(value)[2:])


def _abi_address(value: str) -> bytes:
    return (b"\x00" * 12) + _address_bytes(value)


def _uint256(value: int) -> bytes:
    return int(value).to_bytes(32, "big", signed=False)


def _ethers_twos_be_bytes(value: int, *, bits: int) -> bytes:
    if value < 0:
        value = (1 << bits) + value
    width = max(1, (int(value).bit_length() + 7) // 8)
    return int(value).to_bytes(width, "big", signed=False)


def _bytes32(value: str | bytes) -> bytes:
    if isinstance(value, bytes):
        if len(value) != 32:
            raise ValueError("bytes32 value must be 32 bytes long")
        return value
    normalized = value[2:] if value.startswith("0x") else value
    raw = bytes.fromhex(normalized)
    if len(raw) != 32:
        raise ValueError("bytes32 value must be 32 bytes long")
    return raw


def _recover_id(*, r: int, s: int, digest_int: int, public_key: tuple[int, int]) -> int:
    for recovery_id in range(4):
        candidate = _recover_public_key(recovery_id=recovery_id, r=r, s=s, digest_int=digest_int)
        if candidate == public_key:
            return recovery_id
    raise ValueError("could not derive recovery id for secp256k1 signature")


def _recover_public_key(*, recovery_id: int, r: int, s: int, digest_int: int) -> tuple[int, int] | None:
    x = r + (recovery_id // 2) * _SECP256K1_N
    if x >= _SECP256K1_P:
        return None
    alpha = (pow(x, 3, _SECP256K1_P) + 7) % _SECP256K1_P
    beta = pow(alpha, (_SECP256K1_P + 1) // 4, _SECP256K1_P)
    y = beta if beta % 2 == recovery_id % 2 else _SECP256K1_P - beta
    point_r = (x, y)
    if _scalar_mult(_SECP256K1_N, point_r) is not None:
        return None
    r_inv = pow(r, -1, _SECP256K1_N)
    e = digest_int % _SECP256K1_N
    sr = _scalar_mult((s * r_inv) % _SECP256K1_N, point_r)
    eg = _scalar_mult((-e * r_inv) % _SECP256K1_N, _SECP256K1_G)
    return _point_add(sr, eg)


def _public_key_to_tron_address(public_key: tuple[int, int]) -> str:
    x, y = public_key
    encoded = b"\x04" + x.to_bytes(32, "big") + y.to_bytes(32, "big")
    hashed = keccak256(encoded[1:])
    payload = b"\x41" + hashed[-20:]
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    return base58.b58encode(payload + checksum).decode("ascii")


def _point_add(
    left: tuple[int, int] | None,
    right: tuple[int, int] | None,
) -> tuple[int, int] | None:
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2 and (y1 + y2) % _SECP256K1_P == 0:
        return None
    if left == right:
        slope = (3 * x1 * x1) * pow(2 * y1, -1, _SECP256K1_P)
    else:
        slope = (y2 - y1) * pow(x2 - x1, -1, _SECP256K1_P)
    slope %= _SECP256K1_P
    x3 = (slope * slope - x1 - x2) % _SECP256K1_P
    y3 = (slope * (x1 - x3) - y1) % _SECP256K1_P
    return (x3, y3)


def _scalar_mult(scalar: int, point: tuple[int, int] | None) -> tuple[int, int] | None:
    if point is None or scalar % _SECP256K1_N == 0:
        return None
    if scalar < 0:
        return _scalar_mult(-scalar, (point[0], (-point[1]) % _SECP256K1_P))
    result = None
    addend = point
    k = scalar
    while k:
        if k & 1:
            result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        k >>= 1
    return result
