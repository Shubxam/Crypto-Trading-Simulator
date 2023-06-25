import datetime

import backtrader as bt
import backtrader.analyzers as btanalyzers
import pandas as pd
from backtrader.feeds import GenericCSVData


class EMATrendStrategy(bt.Strategy):

    # tuple to store parameter values. access them using self.p.p-name
    params = (
        ('stopwin', 0.3),
        ('stoploss', 0.05),
        ('fast_ema', 36),
        ('slow_ema', 60),
        ('sizer', 0.2)
    )

    # function which prints any activity to the console.
    def log(self, txt, dt=None):
        # we have referenced above datetime here as datetime
        date_str = self.data.datetime.datetime().isoformat()
        txt = 'Date: {}, {}'.format(date_str, txt)
        print(txt)

    def __init__(self):
        # store the column 'close' to instantly get the closing price by using self.dataclose[0]
        # could either do this or self.data.col-name[0]
        self.dataclose = self.datas[0].close
        # to keep track of any pending orders, last buy-price and commission
        self.order = None
        # Add MovingAverage indicators
        self.ema_fast = bt.indicators.ExponentialMovingAverage(
            self.datas[0], period=self.p.fast_ema
        )
        self.ema_slow = bt.indicators.ExponentialMovingAverage(
            self.datas[0], period=self.p.slow_ema
        )

    def notify_order(self, order):
        '''
        invoked after self.buy() or self.sell()
        To tell user about the order summary and to set stoploss and stopwin for each individual order.
        '''

        if order.status in [order.Submitted, order.Accepted]:
            # If Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # Check if an order has been completed
        # Attention: broker could reject order if not enough cash
        if order.status in [order.Completed]:
            # Check if an order has been completed
            if order.isbuy():
                if self.position.size > 0:  # If we've taken a long position
                    # Take note of buy-price, commission, Max/Min Sell price
                    self.buyprice = order.executed.price
                    self.buycomm = order.executed.comm
                    self.max_sell_price = order.executed.price * \
                        (1+self.params.stopwin)  # 30% stop-profit
                    self.min_sell_price = order.executed.price * \
                        (1-self.params.stoploss)  # 5% stop-loss
                    self.log(
                        'Long Position Taken. Price: {}, Cost: {}, Commission: {}, Max Sell: {}, Min Sell: {}, Position Size: {}, Portfolio Value: {}'.format(
                            order.executed.price,
                            order.executed.value,
                            order.executed.comm,
                            self.max_sell_price,
                            self.min_sell_price,
                            self.position.size,
                            self.broker.get_value())
                    )

                if self.position.size == 0:  # If cleared a short position
                    self.log('Short Position Cleared. Price: {}, Cost: {}, Commission: {}, Portfolio Value: {}'.format(
                        order.executed.price,
                        order.executed.value,
                        order.executed.comm,
                        self.broker.get_value()
                    ))

            elif order.issell():
                if self.position.size < 0:  # If taken a short position
                    self.buyprice = order.executed.price
                    self.min_sell_price = order.executed.price * \
                        (1-self.params.stopwin)  # 30% stop-win
                    self.max_sell_price = order.executed.price * \
                        (1+self.params.stoploss)  # 5% stop-loss
                    self.log('Short Position Taken. Price: {}, Cost: {}, Commission: {}, Max Sell: {}, Min Sell: {}, Position Size: {}'.format(
                        order.executed.price,
                        order.executed.value,
                        order.executed.comm,
                        self.max_sell_price,
                        self.min_sell_price,
                        self.position.size
                    ))
                if self.position.size == 0:  # If cleared a long position
                    self.log('Long Position Cleared. Price: {}, Cost: {}, Commission: {}, Position Size: {}'.format(
                        order.executed.price,
                        order.executed.value,
                        order.executed.comm,
                        self.position.size))

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

        # Write down: no pending order
        '''
        If order is completed or for some reason canceled/rejected you close the order here.
        '''
        self.order = None

    def notify_trade(self, trade):
        '''
        trade refers to a buy/sell pair
        invoked after a buy or sell order is executed i.e. completed.
        '''

        if not trade.isclosed:
            return

        self.log('OPERATION PROFIT, GROSS %.2f, NET %.2f' %
                 (trade.pnl, trade.pnlcomm))

    def next(self):
        '''
        this method is called whenever each new bar (next row in data) is encountered
        '''

        # Check if an order is pending ... if yes, we cannot send a 2nd one
        if self.order:
            return


        if not self.position:

            if self.ema_fast[0] > self.ema_slow[0]:
                self.order = self.buy()
                self.log('Signal: Long Position. Price: {}'.format(
                    self.dataclose[0]))

            if self.ema_fast[0] < self.ema_slow[0]:
                self.log('Signal: Short Position. Price: {}'.format(
                    self.dataclose[0]))
                self.order = self.sell()

        else:
            if self.position.size > 0:
                if self.dataclose[0] <= self.min_sell_price:   # stoploss is reached
                    self.log('Long Position Clear Signal. Stoploss Reached. Price: {} Position Size: {}'.format(
                        self.dataclose[0], self.position.size))

                    self.order = self.close()
                    # self.order = self.sell(self.position.size)

                elif self.ema_fast[0] > self.ema_slow[0]: # buy signal when long
                    if self.dataclose[0] > self.buyprice: # the requirement that last order is long, is satisfied by condition self.position.size > 0
                        self.log('Long Position Increase Signal. Price: {} Position Size: {}'.format(
                            self.dataclose[0], self.position.size))
                        self.order = self.buy(size=self.p.sizer) # buy 0.2 shares

                elif self.ema_fast [0] < self.ema_slow[0]: #TODO maybe also buy a share here
                    self.log('Long Position Clear Signal. Downtrend Detected. Price: {} Position Size: {}'.format(
                        self.dataclose[0], self.position.size))
                    self.order = self.close()
                    # self.order = self.sell(self.position.size)

                elif self.dataclose[0] > self.max_sell_price: #stopwin reached
                    self.log('Short Position Clear Signal. Stopwin Reached. Price: {} Position Size: {}'.format(
                        self.dataclose[0], self.position.size))
                    self.order = self.close()
                    # self.order = self.sell(self.position.size)


            elif self.position.size < 0:
                if self.dataclose[0] > self.max_sell_price:
                    self.log('Short Position Clear Signal. Stoploss Reached. Price: {} Position Size: {}'.format(
                        self.dataclose[0], self.position.size))
                    self.order = self.close()
                    # self.order = self.buy(abs(self.position.size))

                elif self.ema_fast[0] > self.ema_slow[0]: # really make sure that you wanna clear all your short positions.
                    self.log('Short Position Clear Signal. Uptrend Detected. Price: {} Position Size: {}'.format(
                        self.dataclose[0], self.position.size))
                    self.order = self.close()
                    # self.order = self.buy(abs(self.position.size))

                elif self.ema_fast[0] < self.ema_slow[0]: #sell signal when short
                    if self.dataclose[0] < self.buyprice:
                        self.log('Short Position Increase Signal. Price: {} Position Size: {}'.format(
                            self.dataclose[0], self.position.size))
                        self.order = self.sell(size=self.p.sizer) #TODO add quantity and add log message

                elif self.dataclose[0] < self.min_sell_price:  # stopwin reached
                    self.log('Short Position Clear Signal. Stopwin Reached. Price: {} Position Size: {}'.format(
                        self.dataclose[0], self.position.size))
                    self.order = self.close()
                    # self.order = self.buy(abs(self.position.size))


    def stop(self):
        '''
        executes after strategy is done executing i.e. at the very end
        '''
        self.order = self.close()
        self.log('Last Position Close Signal. Price: {} Position Size: {}'.format(
            self.dataclose[0], self.position.size))
        drawdown = self.analyzers.myDrawdown.get_analysis()
        print('max drawdown: {}'.format(drawdown.max.drawdown))


