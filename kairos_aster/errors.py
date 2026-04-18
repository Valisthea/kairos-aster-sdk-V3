"""
AsterDEX error codes — complete mapping from official V3 docs.

Usage:
    from kairos_aster.errors import AsterAPIError, ERRORS

    try:
        client.place_order(...)
    except AsterAPIError as e:
        print(e.code, e.message, e.explanation)
"""

from __future__ import annotations


class AsterAPIError(Exception):
    """Raised when AsterDEX API returns an error response."""

    def __init__(self, code: int, msg: str) -> None:
        self.code = code
        self.message = msg
        self.explanation = ERRORS.get(code, "Unknown error code")
        super().__init__(f"AsterDEX ({code}): {msg} — {self.explanation}")

    @property
    def is_rate_limit(self) -> bool:
        return self.code in (-1003, -1015)

    @property
    def is_signature_error(self) -> bool:
        return self.code in (-1000, -1022)

    @property
    def is_insufficient_balance(self) -> bool:
        return self.code in (-2018, -2019, -4050, -4051)

    @property
    def is_order_rejected(self) -> bool:
        return self.code in (-2010, -2020, -2021, -2022)


class AsterRequestError(Exception):
    """Raised on HTTP-level failures (timeout, connection, 5xx)."""

    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text
        super().__init__(f"HTTP {status_code}: {text}")


# ---------- Complete error code map ----------

