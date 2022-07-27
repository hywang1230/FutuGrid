from peewee import *
from playhouse.shortcuts import ReconnectMixin
from app.config import *

db_setting = {'charset': 'utf8', 'sql_mode': 'PIPES_AS_CONCAT', 'use_unicode': True,
              'host': get_config()['db config']['host'],
              'port': int(get_config()['db config']['port']),
              'user': get_config()['db config']['user'],
              'password': get_config()['db config']['password']}


class ReconnectMySQLDatabase(ReconnectMixin, MySQLDatabase):
    def sequence_exists(self, seq):
        pass


database = ReconnectMySQLDatabase(get_config()['db config']['database'], **db_setting)


class UnknownField(object):
    def __init__(self, *_, **__): pass


class BaseModel(Model):
    class Meta:
        database = database


class GridConfig(BaseModel):
    stock_code = CharField(unique=True)
    market = CharField()
    base_price = DecimalField()
    rise_amplitude = DecimalField()
    fall_amplitude = DecimalField(null=True)
    amplitude_type = IntegerField(constraints=[SQL("DEFAULT 1")])
    single_sell_quantity = IntegerField()
    single_buy_quantity = IntegerField()
    max_sell_quantity = IntegerField()
    max_buy_quantity = IntegerField()
    remaining_sell_quantity = IntegerField()
    remaining_buy_quantity = IntegerField()
    gmt_create = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])
    gmt_modified = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])

    class Meta:
        table_name = 'grid_config'


class TradeOrder(BaseModel):
    stock_code = CharField(unique=True)
    market = CharField()
    order_id = CharField()
    price = DecimalField()
    quantity = IntegerField(null=True)
    direction = IntegerField(null=True)
    order_time = DateTimeField()
    status = CharField(constraints=[SQL("DEFAULT SUBMITTED")])
    fee = DecimalField(constraints=[SQL("DEFAULT 0")])
    finish_time = DateTimeField(null=True)
    gmt_create = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])
    gmt_modified = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])

    class Meta:
        table_name = 'trade_order'


def query_grid_config(stock_code):
    try:
        return GridConfig.get(GridConfig.stock_code == stock_code)
    except DoesNotExist:
        return None


def save_trade_order(stock_code, market, order_id, price, quantity, direction, order_time):
    trade_order = TradeOrder()
    trade_order.stock_code = stock_code
    trade_order.market = market
    trade_order.order_id = order_id
    trade_order.price = price
    trade_order.quantity = quantity
    trade_order.direction = direction
    trade_order.order_time = order_time

    trade_order.save()


def update_base_price_and_reminder_quantity(stock_code, price, quantity, is_sell):
    # if is_sell is true, remaining_sell_quantity = remaining_sell_quantity - quantity,
    # remaining_buy_quantity = remaining_buy_quantity + quantity,
    # if is_sell is false, remaining_sell_quantity = remaining_sell_quantity + quantity,
    # remaining_buy_quantity = remaining_buy_quantity - quantity
    grid_config = GridConfig.get(GridConfig.stock_code == stock_code)
    remaining_sell_quantity = grid_config.remaining_sell_quantity - quantity if is_sell \
        else grid_config.remaining_sell_quantity + quantity

    remaining_buy_quantity = grid_config.remaining_buy_quantity + quantity if is_sell \
        else grid_config.remaining_buy_quantity - quantity

    query = GridConfig.update(base_price=price, remaining_sell_quantity=remaining_sell_quantity,
                              remaining_buy_quantity=remaining_buy_quantity) \
        .where(GridConfig.stock_code == stock_code)

    query.execute()


def update_trade_order_status(order_id, price, status, time):
    query = TradeOrder.update(price=price, status=status, finish_time=time).where(TradeOrder.order_id == order_id)
    query.execute()


def update_trade_fee(order_id, fee):
    query = TradeOrder.update(fee=fee).where(TradeOrder.order_id == order_id)
    query.execute()
