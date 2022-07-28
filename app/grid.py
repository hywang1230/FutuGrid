from futu import *
from app.db import *
import pandas as pd
from app.log import *
import datetime
from app.config import *
from app.stock_helper import *

host = get_config()['futu config']['host']
port = int(get_config()['futu config']['port'])
unlock_password_md5 = get_config()['futu config']['unlock_password_md5']

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('max_colwidth', None)
SysConfig.enable_proto_encrypt(is_encrypt=True)
SysConfig.set_init_rsa_file("./rsa")


class PriceReminder(PriceReminderHandlerBase):
    def on_recv_rsp(self, rsp_pb):
        ret_code, content = super(PriceReminder, self).on_recv_rsp(rsp_pb)
        logging.info('receive price reminder msg, content: %s', content)
        if ret_code != RET_OK:
            logging.error("PriceReminder: error, msg: %s", content)
            return

        stock_code = content['code']
        grid_config = query_grid_config(stock_code)

        if grid_config is None:
            logging.info('no grid config of stock_code[%s]', stock_code)
            return

        price = content['price']
        is_sell = content['reminder_type'] == 'PRICE_UP'
        success = order(stock_code, price, is_sell)

        if not success:
            logging.error('stock_code[%s] order fail', stock_code)
            reset_price_reminder(stock_code, grid_config.base_price)


class TradeOrderHandler(TradeOrderHandlerBase):
    """ order update push"""

    def on_recv_rsp(self, rsp_pb):
        ret, content = super(TradeOrderHandler, self).on_recv_rsp(rsp_pb)
        logging.info('receive trade order msg, content: %s', content)
        if ret == RET_OK:
            if content['trd_env'][0] == 'SIMULATE':
                return

            order_status = content['order_status'][0]
            if order_status in ('CANCELLED_ALL', 'FILLED_ALL'):
                stock_code = content['code'][0]
                grid_config = GridConfig.get(GridConfig.stock_code == stock_code)

                if grid_config is None:
                    logging.info('no grid config of stock_code[%s]', stock_code)
                    return

                price = content['dealt_avg_price'][0]
                order_id = content['order_id'][0]
                finish_time = content['updated_time'][0]
                base_price = float(grid_config.base_price)

                update_trade_order_status(order_id, price, order_status, finish_time)

                if order_status == 'FILLED_ALL':
                    qty = content['dealt_qty'][0]
                    is_sell = content['trd_side'][0] in ('SELL', 'SELL_SHORT')

                    base_price = calculate_amplitude_price(base_price, grid_config, is_sell)

                    update_base_price_and_reminder_quantity(stock_code, base_price, qty, is_sell)

                    fee = calculate_fee(price, qty, is_sell, grid_config.market)

                    update_trade_fee(order_id, round(fee, 2))

                reset_price_reminder(stock_code, base_price)


quote_ctx = OpenQuoteContext(host=host, port=port)
quote_ctx.set_handler(PriceReminder())

trd_ctx = {'US': OpenSecTradeContext(filter_trdmarket=TrdMarket.US, host=host, port=port,
                                     security_firm=SecurityFirm.FUTUSECURITIES),
           'HK': OpenSecTradeContext(filter_trdmarket=TrdMarket.HK, host=host, port=port,
                                     security_firm=SecurityFirm.FUTUSECURITIES)}
trd_ctx['US'].set_handler(TradeOrderHandler())
trd_ctx['HK'].set_handler(TradeOrderHandler())


def reset_price_reminder(stock_code, price):
    grid_config = query_grid_config(stock_code)

    if grid_config is None:
        logging.info('no grid config of stock_code[%s]', stock_code)
        return False

    ret_ask, ask_data = quote_ctx.set_price_reminder(code=stock_code, op=SetPriceReminderOp.DEL_ALL)
    if ret_ask == RET_OK:
        # set price up
        if grid_config.remaining_sell_quantity > 0:
            reminder_price = calculate_amplitude_price(price, grid_config, True)
            ret_ask, ask_data = quote_ctx.set_price_reminder(code=stock_code, op=SetPriceReminderOp.ADD,
                                                             reminder_type=PriceReminderType.PRICE_UP,
                                                             reminder_freq=PriceReminderFreq.ONCE,
                                                             value=reminder_price)
            if ret_ask == RET_OK:
                logging.info('set price up success, stock_code=%s, reminder_price=%s', stock_code, reminder_price)
            else:
                logging.error('error:%s', ask_data)

        # set price down
        if grid_config.remaining_buy_quantity > 0:
            reminder_price = calculate_amplitude_price(price, grid_config, False)
            ret_ask, ask_data = quote_ctx.set_price_reminder(code=stock_code, op=SetPriceReminderOp.ADD,
                                                             reminder_type=PriceReminderType.PRICE_DOWN,
                                                             reminder_freq=PriceReminderFreq.ONCE,
                                                             value=reminder_price)
            if ret_ask == RET_OK:
                logging.info('set price down success, stock_code=%s, reminder_price=%s', stock_code, reminder_price)
            else:
                logging.error('error:%s', ask_data)

    else:
        logging.error('error:%s', ask_data)


def order(stock_code, price, is_sell):
    # get stock code grid config
    grid_config = query_grid_config(stock_code)
    if grid_config is None:
        logging.info('no grid config of stock_code[%s]', stock_code)
        return False

    # check now is in trade time
    now = datetime.datetime.now().strftime('%H:%M:%S')
    if (grid_config.market == 'US' and '04:00:00' < now < '21:30:00') \
            or (grid_config.market == 'HK' and (now < '09:30:00' or now > '16:00:00')):
        logging.info('%s is not in trade time', now)
        return False

    # check reminder quantity > 0
    reminder_quantity = grid_config.remaining_sell_quantity if is_sell else grid_config.remaining_buy_quantity
    if reminder_quantity <= 0:
        logging.info('stock_code[%s] reminder_quantity is zero', stock_code)
        return False

    # only support us
    ret, data = trd_ctx[grid_config.market].unlock_trade(password_md5=unlock_password_md5)  # 若使用真实账户下单，需先对账户进行解锁。
    success = False
    if ret == RET_OK:
        trd_side = TrdSide.SELL if is_sell else TrdSide.BUY
        qty = grid_config.single_sell_quantity if is_sell else grid_config.single_buy_quantity

        ret, data = trd_ctx[grid_config.market].place_order(price=price, qty=qty, code=stock_code, trd_side=trd_side,
                                                            fill_outside_rth=False, order_type=OrderType.MARKET,
                                                            trd_env=TrdEnv.REAL)
        if ret == RET_OK:
            logging.info('place order success, stock_code={}, price={}, quantity={}, is_sell={}'.format(stock_code,
                                                                                                        price, qty,
                                                                                                        is_sell))
            save_trade_order(stock_code, grid_config.market, data['order_id'][0], price, qty, 1 if is_sell else 2,
                             data['create_time'][0])

            success = True
        else:
            logging.error('place_order error: %s', data)
    else:
        logging.error('unlock_trade failed: %s', data)

    return success


def start():
    grid_configs = GridConfig.select()

    for grid_config in grid_configs:
        reset_price_reminder(grid_config.stock_code, float(grid_config.base_price))
