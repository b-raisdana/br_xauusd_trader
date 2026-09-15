import MetaTrader5 as mt5
from global_state_variable import global_state
from numba import njit

__all__ = ["global_state"]


def initialize_execution_projection(param, XAU_ORDER_MARKET, XAU_BUY, param1, param2, param3, submitted_at):
    raise NotImplementedError("initialize_execution_projection function is not implemented yet.")


def project_execution_outcome(param, XAU_ORDER_MARKET, XAU_BUY, param1, param2, param3, submitted_at):
    raise NotImplementedError()


@njit
async def on_tick(tick: mt5.TICK):
    # submitted_at = pd.Timestamp("2026.09.06 10:00:00")

    # position, success = initialize_execution_projection(
    #     "REQ-M", XAU_ORDER_MARKET, XAU_BUY, 100.0, 96.0, 108.0, submitted_at
    # )
    # if not success:
    #     return False

    # position, success =
    # project_execution_outcome("REQ-M", XAU_ORDER_MARKET, XAU_BUY, 100.0, 96.0, 108.0, submitted_at)
    # if not success:
    #     return False

    # position, success = project_execution_outcome(
    #     (XAU_EXECUTION_MODIFY_REJECT,
    # submitted_at + 2, 0.0, 97.0, 110.0) or not nearly_equal(position.stop_loss, 96.0)
    # )
    # if not success:
    #     return False

    # position, success = project_execution_outcome(
    #     (XAU_EXECUTION_MODIFY, submitted_at + 3, 0.0, 97.0, 110.0)
    #     or not NearlyEqual(position.stop_loss, 97.0)
    #     or not NearlyEqual(position.take_profit, 110.0)
    # )
    # if not success:
    #     return False

    # position, success =
    # project_execution_outcome("REQ-M", XAU_ORDER_MARKET, XAU_BUY, 100.0, 96.0, 108.0, submitted_at)
    # if not success:
    #     return False

    raise NotImplementedError("on_tick function is not implemented yet.")
