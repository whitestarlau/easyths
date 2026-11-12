import time

from easyths.core import BaseOperation
from easyths.models.operations import ErrorCode, OperationResult
from easyths.operations.params import LimitOrderParams, format_price
from easyths.operations.results import LimitOrderResult


class BuyOperation(BaseOperation[LimitOrderParams]):
    """买入股票操作"""

    operation_name = "buy"
    description = "买入股票"
    Params = LimitOrderParams
    Result = LimitOrderResult

    def execute(self, params: LimitOrderParams) -> OperationResult:
        start_time = time.time()
        stock_code = params.stock_code
        price = format_price(stock_code, params.price)

        self.logger.info(
            "执行买入操作",
            stock_code=stock_code,
            price=price,
            quantity=params.quantity,
        )

        main_window = self.get_main_window(wrapper_obj=True)
        # 切换到别的页面再切回委托页面会清空可能残留的操作信息，增强操作可用性
        main_window.type_keys("{F3}")
        self.sleep(0.2)
        main_window.type_keys("{F1}")
        # 防抖
        self.sleep(0.25)
        main_panel = self.get_control_with_children(
            main_window,
            class_name="AfxMDIFrame140s",
            control_type="Pane",
            auto_id="59648",
        ).children(class_name="AfxMDIFrame140s")[0]

        # 1. 输入股票代码
        self.get_control_with_children(
            main_panel, control_type="Edit", auto_id="1032"
        ).type_keys(stock_code)
        self.sleep(0.08)
        # 2. 输入价格（清空后写入并回读校验，避免与自动填充值拼接）
        price_edit = self.get_control_with_children(
            main_panel, control_type="Edit", auto_id="1033"
        )
        if not self.set_edit_verified(price_edit, price):
            return self._fail(
                f"买入价格输入校验失败：期望 {price}，实际 {price_edit.window_text()!r}",
                ErrorCode.UI_ERROR,
            )
        self.sleep(0.08)
        # 3. 输入数量
        qty_edit = self.get_control_with_children(
            main_panel, control_type="Edit", auto_id="1034"
        )
        if not self.set_edit_verified(qty_edit, str(params.quantity)):
            return self._fail(
                f"买入数量输入校验失败：期望 {params.quantity}，实际 {qty_edit.window_text()!r}",
                ErrorCode.UI_ERROR,
            )
        # 等待输入数量后稳定在确认
        self.sleep(0.3)
        # 提交前再校验一次价格，防止客户端在此间隙自动填充覆盖
        if price_edit.window_text().strip() != price:
            if not self.set_edit_verified(price_edit, price):
                return self._fail(
                    f"买入价格在提交前被改写：期望 {price}，实际 {price_edit.window_text()!r}",
                    ErrorCode.UI_ERROR,
                )
        # 4. 提交委托
        main_window.type_keys("{ENTER}")
        self.wait_for_pop_dialog(0.3)
        # 没弹窗就是成功，这里已经假设用户已经按照项目设置好软件，
        # 为了加快操作速度，去掉了多余的弹窗处理（因为设置好软件后不会有弹窗）
        is_op_success = not self.is_exist_pop_dialog()
        # 证券名称，如果提交成功，stock_name 会清空
        stock_name = self.get_control_with_children(
            main_panel, control_type="Text", auto_id="1036"
        ).window_text()

        if not is_op_success:
            # 提交被拒，提取弹窗内容并关闭
            pop_dialog_title, pop_control = self.get_pop_dialog()
            if pop_dialog_title == "失败提示":
                message = self.get_control_with_children(
                    pop_control,
                    control_type="Image",
                    auto_id="1004",
                    class_name="Static",
                ).window_text()
                self.get_control_with_children(
                    pop_control,
                    control_type="Button",
                    auto_id="2",
                    class_name="Button",
                ).type_keys("{ENTER}")
                return self._fail(message, ErrorCode.CLIENT_REJECTED)
            return self._fail(
                f"买入提交被拒: {self.get_pop_dialog_content() or pop_dialog_title or '未知弹窗'}",
                ErrorCode.CLIENT_REJECTED,
            )
        if len(stock_name) > 0:
            # 表单未清空，说明委托没有真正提交
            return self._fail(
                "买入操作未能成功，请检查软件设置是否有与项目要求不符的地方",
                ErrorCode.UI_ERROR,
            )

        return self._ok(
            data=LimitOrderResult(
                stock_code=stock_code, price=params.price, quantity=params.quantity
            ).model_dump(),
            message=f"成功提交{stock_code}的买入委托，耗时{time.time() - start_time:.2f}秒",
        )
