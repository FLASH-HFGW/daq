import FitFunctions as ff
import numpy as np
from iminuit import Minuit, cost



def fitCall(file1,file2,file3,fitmin,fitmax,parini,parname,parmin,parmax):

    x12,Re12,Im12 = np.genfromtxt(file1,unpack=True,delimiter=' ',usecols=(0,1,2))
    S12 = np.sqrt(Re12*Re12+Im12*Im12)
    fMin = float(fitmin)
    fMax = float(fitmax)

    x22,Re22,Im22 = np.genfromtxt(file2,unpack=True,delimiter=' ',usecols=(0,1,2))
    S22 = np.sqrt(Re22*Re22+Im22*Im22)

    x21,Re21,Im21 = np.genfromtxt(file3,unpack=True,delimiter=' ',usecols=(0,1,2))
    S21 = np.sqrt(Re21*Re21+Im21*Im21)

    S21e = 0.02*S21
    c21 = cost.LeastSquares(x21,S21,S21e,ff.modS21)

    S12e = 0.05*S12
    c12 = cost.LeastSquares(x12,S12,S12e,ff.modS12)

    S22e = 0.02*S22
    c22 = cost.LeastSquares(x22,S22,S22e,ff.modS22)

    maskIn = (np.abs(x22 - fMin)).argmin()
    maskEnd = (np.abs(x22 - fMax)).argmin()

    c22.mask = np.arange(min(maskIn, maskEnd), max(maskIn, maskEnd) + 1)
    #c22.mask = None
    c21.mask = None
    c12.mask = None
    cc = c12 + c22 + c21

    #m1 = Minuit(c11,parini,name=(parname[0],parname[1],parname[2],parname[3],parname[4],parname[5],parname[6],parname[7],parname[8],parname[9],parname[10],parname[11],parname[12]))
    m1 = Minuit(cc,parini,name=parname)

    for l in np.arange(len(parmin)):
        m1.limits[l] = (parmin[l],parmax[l])


    # m1.fixed['x1'] = True
    # m1.fixed['x3'] = True
    # m1.fixed['x4'] = True
    # m1.fixed['x6'] = True
    # m1.fixed['x7'] = True

    m1.migrad()
    m1.hesse()

    datasets = {
        "S12": (x12, S12, ff.modS12(x12, m1.values)),
        "S22": (x22, S22, ff.modS22(x22, m1.values)),
        "S21": (x21, S21, ff.modS21(x21, m1.values)),
    }

    return m1, datasets
