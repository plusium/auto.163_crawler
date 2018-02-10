#!/usr/bin/env python
# encoding: utf-8

from urllib import request
from urllib import error
import gzip
import re
import sqlite3


# settings
url_domain = 'http://product.auto.163.com/'
url_config = url_domain + 'series/config1/%s.html'
url_product = url_domain + 'config_compare/%s.html'
str_no_config = '即将上市 ,具体参数配置敬请期待！'
str_fuel_space = '                                    '  # 【官方油耗(L)】配置项中的空格
urls = (
    'firstchar/0/',
)
headers = {
    "Proxy-Connection": "keep-alive",
    "Cache-Control": "max-age=0",
    "Upgrade-Insecure-Requests": "1",
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.101 Safari/537.36',
    "Accept": "text/plain, text/html",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.8,en;q=0.6",
    "referer": url_domain
}
# 各类搜索用正则表达式
# 所有车系编号
pattern_series_ids = re.compile(r'/series/(\d+).html')
# 品牌
pattern_brand_name = re.compile(r"brand_name:'([^']*)'")
# 车系
pattern_series_name = re.compile(r"series_name:'([^']*)'")
# 配置名、字段名
pattern_config_type = re.compile(r'<div class="cell"><span class="cell_text" title="([^"]*)" data-key="([^"]+)"')
# 年份、车型、指导价
pattern_config_list1 = re.compile(r"year:'([^']*)',.+,product_name:'([^']*)',price:'([^']*)'")
pattern_config_list_for_product = re.compile(r"series_id:'(\d+)',.+,series_name:'([^']*)',product_name:'([^']*)',price:'([^']*)'")
# 其他配置
pattern_config_list2 = re.compile(r'<div class="cell"><span class="cell_text">(.*?)</span></div>')


# 所有车系编号
series_ids = []
# 所有车型编号
product_ids = ['000BBGCG', '000BQENX']  # 旧款别克君越 旧款驭胜S350
# 数据库字段列表
list_columns = ['series_id', 'series_name', 'brand_name', 'config_year', 'config_name', 'config_price']
# 数据库字段名列表
list_columns_name = ['车系编号', '车系', '品牌', '年份', '车型', '指导价']

# 数据记录的字段列表及数据列表 每个元素又是一个列表，代表一条记录
list_records_column = []
list_records = []

# 用于统计的计数器
count_done_series = 0
count_done_config = 0
count_done_product = 0


# 找到所有车系编号
def get_series_ids():
    global series_ids
    for url in urls:
        req = request.Request(url_domain + url)
        req.headers = headers

        try:
            res = request.urlopen(req)
            content = gzip.decompress(res.read()).decode('gb2312', 'ignore')
            ids = pattern_series_ids.findall(content)
            series_ids = series_ids + ids
            print('找到车系数:%d' % len(ids))
        except error.HTTPError as e:
            print('series_ids request error:' + e.code)
    # 去重
    series_ids = list(set(series_ids))
    print('找到总车系数:%d' % len(series_ids))
    print(series_ids)


# 将新找到的字段加入列表
def add_column(column_id, column_name):
    if column_id not in list_columns:
        list_columns.append(column_id)
        list_columns_name.append(column_name)


get_series_ids()
# 循环抓取所有车系配置页面 start
for series_id in series_ids:
    req = request.Request(url_config % series_id)
    req.headers = headers

    try:
        res = request.urlopen(req)
        content = gzip.decompress(res.read()).decode('gb2312', 'ignore')
    except error.HTTPError as e:
        print('config request error:' + e.code + ',series_id:' + series_id)

    if content.find(str_no_config) >= 0:
        continue

    # 车系
    match = pattern_series_name.search(content)
    if not match:
        # 没有配置，跳过
        continue
    series_name = match.group(1)

    # 品牌
    match = pattern_brand_name.search(content)
    if not match:
        # 没有配置，跳过
        continue
    brand_name = match.group(1)

    # 公共字段
    one_record_column = ['series_id', 'series_name', 'brand_name', 'config_year', 'config_name', 'config_price']

    # 配置名、字段名
    config_types = pattern_config_type.findall(content)
    for one_config_type in config_types:
        add_column(one_config_type[1], one_config_type[0])
        one_record_column.append(one_config_type[1])

    # 年份、车型、指导价
    config_list1 = pattern_config_list1.findall(content)

    # 先精简字符串
    start_index = content.find('car_config_param_list')
    end_index = content.find('car_config_guide')
    if start_index == -1 or end_index == -1:
        # 没有配置，跳过
        continue
    content = content[start_index:end_index]
    content = content.replace('\r\n', '')
    content = content.replace('\t', '')

    # 其他配置
    config_list2 = pattern_config_list2.findall(content)

    # 配置项数量检查
    config_types_count = len(config_types)
    config_count = len(config_list1)
    item_count = len(config_list2)
    if item_count != (config_types_count * config_count):
        print('item_count error:series_id:%s,configs:%s,types:%s,items:%s'
              % (series_id, config_count, config_types_count, item_count))
        continue

    # 该车型的所有记录列表
    all_records = []
    for one_config in config_list1:
        # 循环以初始化各条车型记录
        all_records.append([str(series_id), series_name, brand_name, one_config[0], one_config[1], one_config[2]])

    # 依次取出单条车型记录，并在其后添加新的配置项
    all_records_index = 0
    for one_config in config_list2:
        # 取出单条车型记录
        one_record = all_records[all_records_index]
        # 继续添加其他配置项
        one_data = one_config.strip()
        # 针对【官方油耗(L)】这一列数据的特殊处理
        one_data = one_data.replace(str_fuel_space, '')
        # 有些数据里有双引号 替换成全角 TODO 有些可能要替换成【“】
        one_data = one_data.replace('"', '”')
        one_record.append(one_data)
        # 切换到下一个车型
        all_records_index = all_records_index + 1
        if all_records_index == config_count:
            all_records_index = 0

    # 放入总列表
    for one_record in all_records:
        # 有多少个车型 则添加多少组列名
        list_records_column.append(one_record_column)
        list_records.append(one_record)

    count_done_series = count_done_series + 1