def backtest():
    cerebro = bt.Cerebro(stdstats=False)

    # add default observers
    cerebro.addobserver(bt.observers.Broker, plot=False)
    cerebro.addobserver(bt.observers.Trades)
    cerebro.addobserver(bt.observers.BuySell)

    df_tm = pd.read_csv('data/BTC-USD_tm.csv', parse_dates=True, index_col=0)

    df_custom = pd.read_csv('data/BTC-USD_1hr.csv',
                            parse_dates=True, index_col=0)

    # change df here
    df = df_tm

    data = bt.feeds.PandasData(
        dataname=df,
        datetime=None,
        open=0,
        high=1,
        low=2,
        close=3,
        volume=4,
        openinterest=None
    )


    cerebro.adddata(data)

    cerebro.addstrategy(EMATrendStrategy)

    cerebro.broker.setcash(100000)

    cerebro.broker.setcommission(commission=0.001)

    # annaul Sharpe Ratio
    cerebro.addanalyzer(btanalyzers.SharpeRatio_A,
                        _name='mySharpe', riskfreerate=0.07)

    # Drawdown
    cerebro.addanalyzer(btanalyzers.DrawDown, _name='myDrawdown')

    cerebro.addanalyzer(btanalyzers.TradeAnalyzer, _name='myTradeAnalyzer')

    start_value = cerebro.broker.getvalue()
    print('Starting Portfolio Value: {}'.format(start_value))


    backtest_result = cerebro.run()

    sr = backtest_result[0].analyzers.mySharpe.get_analysis()['sharperatio']
    print('Sharpe Ratio: {}'.format(sr))
    tt = backtest_result[0].analyzers.getbyname(
        'myTradeAnalyzer').get_analysis()['total']['total']
    print('total trades:', tt)
    profit_win = backtest_result[0].analyzers.getbyname(
        'myTradeAnalyzer').get_analysis()['won']['pnl']['average']
    print('profit/winning trade:', profit_win)
    loss_lose = backtest_result[0].analyzers.getbyname(
        'myTradeAnalyzer').get_analysis()['lost']['pnl']['average']
    print('loss/losing trade:', loss_lose)
    pnl = backtest_result[0].analyzers.getbyname(
        'myTradeAnalyzer').get_analysis()['pnl']['net']['total']
    print('PnL:', pnl)
    avg_pnl = backtest_result[0].analyzers.getbyname(
        'myTradeAnalyzer').get_analysis()['pnl']['net']['average']
    print('Avg PnL/Trade:', avg_pnl)

    end_value = cerebro.broker.getvalue()

    abs_rtn = (end_value - start_value)/start_value
    print('Absolute Returns: {}%'.format(abs_rtn*100))

    no_days = len(df.asfreq(freq='D').dropna())
    cagr = (end_value/start_value)**(365/no_days) - 1
    print('CAGR: {}%'.format(cagr*100))

    print('Ending Portfolio Value: {}'.format(end_value))



if __name__ == '__main__':
    backtest()
