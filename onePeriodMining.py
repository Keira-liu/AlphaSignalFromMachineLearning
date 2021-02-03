# -*- coding: utf-8 -*-
"""
Created on Tue Jan 26 14:06:31 2021

@author: eiahb
"""

#%% import
import sys
import os
import ray
import json
import numpy as np
import numpy.random as random

from datetime import datetime
from deap import base, creator, gp, tools
from functools import partial
try:
    from GeneticPogramming.psetCreator import pset_creator
    from GeneticPogramming.rayMapper import ray_deap_map
    from GeneticPogramming.evalAlgorithm import preprocess_eval_single_period
    from GeneticPogramming.evolutionAlgorithm import easimple
    from GeneticPogramming.factorEvaluator import ic_evaluator, icir_evaluator
    from GeneticPogramming.utils import save_factor, compileFactor
    from Tool import Logger, GeneralData, Factor
    from GetData import load_data, align_all_to
except :
    PROJECT_ROOT = 'C:\\Users\\eiahb\\Documents\\MyFiles\\WorkThing\\tf\\01task\\GeneticProgrammingProject\\AlphaSignalFromMachineLearning\\'
    os.chdir(PROJECT_ROOT)
    from GeneticPogramming.psetCreator import pset_creator
    from GeneticPogramming.rayMapper import ray_deap_map
    from GeneticPogramming.evalAlgorithm import preprocess_eval_single_period
    from GeneticPogramming.evolutionAlgorithm import easimple
    from GeneticPogramming.factorEvaluator import ic_evaluator, icir_evaluator
    from GeneticPogramming.utils import save_factor, compileFactor
    from Tool import Logger, GeneralData, Factor
    from GetData import load_data, align_all_to

os.environ['NUMEXPR_MAX_THREADS'] = '16'
#%% set parameters 挖因子過程參數
PROJECT_ROOT = 'C:\\Users\\eiahb\\Documents\\MyFiles\\WorkThing\\tf\\01task\\GeneticProgrammingProject\\AlphaSignalFromMachineLearning\\'
FACTOR_PATH = os.path.join(PROJECT_ROOT,"data\\factors")


PERIOD_START = "2017-01-01"
PERIOD_END = "2019-01-01"
ITERTIMES = 30
POOL_SIZE = 4

EVALUATE_FUNC = ic_evaluator
#%% hyperparameters 魔仙超參數

N_POP = 100
N_GEN = 7
CXPB = 0.6
MUTPB = 0.2
# the tournsize of tourn selecetion
TOURNSIZE = 3
# The parameter *termpb* sets the probability to choose between 
# a terminal or non-terminal crossover point.
TERMPB = 0.1

# the height min max of a initial generate 
initGenHeightMin, initGenHeightMax = 2, 4

# the height min max of a mutate sub tree
mutGenHeightMin, mutGenHeightMax = 1, 2

materialDataNames = [
    'close',
    'high',
    'low',
    'open',
    # 'preclose',
    'amount',
    'volume',
    'pctChange'
]

barraNames = [
    'beta',
    'bp',
    'mom',
    'size',
    'stoa',
    'stom',
    'stoq'
]
config = {}
config.update({
    "PERIOD_START":PERIOD_START,
    "PERIOD_END":PERIOD_END,
    "ITERTIMES":ITERTIMES,
    "POOL_SIZE":POOL_SIZE,
    "EVALUATE_FUNC":EVALUATE_FUNC.__name__,
    "N_POP":N_POP,
    "N_GEN":N_GEN,
    "CXPB":CXPB,
    "MUTPB":MUTPB,
    "TOURNSIZE":TOURNSIZE,
    "TERMPB":TERMPB,
    "initGenHeightMin":initGenHeightMin,
    "initGenHeightMax":initGenHeightMax,
    "mutGenHeightMin":mutGenHeightMin,
    "mutGenHeightMax":mutGenHeightMax,
    "materialDataNames":materialDataNames,
    "barraNames":barraNames
})
# TODO
# import configparser
# config = configparser.ConfigParser()
# config['DEFAULT'] = {'ServerAliveInterval': '45',
#                       'Compression': 'yes',                  
#                       'CompressionLevel': '9'}