ERRORS: dict[int, str] = {
    # 10xx — General Server / Network
    -1000: "UNKNOWN — Unknown error processing request",
    -1001: "DISCONNECTED — Internal error, retry",
    -1002: "UNAUTHORIZED — Not authorized",
    -1003: "TOO_MANY_REQUESTS — Rate limit hit",
    -1004: "DUPLICATE_IP — IP already whitelisted",
    -1005: "NO_SUCH_IP — IP not whitelisted",
    -1006: "UNEXPECTED_RESP — Unexpected message bus response",
    -1007: "TIMEOUT — Backend timeout, status unknown",
    -1010: "ERROR_MSG_RECEIVED",
    -1011: "NON_WHITE_LIST — IP cannot access route",
    -1013: "INVALID_MESSAGE",
    -1014: "UNKNOWN_ORDER_COMPOSITION — Unsupported order combination",
    -1015: "TOO_MANY_ORDERS — Order rate limit",
    -1016: "SERVICE_SHUTTING_DOWN",
    -1020: "UNSUPPORTED_OPERATION",
    -1022: "INVALID_SIGNATURE — Signature check failed",
    -1023: "START_TIME_GREATER_THAN_END_TIME",

    # 11xx — Request Issues
    -1100: "ILLEGAL_CHARS — Illegal characters in parameter",
    -1101: "TOO_MANY_PARAMETERS",
    -1102: "MANDATORY_PARAM_EMPTY_OR_MALFORMED",
    -1103: "UNKNOWN_PARAM",
    -1104: "UNREAD_PARAMETERS",
    -1105: "PARAM_EMPTY",
    -1106: "PARAM_NOT_REQUIRED",
    -1108: "BAD_ASSET — Invalid asset",
    -1109: "BAD_ACCOUNT — Invalid account",
    -1110: "BAD_INSTRUMENT_TYPE",
    -1111: "BAD_PRECISION — Precision over max",
    -1112: "NO_DEPTH — No orders on book",
    -1113: "WITHDRAW_NOT_NEGATIVE",
    -1114: "TIF_NOT_REQUIRED",
    -1115: "INVALID_TIF — Invalid timeInForce",
    -1116: "INVALID_ORDER_TYPE",
    -1117: "INVALID_SIDE",
    -1118: "EMPTY_NEW_CL_ORD_ID",
    -1119: "EMPTY_ORG_CL_ORD_ID",
    -1120: "BAD_INTERVAL",
    -1121: "BAD_SYMBOL — Invalid symbol",
    -1125: "INVALID_LISTEN_KEY",
    -1127: "MORE_THAN_XX_HOURS — Interval too large",
    -1128: "OPTIONAL_PARAMS_BAD_COMBO",
    -1130: "INVALID_PARAMETER",
    -1136: "INVALID_NEW_ORDER_RESP_TYPE",

    # 20xx — Processing Issues
    -2010: "NEW_ORDER_REJECTED",
    -2011: "CANCEL_REJECTED",
    -2013: "NO_SUCH_ORDER — Order does not exist",
    -2014: "BAD_API_KEY_FMT",
    -2015: "REJECTED_MBX_KEY — Invalid API-key, IP, or permissions",
    -2016: "NO_TRADING_WINDOW",
    -2018: "BALANCE_NOT_SUFFICIENT",
    -2019: "MARGIN_NOT_SUFFICIENT",
    -2020: "UNABLE_TO_FILL",
    -2021: "ORDER_WOULD_IMMEDIATELY_TRIGGER",
    -2022: "REDUCE_ONLY_REJECT",
    -2023: "USER_IN_LIQUIDATION",
    -2024: "POSITION_NOT_SUFFICIENT",
    -2025: "MAX_OPEN_ORDER_EXCEEDED",
    -2026: "REDUCE_ONLY_ORDER_TYPE_NOT_SUPPORTED",
    -2027: "MAX_LEVERAGE_RATIO — Exceeded max position at current leverage",
    -2028: "MIN_LEVERAGE_RATIO — Insufficient margin for leverage",

    # 40xx — Filters & Validation
    -4000: "INVALID_ORDER_STATUS",
    -4001: "PRICE_LESS_THAN_ZERO",
    -4002: "PRICE_GREATER_THAN_MAX_PRICE",
    -4003: "QTY_LESS_THAN_ZERO",
    -4004: "QTY_LESS_THAN_MIN_QTY",
    -4005: "QTY_GREATER_THAN_MAX_QTY",
    -4006: "STOP_PRICE_LESS_THAN_ZERO",
    -4007: "STOP_PRICE_GREATER_THAN_MAX_PRICE",
    -4013: "PRICE_LESS_THAN_MIN_PRICE",
    -4014: "PRICE_NOT_INCREASED_BY_TICK_SIZE",
    -4015: "INVALID_CL_ORD_ID_LEN — Max 36 chars",
    -4016: "PRICE_HIGHER_THAN_MULTIPLIER_UP",
    -4023: "QTY_NOT_INCREASED_BY_STEP_SIZE",
    -4024: "PRICE_LOWER_THAN_MULTIPLIER_DOWN",
    -4026: "COMMISSION_INVALID",
    -4028: "INVALID_LEVERAGE",
    -4031: "INVALID_WORKING_TYPE",
    -4044: "INVALID_BALANCE_TYPE",
    -4045: "MAX_STOP_ORDER_EXCEEDED",
    -4046: "NO_NEED_TO_CHANGE_MARGIN_TYPE",
    -4047: "MARGIN_TYPE_CHANGE_OPEN_ORDERS — Close open orders first",
    -4048: "MARGIN_TYPE_CHANGE_POSITION — Close positions first",
    -4049: "ADD_ISOLATED_MARGIN_REJECT — Isolated only",
    -4050: "CROSS_BALANCE_INSUFFICIENT",
    -4051: "ISOLATED_BALANCE_INSUFFICIENT",
    -4055: "AMOUNT_MUST_BE_POSITIVE",
    -4056: "INVALID_API_KEY_TYPE",
    -4059: "NO_NEED_TO_CHANGE_POSITION_SIDE",
    -4060: "INVALID_POSITION_SIDE",
    -4061: "POSITION_SIDE_NOT_MATCH",
    -4062: "REDUCE_ONLY_CONFLICT",
    -4082: "INVALID_BATCH_PLACE_ORDER_SIZE",
    -4083: "PLACE_BATCH_ORDERS_FAIL",
    -4084: "UPCOMING_METHOD — Not available yet",
    -4087: "REDUCE_ONLY_ORDER_PERMISSION",
    -4088: "NO_PLACE_ORDER_PERMISSION",
    -4104: "INVALID_CONTRACT_TYPE",
    -4118: "REDUCE_ONLY_MARGIN_CHECK_FAILED",
    -4131: "MARKET_ORDER_REJECT — Fails PERCENT_PRICE filter",
    -4135: "INVALID_ACTIVATION_PRICE",
    -4137: "QUANTITY_EXISTS_WITH_CLOSE_POSITION",
    -4138: "REDUCE_ONLY_MUST_BE_TRUE",
    -4141: "SYMBOL_ALREADY_CLOSED",
    -4142: "STRATEGY_INVALID_TRIGGER_PRICE — TP/SL would trigger immediately",
    -4161: "ISOLATED_LEVERAGE_REJECT_WITH_POSITION",
    -4164: "MIN_NOTIONAL — Order notional too small (min 5 USDT)",
    -4183: "PRICE_HIGHER_THAN_STOP_MULTIPLIER_UP",
    -4184: "PRICE_LOWER_THAN_STOP_MULTIPLIER_DOWN",
}
