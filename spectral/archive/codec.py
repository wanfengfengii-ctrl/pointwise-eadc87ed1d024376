from fractions import Fraction
import json
import re

_NUMBER = re.compile(r"[+-]?(?:[0-9]+/[+-]?[0-9]+|[0-9]+(?:\.[0-9]*)?|\.[0-9]+)\Z")


def sequence(value, label):
    if not isinstance(value, (list, tuple)):
        raise ValueError(label + " must be an ordered list or tuple")
    return tuple(value)


def parse_rational(value):
    if isinstance(value, bool):
        raise ValueError("boolean is not a rational measurement")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, str) and _NUMBER.fullmatch(value):
        try:
            return Fraction(value)
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError("invalid rational") from exc
    raise ValueError("expected integer, Fraction or exact numeric string")


def _pack(value):
    if isinstance(value, Fraction):
        return {"$fraction": [value.numerator, value.denominator]}
    if value is None or type(value) in (str, int, bool):
        return value
    if isinstance(value, (tuple, list)):
        return [_pack(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("payload keys must be strings")
        if "$fraction" in value:
            raise ValueError("reserved payload key")
        return {key: _pack(item) for key, item in value.items()}
    raise ValueError("unsupported payload value")


def _unpack(value):
    if isinstance(value, list):
        return [_unpack(item) for item in value]
    if isinstance(value, dict):
        if "$fraction" in value:
            pair = value["$fraction"]
            if (set(value) != {"$fraction"} or not isinstance(pair, list)
                    or len(pair) != 2 or any(type(x) is not int for x in pair)
                    or pair[1] <= 0):
                raise ValueError("invalid fraction encoding")
            result = Fraction(*pair)
            if [result.numerator, result.denominator] != pair:
                raise ValueError("noncanonical fraction encoding")
            return result
        return {key: _unpack(item) for key, item in value.items()}
    if value is None or type(value) in (str, int, bool):
        return value
    raise ValueError("invalid payload encoding")


def encode_payload(value):
    return json.dumps(_pack(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def decode_payload(text):
    return _unpack(json.loads(text))
