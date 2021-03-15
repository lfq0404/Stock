#!/usr/bin/env python
# encoding: utf-8
'''
@author: lifengqi
@license: SCOUT
@contact: fengqi_li@sina.cn
@software: scout
@file: deal.py
@time: 21-2-24 下午4:40
@desc:
'''
import datetime
import requests
import time
import pandas as pd


class JeremyDeal:
    # 请求网易的头
    headers = {
        'Connection': 'Keep-Alive',
        'Accept': 'text/html, application/xhtml+xml, */*',
        'Accept-Language': 'zh-CN,zh;q=0.8',
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; WOW64; Trident/7.0; rv:11.0) like Gecko'
    }

    def get_stock_history_by_code(self, stock_type, stock_code, start=19900101, end=None):
        """
        获取对应股票历史数据
        :param stock_type: 'sh' or 'sz'
        :param stock_code: 'sh000001' 上证指数
        :param start: 开始时间
        :param end: 结束时间，默认当前日期
        :return: 按照时间由远到近的df
        """
        if stock_type == 'sh':
            stock_code = '0' + stock_code
        if stock_type == "sz":
            stock_code = '1' + stock_code
        url = 'http://quotes.money.163.com/service/chddata.html?code={index_id}&start={start}&end={end}&fields=TCLOSE;HIGH;LOW;TOPEN;LCLOSE;CHG;PCHG;VOTURNOVER;VATURNOVER'.format(
            index_id=stock_code, start=start, end=end or time.strftime("%Y%m%d"))

        page = requests.get(url, headers=self.headers).text  # 该段获取原始数据
        page = page.split('\r\n')
        col_info = page[0].split(',')  # 各列的含义
        index_data = page[1:]  # 真正的数据

        # 修改字段名称
        col_info[col_info.index('日期')] = '交易日期'

        index_data = [x.replace("'", '') for x in index_data]  # 去掉指数编号前的“'”
        index_data = [x.split(',') for x in index_data]

        index_data = index_data[0:index_data.__len__() - 1]  # 最后一行为空，需要去掉
        pos1 = col_info.index('涨跌幅')
        pos2 = col_info.index('涨跌额')
        posclose = col_info.index('收盘价')
        index_data[index_data.__len__() - 1][pos1] = 0  # 最下面行涨跌额和涨跌幅为None改为0
        index_data[index_data.__len__() - 1][pos2] = 0
        for i in range(0, index_data.__len__() - 1):  # 这两列中有些值莫名其妙为None 现在补全
            if index_data[i][pos2] == 'None':
                index_data[i][pos2] = float(index_data[i][posclose]) - float(index_data[i + 1][posclose])
            if index_data[i][pos1] == 'None':
                index_data[i][pos1] = (float(index_data[i][posclose]) - float(index_data[i + 1][posclose])) / float(
                    index_data[i + 1][posclose])

        df = pd.DataFrame(index_data, columns=col_info)
        df.set_index(["交易日期"], inplace=True)
        df.sort_values('交易日期', inplace=True)  # 时间从远到近
        return df

    def calculate_cross_params(self, df):
        """
        计算金叉、死叉
        :param df: 待计算的df
        :return:
        """
        df = df[['开盘价', '收盘价', '最高价', '最低价']]
        df['ma5'] = df['收盘价'].rolling(5).mean()
        df['ma10'] = df['收盘价'].rolling(10).mean()
        df['ma20'] = df['收盘价'].rolling(20).mean()

        # 计算金叉、死叉
        df = df.dropna()
        sr5_20 = df['ma5'] < df['ma20']
        sr20_5 = df['ma5'] >= df['ma20']
        sr20_5_yesterday = sr20_5.shift(1)
        # sr5_10 = df['ma5'] < df['ma10']
        # sr10_5_yesterday = (df['ma5'] >= df['ma10']).shift(1)

        death_cross = df[sr5_20 & sr20_5_yesterday].index  # ma5昨天在上，今天在下
        golden_cross = df[-(sr5_20 | sr20_5_yesterday)].index

        # 金叉日期 DatetimeIndex(['2007-04-12', '2007-06-14', '2007-12-10', '2008-04-23',..., '2020-01-02']
        print('金叉日期', golden_cross)
        # 死叉日期 DatetimeIndex(['2007-06-04', '2007-11-06', '2007-12-13', '2008-05-20',..., '2019-11-12', '2019-12-23']
        print('死叉日期', death_cross)

        return golden_cross, death_cross

    def average_mock_trading(self, df, golden_cross, death_cross, begin_date):
        """
        均线(金叉、死叉)模拟交易
        :param begin_date: 开始模拟的日期 2020-01-01
        :return: 盈亏数据
        """
        # 炒股收益率
        first_money = 100000
        money = first_money  # 持有的资金
        hold = 0  # 持有的股票
        sr1 = pd.Series(1, index=golden_cross)
        sr2 = pd.Series(0, index=death_cross)

        sr = sr1.append(sr2).sort_index()  # 将两个表合并，并按时间排序
        sr = sr[begin_date:]

        for i in range(0, len(sr)):
            bp = float(df['开盘价'][sr.index[i]])  # 当天的开盘价
            lp = float(df['最低价'][sr.index[i]])  # 当天的最低价
            if sr.iloc[i] == 1:
                # 金叉
                buy = money // (100 * bp)  # 买多少手
                hold += buy * 100
                money -= buy * 100 * bp
            else:
                # 死叉，以最低价模拟
                money += hold * lp
                hold = 0  # 持有股票重置为0

        # 计算最后一天股票市值加上持有的资金
        p = float(df['开盘价'][-1])
        now_money = hold * p + money
        print('{}的原始资金为：{}'.format(begin_date, first_money))
        print('模拟交易到今天，持有资产总额:', now_money)
        print('盈亏情况:', now_money - first_money)

        return now_money - first_money


if __name__ == '__main__':
    begin_date = '2020-01-01'  # 开始模拟炒股的时间

    # stocks = {
    #     'sz': [
    #         '300760',
    #         '002340',
    #         '300999',
    #         '300783',
    #         '300773',
    #         '300785',
    #         '002950',
    #         '300750',
    #         '300696',
    #     ],
    #     'sh': []
    # }
    # result = []
    # for k, stock_codes in stocks.items():
    #     for stock_code in stock_codes:
    #         deal = JeremyDeal()
    #         stock_df = deal.get_stock_history_by_code(k, stock_code, start=20190101)
    #         golden_cross, death_cross = deal.calculate_cross_params(stock_df)
    #         income = deal.average_mock_trading(stock_df, golden_cross, death_cross, begin_date)
    #         result.append('{} 从{}开始至{}的收益为：{}'.format(stock_code, begin_date, datetime.date.today(), income))
    # for i in result:
    #     print(i)

    # 单个测试
    deal = JeremyDeal()
    # 获取股票历史信息
    # stock_df = deal.get_stock_history_by_code('sz', '300773')
    # stock_df.to_excel('test.xlsx')
    stock_df = pd.read_excel('test.xlsx')
    stock_df.set_index(["交易日期"], inplace=True)
    # 计算均线
    golden_cross, death_cross = deal.calculate_cross_params(stock_df)
    income = deal.average_mock_trading(stock_df, golden_cross, death_cross, begin_date)