#%% pset & creator
def creator_setup():
    creator.create('FitnessMax', base.Fitness, weights=(1.0,))
    creator.create('Individual', gp.PrimitiveTree, fitness = creator.FitnessMax) 
    

pset = pset_creator(materialDataNames)
creator_setup()
#%% toolbox
# toolbox setup
toolbox = base.Toolbox()
toolbox.register("expr", gp.genHalfAndHalf, pset=pset, min_= initGenHeightMin, max_ = initGenHeightMax)
toolbox.register("individual", tools.initIterate, creator.Individual, toolbox.expr)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)

# register for tools to evolution 注册进化过程需要的工具：配种选择、交叉、突变
toolbox.register('select', tools.selTournament, tournsize = TOURNSIZE) 
toolbox.register('crossover', gp.cxOnePointLeafBiased, termpb = TERMPB)
toolbox.register("expr_mut", gp.genHalfAndHalf, min_ = mutGenHeightMin, max_ = mutGenHeightMax)

def multi_mutate(individual, expr, pset):
    '''
    apply multiple kinds of mutation in a funciton
    '''
    rand = random.uniform(0)
    if rand <= 0.4:
        return gp.mutUniform(individual, expr, pset)
    elif rand <= 0.75:
        return gp.mutShrink(individual)
    else:
        return gp.mutNodeReplacement(individual, pset)
    
toolbox.register("mutate", multi_mutate, expr=toolbox.expr_mut, pset=pset)

# use ray to implement multiprocess
toolbox.register("map", ray_deap_map, creator_setup=creator_setup,
                 pset_creator=partial(pset_creator,materialDataNames = materialDataNames))

#%% define stat and logbook
stats_fit = tools.Statistics(lambda ind: ind.fitness.values)
stats_size = tools.Statistics(len)
mstats = tools.MultiStatistics(fitness=stats_fit, size=stats_size)
mstats.register("avg", np.mean)
mstats.register("std", np.std)
mstats.register("min", np.min)
mstats.register("max", np.max)

