from decimal import Decimal, InvalidOperation
from .domain import RuleError


def text(data, key, limit=1000, required=True):
    value = str(data.get(key, '')).strip()
    if (required and not value) or len(value) > limit:
        raise RuleError(f'{key.replace("_", " ").capitalize()} is required and must be at most {limit} characters.')
    return value


def integer(data, key, default=None):
    try:
        value = str(data.get(key, default))
        if not value.isdigit():
            raise ValueError
        return int(value)
    except (TypeError, ValueError):
        raise RuleError(f'Enter a valid {key.replace("_", " ")}.') from None


def choice(data, key, values):
    value = data.get(key)
    if value not in values:
        raise RuleError(f'Choose a valid {key.replace("_", " ")}.')
    return value


def money(data, key):
    raw = str(data.get(key, '')).strip()
    if not raw:
        return None
    try:
        value = Decimal(raw)
        if not value.is_finite() or value < 0 or value > 100000000 or value.as_tuple().exponent < -2:
            raise InvalidOperation
        return int(value * 100)
    except InvalidOperation:
        raise RuleError(f'{key.replace("_", " ")} must be a nonnegative AED amount with at most two decimals, or blank for Unknown.') from None