# 循环抓取所有车系配置页面 end

print('已分析车系数:%d' % count_done_series)
print('已分析车型数:%d' % len(list_records))

print('找到零散的车型数:%d' % len(product_ids))
# 循环抓取所有车型配置页面 start
for product_id in product_ids:
    req = request.Request(url_product % product_id)
    req.headers = headers

    try:
        res = request.urlopen(req)
        content = gzip.decompress(res.read()).decode('gb2312', 'ignore')
    except error.HTTPError as e:
        print('config request error:' + e.code + ',product_id:' + product_id)

    if content.find(str_no_config) >= 0:
        continue

    # 公共字段
    one_record_column = ['series_id', 'series_name', 'config_name', 'config_price']

    # 配置名、字段名
    config_types = pattern_config_type.findall(content)
    for one_config_type in config_types:
        add_column(one_config_type[1], one_config_type[0])
        one_record_column.append(one_config_type[1])

    # 车系编号、车系、车型、指导价
    match = pattern_config_list_for_product.search(content)
    if not match:
        # 没有配置，跳过
        continue
    series_id = match.group(1)
    series_name = match.group(2)
    config_name = match.group(3)
    config_price = match.group(4)

    # 先精简字符串
    start_index = content.find('car_config_param_list')
    end_index = content.find('car_config_guide')
    if start_index == -1 or end_index == -1:
        # 没有配置，跳过
        continue
    content = content[start_index:end_index]
    content = content.replace('\r\n', '')
    content = content.replace('\t', '')

    # 其他配置
    config_list2 = pattern_config_list2.findall(content)

    # 配置项数量检查
    config_types_count = len(config_types)
    item_count = len(config_list2)
    if item_count != config_types_count:
        print('item_count error:product_id:%s,types:%s,items:%s'
              % (product_id, config_types_count, item_count))
        continue

    # 该车型的所有记录
    one_record = [str(series_id), series_name, config_name, config_price]

    # 在其后添加新的配置项
    for one_config in config_list2:
        # 继续添加其他配置项
        one_data = one_config.strip()
        # 针对【官方油耗(L)】这一列数据的特殊处理
        one_data = one_data.replace(str_fuel_space, '')
        # 有些数据里有双引号 替换成全角 TODO 有些可能要替换成【“】
        one_data = one_data.replace('"', '”')
        one_data = one_data.replace('&nbsp;', ' ')
        one_data = one_data.strip()
        one_record.append(one_data)

    # 放入总列表
    list_records_column.append(one_record_column)
    list_records.append(one_record)

    count_done_product = count_done_product + 1
# 循环抓取所有车型配置页面 end

print('已分析零散的车型数:%d' % count_done_product)

# 数据库操作
sql_droptable_config = 'drop table if exists t_configs'
sql_createtable_config = 'create table t_configs (config_id varchar(50), config_name varchar(50))'
sql_insert_config = 'insert into t_configs values ("%s", "%s")'

sql_droptable = 'drop table if exists t_cars'
sql_createtable = 'create table t_cars (%s varchar(50))'
sql_insert = 'insert into t_cars values ("%s")'
sql_insert2 = 'insert into t_cars (%s) values ("%s")'

conn = sqlite3.connect('cars.db')
cursor = conn.cursor()

cursor.execute(sql_droptable_config)
cursor.execute(sql_createtable_config)
for config_id, config_name in zip(list_columns, list_columns_name):
    sql = sql_insert_config % (config_id, config_name)
    cursor.execute(sql)

cursor.execute(sql_droptable)
cursor.execute(sql_createtable % ' varchar(50),'.join(list_columns))

# 插入一行列名数据 之后可以通过 where rowid=1 取得这行数据
cursor.execute(sql_insert % '","'.join(list_columns_name))

for one_column, one_record in zip(list_records_column, list_records):
    try:
        sql = sql_insert2 % (','.join(one_column), '","'.join(one_record))
        cursor.execute(sql)
        count_done_config = count_done_config + 1
    except sqlite3.Error as e:
        print('db error:' + e.args[0] + ',sql:' + sql)
print('已保存车型数:%d' % count_done_config)
cursor.close()
conn.commit()
conn.close()
