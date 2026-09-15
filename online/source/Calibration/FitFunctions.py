import numpy as np

##S21 fit function
def modS21(x,par):
	ReSM=0.
	ImSM=0.
	delta = x/(par[1]) - (par[1])/x

	Q_L = par[2]/(1+par[3]+par[4])
	A = 2.*np.sqrt(par[3]*par[4])/(1+par[3]+par[4])
	ReSM = ReSM+A/(1+np.power(Q_L*delta,2))
	ImSM = ImSM-A*Q_L*delta/(1+np.power(Q_L*delta,2))

	mod = par[5]*np.sqrt(ReSM*ReSM+ImSM*ImSM)
	return mod


##S12 fit function
def modS12(x,par):
	ReSM=0.
	ImSM=0.
	delta = x/(par[1]) - (par[1])/x

	Q_L = par[2]/(1+par[4]+par[3])
	A = 2.*np.sqrt(par[4]*par[3])/(1+par[4]+par[3])
	ReSM = ReSM+A/(1+np.power(Q_L*delta,2))
	ImSM = ImSM-A*Q_L*delta/(1+np.power(Q_L*delta,2))

	mod = par[0]*np.sqrt(ReSM*ReSM+ImSM*ImSM)
	return mod


##S22 fit function
def modS22(x,par):
	ReSM=0.
	ImSM=0.
	delta=(x/par[1]-par[1]/x)
	numeratorRE=np.power(par[4],2)-np.power(1+par[3],2)-np.power(par[2]*delta + par[7],2)
	numeratorIM=-2.*par[4]*par[2]*delta
	denomin=np.power(1+par[3]+par[4],2)+np.power(par[2]*delta,2)

	ReSM=ReSM+numeratorRE/denomin
	ImSM=ImSM+numeratorIM/denomin

	mod = par[6]*np.sqrt(ReSM*ReSM+ImSM*ImSM)
	return mod
