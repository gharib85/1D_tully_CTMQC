#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May 13 12:25:43 2019

@author: oem
"""
import numpy as np
import scipy.integrate as integrate
import random as rd


def calc_ad_frc(pos, ctmqc_env):
    """
    Will calculate the forces from each adiabatic state (the grad E term)
    """
    dx = ctmqc_env['dx']
    H_xm = ctmqc_env['Hfunc'](pos - dx)
    H_x = ctmqc_env['Hfunc'](pos)
    H_xp = ctmqc_env['Hfunc'](pos + dx)
    allH = [H_xm, H_x, H_xp]
    allE = [np.linalg.eigh(H)[0] for H in allH]
    gradE = np.array(np.gradient(allE, dx, axis=0))[1]
    return -gradE


def calc_ad_mom(ctmqc_env, irep, ad_frc=False):
    """
    Will calculate the adiabatic momenta (time-integrated adiab force)
    """
    if ad_frc is False:
        pos = ctmqc_env['pos'][irep]
        ad_frc = calc_ad_frc(pos, ctmqc_env)

    ad_mom = ctmqc_env['adMom'][irep]
    dt = ctmqc_env['dt']

    ad_mom += dt * ad_frc
#    print(ad_mom)
    return ad_mom


def gaussian(RIv, RJv, sigma):
    """
    Will calculate the gaussian on the traj

    This has been tested and is definitely normalised
    """
    sig2 = sigma**2

    prefact = (sig2 * 2 * np.pi)**(-0.5)
    exponent = -((RIv - RJv)**2 / (2 * sig2))

    return prefact * np.exp(exponent)


def test_norm_gauss():
    """
    Will test whether the gaussian is normalised by checking 50 different
    random gaussians.
    """
    x = np.arange(-13, 13, 0.001)
    y = [gaussian(x, -1, abs(rd.gauss(0.5, 0.3))+0.05) for i in range(50)]
    norms = [integrate.simps(i, x) for i in y]
    if any(abs(norm - 1) > 1e-9 for norm in norms):
        print(norms)
        raise SystemExit("Gaussian not normalised!")


def calc_nucl_dens_PP(R, sigma):
    """
    Will calculate the nuclear density post-production

    Inputs:
        * R => the positions for 1 step <np.array (nrep)>
        * sigma => the nuclear widths for 1 step <np.array (nrep)>
    """
    nRep = np.shape(R)
    nuclDens = np.zeros(nRep)

    for I in range(nRep):
        RIv = R[I]
        allGauss = [gaussian(RIv, RJv, sigma[I])
                    for RJv in R]
        nuclDens[I] = np.mean(allGauss)

    return nuclDens, R


def calc_nucl_dens(RIv, ctmqc_env):
    """
    Will calculate the nuclear density on replica I (for 1 atom)

    Inputs:
        * I => <int> Replica Index I
        * v => <int> Atom index v
        * sigma => the width of the gaussian on replica J atom v
        * ctmqc_env => the ctmqc environment
    """
    RJv = ctmqc_env['pos']
    sigma = ctmqc_env['sigma']
    allGauss = [gaussian(RIv, RJ, sig) for sig, RJ in zip(sigma, RJv)]
    return np.mean(allGauss)


def calc_sigma(ctmqc_env):
    """
    Will calculate the value of sigma used in constructing the nuclear density.

    This algorithm doesn't seem to work -it gives discontinuous sigma and sigma
    seems to blow up. To fix discontinuities a weighted stddev might work.
    """
    for I in range(ctmqc_env['nrep']):
        cnst = ctmqc_env['const']
        sigma_tm = ctmqc_env['sigma_tm'][I]
        cutoff_rad = cnst * sigma_tm
        sig_thresh = cnst/ctmqc_env['nrep'] * np.min(ctmqc_env['sigma_tm'])

        distances = ctmqc_env['pos'] - ctmqc_env['pos'][I]
        distMask = distances < cutoff_rad
        if any(distMask):
            new_var = np.std(distances[distances < cutoff_rad])
        else:
            print(cutoff_rad)
            new_var = sig_thresh
        ctmqc_env['sigma'][I] = new_var


def calc_QM_FD(ctmqc_env):
    """
    Will calculate the quantum momentum (only for 1 atom currently)
    """
    nRep = ctmqc_env['nrep']
    QM = np.zeros(nRep)
    for I in range(nRep):
        RIv = ctmqc_env['pos'][I]
        dx = ctmqc_env['dx']
    
        nuclDens_xm = calc_nucl_dens(RIv - dx, ctmqc_env)
        nuclDens = calc_nucl_dens(RIv, ctmqc_env)
        nuclDens_xp = calc_nucl_dens(RIv + dx, ctmqc_env)
    
        gradNuclDens = np.gradient([nuclDens_xm, nuclDens, nuclDens_xp],
                                   dx)[2]
        if nuclDens < 1e-12:
            return 0
    
        QM[I] = -gradNuclDens/(2*nuclDens)
        
    return QM / ctmqc_env['mass'][0]


def calc_QM_analytic(ctmqc_env):
    """
    Will use the analytic formula provided in SI to calculate the QM.
    """
    nRep = ctmqc_env['nrep']
    QM = np.zeros(nRep)
    for I in range(nRep):
        RIv = ctmqc_env['pos'][I]
        WIJ = np.zeros(ctmqc_env['nrep'])  # Only calc WIJ for rep I
        allGauss = [gaussian(RIv, RJv, sig)
                    for (RJv, sig) in zip(ctmqc_env['pos'],
                                          ctmqc_env['sigma'])]
        # Calc WIJ
        sigma2 = ctmqc_env['sigma']**2
        WIJ = allGauss / (2. * sigma2 * np.sum(allGauss))
    
        # Calc QM
        QM[I] = np.sum(WIJ * (RIv - ctmqc_env['pos']))
        
    return QM / ctmqc_env['mass'][0]


def calc_all_prod_gauss(ctmqc_env):
    """
    Will calculate the product of the gaussians in a more efficient way than
    simply brute forcing it.
    """
    nRep = ctmqc_env['nrep']
    
    # We don't need the prefactor of (1/(2 pi))^{3/2} as it always cancels out
    prefact = ctmqc_env['sigma']**(-1)
    # Calculate the exponent
    exponent = np.zeros((nRep, nRep))
    for I in range(nRep):
        RIv = ctmqc_env['pos'][I]
        for J in range(nRep):
            RJv = ctmqc_env['pos'][J]
            sJv = ctmqc_env['sigma'][J]
            
            exponent[I, J] -= ( (RIv - RJv)**2 / (sJv**2))
    return np.exp(exponent * 0.5) * prefact


def calc_WIJ(ctmqc_env, reps_to_complete=False):
    """
    Will calculate alpha for all replicas and atoms
    """
    nRep = ctmqc_env['nrep']
    WIJ = np.zeros((nRep, nRep))
    allProdGauss_IJ = calc_all_prod_gauss(ctmqc_env)

    if reps_to_complete is not False:
        for I in reps_to_complete:
            # Calc WIJ and alpha
            sigma2 = ctmqc_env['sigma']**2
            WIJ[I, :] = allProdGauss_IJ[I, :] \
                            / (sigma2 * np.sum(allProdGauss_IJ[I, :]))
        WIJ /= 2.
    else:
         for I in range(nRep):
            # Calc WIJ and alpha
            sigma2 = ctmqc_env['sigma']**2
            WIJ[I, :] = allProdGauss_IJ[I, :] \
                            / (2. * sigma2 * np.sum(allProdGauss_IJ[I, :]))
    return WIJ


def calc_Qlk(ctmqc_env):
    """
    Will calculate the (effective) intercept for the Quantum Momentum based on
    the values in the ctmqc_env dict. If this spikes then the R0 will be used,
    if the Rlk isn't spiking then the Rlk will be used.
    """
    # Calculate Rlk -compare it to previous timestep Rlk
    nRep = ctmqc_env['nrep']
    nState = ctmqc_env['nstate']

    pops = ctmqc_env['adPops']
    reps_to_complete = np.arange(nRep)
    #reps_to_complete = [irep for irep, rep_pops in enumerate(pops[:, 0, :])
    #                    if all(state_pop < 0.995 for state_pop in rep_pops)]

    # Calculate WIJ and alpha
    WIJ = calc_WIJ(ctmqc_env, reps_to_complete)
    alpha = np.sum(WIJ, axis=1)
    ctmqc_env['alpha'] = alpha
    Ralpha = ctmqc_env['pos'] * alpha

    # Calculate all the Ylk
    f = ctmqc_env['adMom']
    Ylk = np.zeros((nRep, nState, nState))
    for J in reps_to_complete:
        for l in range(nState):
            Cl = pops[J, l]
            fl = f[J, l]
            for k in range(l):
                Ck = pops[J, k]
                fk = f[J, k]
                Ylk[J, l, k] = Ck * Cl * (fk - fl)
                Ylk[J, k, l] = -Ylk[J, l, k]
    sum_Ylk = np.sum(Ylk, axis=0)  # sum over replicas
    # Calculate Qlk
    Qlk = np.zeros((nRep, nState, nState))
    if abs(sum_Ylk[0, 1]) > 1e-12:
        # Calculate the R0 (used if the Rlk spikes)
        RI0 = np.zeros((nRep))
        for I in reps_to_complete:
            RI0[I] = np.dot(WIJ[I, :], ctmqc_env['pos'][:])

        # Calculate the Rlk
        Rlk = np.zeros((nState, nState))
        for I in reps_to_complete:
            Rav = Ralpha[I]
            for l in range(nState):
                for k in range(l):
                    Rlk[l, k] += Rav * (
                                 Ylk[I, l, k] / sum_Ylk[l, k])
                    Rlk[k, l] = Rlk[l, k]
            
        # Save the data
        ctmqc_env['Rlk'] = Rlk
        ctmqc_env['RI0'] = RI0

        # Calculate the Quantum Momentum
        maxRI0 = np.max(RI0[np.abs(RI0) > 0], axis=0)
        minRI0 = np.min(RI0[np.abs(RI0) > 0], axis=0)
        for I in reps_to_complete:
            R = np.zeros((nState, nState))
            for l in range(nState):
                for k in range(l):
                    if Rlk[l, k] > maxRI0 or Rlk[l, k] < minRI0:
                        R[l, k] = RI0[I]
                        R[k, l] = RI0[I]
                    else:
                        R[l, k] = Rlk[l, k]
                        R[k, l] = Rlk[k, l]

            Qlk[I, :, :] = Ralpha[I] - R
            Qlk[I, :, :] = Ralpha[I] - R

        # Divide by mass2
        Qlk[:, :, :] /= ctmqc_env['mass'][0]

    return Qlk


def calc_sigmal(ctmqc_env):
    """
    Will calculate the sigmal term.
    """


def test_QM_calc(ctmqc_env):
    """
    Will compare the output of the analytic QM calculation and the finite
    difference one.
    """
    allDiffs = calc_QM_analytic(ctmqc_env) - calc_QM_FD(ctmqc_env)
    allPos = ctmqc_env['pos']

    print("Avg Abs Diff = %.2g +/- %.2g" % (np.mean(allDiffs),
                                              np.std(allDiffs)))
    print("Max Abs Diff = %.2g" % np.max(np.abs(allDiffs)))
    print("Min Abs Diff = %.2g" % np.min(np.abs(allDiffs)))
    if np.max(np.abs(allDiffs)) > 1e-5:
        raise SystemExit("Analytic Quantum Momentum != Finite Difference")

    return allDiffs, allPos


#test_norm_gauss()
