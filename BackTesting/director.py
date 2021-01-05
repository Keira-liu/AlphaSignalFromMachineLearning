# -*- coding: utf-8 -*-
"""
Created on Sat Jan 2 13:30:30 2021

@author: Ye Donggua

"""
import pandas as pd
from sklearn.metrics import mean_squared_error

from Tool import globalVars
from Tool.Factor import Factor
from Tool.DataPreProcessing import DeExtremeMethod, ImputeMethod, StandardizeMethod
from GetData.loadData import load_material_data
from BackTesting.Signal.CrossSectionalModels.CrossSectionalModel import CrossSectionalModelXGBoost


class SignalDirector:
    def __init__(self, signalGeneratorClass, logger=None):
        self.signalGeneratorClass = signalGeneratorClass
        self.logger = logger
        # 回测的时候关心的factors
        self.factorNameList = []
        # run的时候会有实例
        self.signalGenerator = None

    def run(self):
        # initialize the globalVars
        globalVars.initialize()
        self.logger.info('globalVars is initialized')

        # load material data
        loadedDataList = load_material_data()
        self.logger.info('material data {0} is loaded'.format(loadedDataList))

        # load factors
        # TODO: should load from some factor.json file latter rather than simply load from material data
        # self.factorNameList
        toLoadFactors = ['close',
                         'high',
                         'low',
                         'open',
                         'volume'
                         ]
        # 给globalVars注册factors（dict）
        # key：factor的名字，value：generalData
        if 'factors' not in globalVars.varList:
            globalVars.register('factors', {})
        # TODO: factorManager
        for factorName in toLoadFactors:

            globalVars.factors[factorName] = Factor(factorName, globalVars.materialData[factorName])
            print(factorName, 'is now in globalVars.factors')
            self.factorNameList.append(factorName)
            self.logger.info("factor {0} is loaded".format(factorName))
        self.logger.info("all factors are loaded")

        # calculate the signal
        # 设置计算factors的参数
        # 可直接传pipeline
        # maskList：mask的nameList
        params = {
            "startDate": pd.to_datetime('2020-01-01'),
            "endDate": pd.to_datetime('2020-10-31'),
            "panelSize": 3,
            "trainTestGap": 1,
            "maskList": None,
            "deExtremeMethod": DeExtremeMethod.MeanStd(),
            "imputeMethod": ImputeMethod.JustMask(),
            "standardizeMethod": StandardizeMethod.StandardScaler(),
            "pipeline": None,
            "factorNameList": toLoadFactors,
            # params for XGBoost
            "modelParams": {
                "jsonPath": None,
                "paraDict": {
                    "n_estimators": 50,
                    "random_state": 42,
                    "max_depth": 2}
            },
            # metric function for machine learning models
            "metric_func": mean_squared_error,
            # smoothing params
            "periods": 10,
            # smoothing的时候用的方式
            "method": "linear"
        }
        self.logger.info("start to generate signalGenerator")
        self.signalGenerator = self.signalGeneratorClass(model=CrossSectionalModelXGBoost, logger=self.logger)
        signals = self.signalGenerator.generate_signals(**params)

        return signals


if __name__ == '__main__':
    import logging
    import numpy as np
    from Tool.logger import Logger
    from BackTesting.Signal.SignalSynthesis import SignalSynthesis

    np.warnings.filterwarnings('ignore')

    logger = Logger("SignalDirector")
    logger.setLevel(logging.INFO)

    director = SignalDirector(SignalSynthesis, logger=logger)
    director.run()