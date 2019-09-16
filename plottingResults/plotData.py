#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 11 16:05:11 2019

@author: mellis
"""
import getData

import matplotlib.pyplot as plt
import numpy as np

def plotNormVsElecDt(allNestedData, model, fig=False, axis=False):
    """
    Will plot the electronic timestep vs the norm for all the data in the
    nested data input for a certain model. BOB
    """
    allData = allNestedData.query_data({'tullyModel': model})
    dt = allData[0].dt * 24.188843265857  # in as
    elec_dts = [dt / data.elec_steps for data in allData]
    norms = [abs(data.get_norm_drift()) for data in allData]

    repeats = False
    if any([j == 0 for j in np.diff(elec_dts)]):
        repeats = True

    if axis is False or fig is False:
        f, axis = plt.subplots()

    if repeats is False:
        axis.plot(elec_dts, norms, 'ko', ls='--')
    else:
        data = {}
        for elec_dt, norm in zip(elec_dts, norms):
            getData.add_to_list_in_dict(data, elec_dt, norm)
    
        x = [i for i in data]
        y = [np.mean(data[i]) for i in data]
        axis.plot(sorted(x), [i[1] for i in sorted(zip(x,y))],
                  'ko', ls='--')
        for i in data:
            axis.plot([i] * len(data[i]), data[i], 'k-', lw=0.5)
    axis.set_yscale("log")
    axis.grid(color="#dddddd")
    axis.set_ylabel("Norm Drift [$ps^{-1}$]")
    axis.set_xlabel("Electronic Timestep [as]")
    fig.suptitle("Nuclear dt = %.2g [as]" % (dt), fontsize=30)


def plotEnerVsNuclDt(allNestedData, model, fig=False, axis=False):
    """
    Will plot the electronic timestep vs the norm for all the data in the
    nested data input for a certain model. BOB
    """
    allData = allNestedData.query_data({'tullyModel': model})

    elec_dt = [float(data.dt) / data.elec_steps for data in allData]
    # All elec dt should be the same!
    if any([j > 1e-5 for j in np.diff(elec_dt)]):
        raise SystemExit("The electronic timesteps are different!")

    nucl_dt = [data.dt * 24.188843265857 for data in allData]  # in as
    ener_drifts = [abs(data.get_ener_drift()) for data in allData]

    allD = sorted(zip(nucl_dt, ener_drifts))
    nucl_dt = [i[0] for i in allD]
    ener_drifts = [i[1] for i in allD]

    if axis is False or fig is False:
        f, axis = plt.subplots()

    axis.plot(nucl_dt, ener_drifts, 'ko', ls='--')
    axis.set_yscale("log")
    axis.grid(color="#dddddd")
    axis.set_ylabel(r"Ener Drift [$\frac{Ha}{ps \ atom}$]")
    axis.set_xlabel("Nuclear Timestep [as]")
    fig.suptitle("Elec dt = %.2g [as]" % (elec_dt[0]), fontsize=30)