#%% define main 
def main():
    random.seed(318)
    ray.init(num_cpus=POOL_SIZE, ignore_reinit_error=True)
    logbook = tools.Logbook()
    # make a new folder

    test_number = datetime.now().strftime("%Y%m%d_%H_%M_%S")
    this_test_path = os.path.join(FACTOR_PATH,test_number)
    os.makedirs(this_test_path, exist_ok=True)
    os.makedirs(os.path.join(this_test_path, "best_factors"), exist_ok=True)
    os.makedirs(os.path.join(this_test_path, "found_factors"), exist_ok=True)

    with open(os.path.join(this_test_path,'config.json'), 'w') as outfile:
        json.dump(config, outfile)

    # set up logger
    loggerFolder = os.path.join(this_test_path, 'log')
    os.makedirs(loggerFolder, exist_ok=True)
    logger = Logger(loggerFolder=loggerFolder, exeFileName='log')
    globalVars.initialize(logger)
    
    # load data to globalVars
    load_data("barra",
        os.path.join(os.path.join(PROJECT_ROOT,"data"), "h5")
    )
    load_data("materialData",
        os.path.join(os.path.join(PROJECT_ROOT,"data"), "h5")
    )
    globalVars.logger.info('load all......done')
    
    # prepare data
    materialDataDict = {k:globalVars.materialData[k] for k in materialDataNames} # only take the data specified in materialDataNames
    barraDict = {k:globalVars.barra[k] for k in barraNames} # only take the data specified in barraNames
    toRegFactorDict = {}
    
    # get the return to compare 
    open_ = globalVars.materialData['open']
    shiftedPctChange_df = open_.to_DataFrame().pct_change().shift(-2)
    
    # align data within 2Y
    periodShiftedPctChange_df = shiftedPctChange_df.loc[PERIOD_START:PERIOD_END]
    periodShiftedPctChange = GeneralData('periodShiftedPctChange_df', periodShiftedPctChange_df)
    periodMaterialDataDict = align_all_to(materialDataDict, periodShiftedPctChange)
    periodBarraDict = align_all_to(barraDict, periodShiftedPctChange)
    
    del shiftedPctChange_df, periodShiftedPctChange_df
    
    # stack barra data
    barraStack = None
    toRegFactorStack =  None
    if len(barraDict)>0:
        barraStack = np.stack([aB.generalData for aB in periodBarraDict.values()],axis = 2)
        
    if len(toRegFactorDict)>0:
        toRegFactorStack = np.stack([aB.generalData for aB in toRegFactorDict.values()],axis = 2)
        
        
    materialDataDictID = ray.put(periodMaterialDataDict)
    barraStackID = ray.put(barraStack)
    toRegFactorStackID = ray.put(toRegFactorStack)
    
    evaluate = partial(
        preprocess_eval_single_period,
        materialDataDictID = materialDataDictID,
        barraStackID = barraStackID,
        toRegFactorStackID = toRegFactorStackID,
        factorEvalFunc = partial(EVALUATE_FUNC, shiftedPctChange = periodShiftedPctChange),
        pset = pset
    )
    
    for i in range(ITERTIMES):
        logger.info("start easimple algorithm from iteration {}th time".format(i+1))

        findFactor, returnIndividual, logbook = easimple(toolbox = toolbox,
                                                         stats = mstats,
                                                         logbook = logbook,
                                                         evaluate = evaluate,
                                                         logger = globalVars.logger,
                                                         N_POP = N_POP,
                                                         N_GEN = N_GEN,
                                                         CXPB = CXPB,
                                                         MUTPB = MUTPB
                                                        )
        if findFactor:
            func, factor_data = compileFactor(individual = returnIndividual, materialDataDict = periodMaterialDataDict, pset = pset)
            factor = Factor(name=str(returnIndividual),
                            generalData=factor_data,
                            functionName=str(returnIndividual),
                            reliedDatasetNames={"materialData":list(materialDataDict.keys())},
                            parameters_dict={},
                            **config
                        )
            factor.save(os.path.join(this_test_path,"found_factors\\{}.pickle".format(factor.name)))



            # save_factor(factor, USEFUL_FACTOR_RECORD_PATH)
            toRegFactorDict.update({str(returnIndividual):factor})
            if len(toRegFactorDict)>0:
                toRegFactorStack = np.stack([aB.generalData for aB in toRegFactorDict.values()],axis = 2)
                toRegFactorStackID = ray.put(toRegFactorStack)
        
            evaluate = partial(
                preprocess_eval_single_period,
                materialDataDictID = materialDataDictID,
                barraStackID = barraStackID,
                toRegFactorStackID = toRegFactorStackID,
                factorEvalFunc = partial(EVALUATE_FUNC, shiftedPctChange = periodShiftedPctChange),
                pset = pset
            )
            
            continue;
                
        else:
            func, factor_data = compileFactor(individual = returnIndividual, materialDataDict = periodMaterialDataDict, pset = pset)
            factor = Factor(name=str(returnIndividual),
                generalData=factor_data,
                functionName=str(returnIndividual),
                reliedDatasetNames={"materialData":list(materialDataDict.keys())},
                parameters_dict={},
                **config
            )
            factor.save(os.path.join(this_test_path,"best_factors\\{}.pickle".format(factor.name)))
            logger.info("end easimple algorithm from iteration {}th time".format(i+1))


#%% main
if __name__ == '__main__':
    from Tool import globalVars
    main()
    




# %%