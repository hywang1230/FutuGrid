# FutuGrid
利用富途API做的网格交易小程序
## 功能说明
本程序是通过监控到价来触发交易，实现自动交易的行为。
目前支持价格百分比波动以及金额数值的波动。
整体流程如图所示：![img.png](img.png)
## 支持的范围
* 美股（仅支持盘中交易）

## 使用 
### Step1：创建mysql数据库导入，执行sql
```sql
CREATE TABLE `grid_config` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键',
  `stock_code` varchar(16) NOT NULL COMMENT '股票代码',
  `market` char(2) NOT NULL COMMENT '市场：US.美股，HK.港股',
  `base_price` decimal(20,8) NOT NULL COMMENT '基础价',
  `rise_amplitude` decimal(20,8) NOT NULL COMMENT '上升幅度',
  `fall_amplitude` decimal(20,8) DEFAULT NULL COMMENT '下跌幅度',
  `amplitude_type` int NOT NULL DEFAULT '1' COMMENT '幅度类型：1.百分比，2.价格',
  `single_sell_quantity` int NOT NULL COMMENT '单次卖出数量',
  `single_buy_quantity` int NOT NULL COMMENT '单次买入数量',
  `max_sell_quantity` int NOT NULL COMMENT '最大净卖出数量',
  `max_buy_quantity` int NOT NULL COMMENT '最大净买入数量',
  `remaining_sell_quantity` int NOT NULL COMMENT '剩余可卖出数量',
  `remaining_buy_quantity` int NOT NULL COMMENT '剩余可买入数量',
  `gmt_create` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `gmt_modified` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_stock_code` (`stock_code`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='网格配置';

CREATE TABLE `trade_order` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键',
  `stock_code` varchar(16) NOT NULL COMMENT '股票代码',
  `market` char(2) NOT NULL COMMENT '市场：US.美股，HK.港股',
  `order_id` varchar(32) NOT NULL COMMENT '订单号',
  `price` decimal(20,8) NOT NULL COMMENT '价格',
  `quantity` int DEFAULT NULL COMMENT '数量',
  `direction` int DEFAULT NULL COMMENT '方向：1.sell，2.buy',
  `order_time` timestamp NOT NULL COMMENT '下单时间',
  `status` varchar(32) NOT NULL DEFAULT 'SUBMITTED' COMMENT '状态：采用富途的订单状态',
  `fee` decimal(20,8) DEFAULT '0.00000000' COMMENT '费用',
  `finish_time` timestamp NULL DEFAULT NULL COMMENT '结束时间，即成交时间或撤单时间',
  `gmt_create` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `gmt_modified` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_order_id` (`order_id`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='订单信息';
```
### step2：向数据库导入配置
```mysql-sql
insert into grid_config(market, base_price, rise_amplitude, fall_amplitude, amplitude_type, single_sell_quantity, single_buy_quantity, max_sell_quantity, max_buy_quantity, remaining_sell_quantity, remaining_buy_quantity) values('US.股票代码', 'US', '基础价', '涨幅', '跌幅', '幅度类型：1.百分比，2.价格', '单次卖出量', '单次买入量', '最大卖出量', '最大买入量', '剩余卖出量，填最大卖出量', '剩余买入入量，填最大买入量');
```
### Step3：创建配置文件config.ini
```ini
[db config]
host=192.168.1.254
port=3306
user=root
password=Abc123789
database=futu_grid

[futu config]
host=192.168.1.254
port=11111
unlock_password_md5=55587a910882016321201e6ebbc9f595
```
#### unlock_password_md5生成方式
1. 打开https://tool.chinaz.com/tools/md5.aspx 
2. 选择32位小
3. 输入交易密码，点击加密，生成md5

### Step4：生成RSA密钥，将私钥写到文件rsa中，文件名就叫rsa，无后缀，具体密钥生成参考https://openapi.futunn.com/futu-api-doc/qa/other.html#4601

### Step5：部署docker
```docker
docker run -d --restart=always -v /app/config.ini:/app/config.ini /app/rsa:/app/config.ini  --name="futu_grid" pionnerwang/futu_grid
```