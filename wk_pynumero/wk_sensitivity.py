#
# Work through
# https://github.com/Pyomo/pyomo/blob/master/pyomo/contrib/pynumero/examples/sensitivity.py
#

import pyomo.environ as pyo
from pyomo.contrib.pynumero.interfaces.pyomo_nlp import PyomoNLP
from pyomo.contrib.pynumero.sparse import BlockSymMatrix, BlockMatrix, BlockVector
from scipy.sparse import identity
from scipy.sparse.linalg import spsolve
import numpy as np

def create_model(eta1, eta2):
    model = pyo.ConcreteModel()
    # variables
    model.x1 = pyo.Var(initialize=0.15)
    model.x2 = pyo.Var(initialize=0.15)
    model.x3 = pyo.Var(initialize=0.0)
    # parameters
    model.eta1 = pyo.Var()
    model.eta2 = pyo.Var()

    model.nominal_eta1 = pyo.Param(initialize=eta1, mutable=True)
    model.nominal_eta2 = pyo.Param(initialize=eta2, mutable=True)

    # constraints + objective
    model.const1 = pyo.Constraint(expr=6*model.x1+3*model.x2+2*model.x3 - model.eta1 == 0)
    model.const2 = pyo.Constraint(expr=model.eta2*model.x1+model.x2-model.x3-1 == 0)
    model.cost = pyo.Objective(expr=model.x1**2 + model.x2**2 + model.x3**2)
    model.consteta1 = pyo.Constraint(expr=model.eta1 == model.nominal_eta1)
    model.consteta2 = pyo.Constraint(expr=model.eta2 == model.nominal_eta2)

    return model

def compute_init_lam(nlp, x=None, lam_max=1e3):
    if x is None:
        x = nlp.init_primals()
    else:
        assert x.size == nlp.n_primals()
    nlp.set_primals(x)

    assert nlp.n_ineq_constraints() == 0, "only supported for equality constrained nlps for now"

    nx = nlp.n_primals()
    nc = nlp.n_constraints()

    # create Jacobian
    jac = nlp.evaluate_jacobian()

    # create gradient of objective
    df = nlp.evaluate_grad_objective()

    # create KKT system
    kkt = BlockSymMatrix(2)
    kkt[0, 0] = identity(nx)
    kkt[1, 0] = jac

    zeros = np.zeros(nc)
    rhs = BlockVector([-df, zeros])

    flat_kkt = kkt.tocoo().tocsc()
    flat_rhs = rhs.flatten()

    sol = spsolve(flat_kkt, flat_rhs)
    return sol[nlp.n_primals() : nlp.n_primals() + nlp.n_constraints()]

#################################################################
m = create_model(4.5, 1.0)
opt = pyo.SolverFactory('ipopt')
results = opt.solve(m, tee=True)

#################################################################

nlp = PyomoNLP(m)
x = nlp.init_primals()
y = compute_init_lam(nlp, x=x)
nlp.set_primals(x)
nlp.set_duals(y)

J = nlp.evaluate_jacobian()
H = nlp.evaluate_hessian_lag()

M = BlockSymMatrix(2)
M[0, 0] = H
M[1, 0] = J

sens_vars = [m.eta1, m.eta2]
nsens  = len(sens_vars)
nr = M.shape[0]

#Np = BlockMatrix(2, 1)
#Np[0, 0] = nlp.extract_submatrix_hessian_lag(pyomo_variables_rows=nlp.get_pyomo_variables(), pyomo_variables_cols=[m.eta1, m.eta2])
#Np[1, 0] = nlp.extract_submatrix_jacobian(pyomo_variables=[m.eta1, m.eta2], pyomo_constraints=nlp.get_pyomo_constraints())

Np = np.zeros((nr, nsens))
Np[(nr - nsens):nr,:] = np.eye(nsens)

sens_cons = ['consteta1', 'consteta2']
clist = nlp.constraint_names()
nc = len(clist)
Np = np.zeros((nr, nsens))
for i, cons in enumerate(sens_cons):
    Np[nr - nc + clist.index(cons), i] = 1

ds = spsolve(M.tocsc(), Np)
print(nlp.variable_names())

#################################################################

p0 = np.array([pyo.value(m.nominal_eta1), pyo.value(m.nominal_eta2)])
p = np.array([4.45, 1.05])
dp = p - p0
dx = ds.dot(dp)[0:nlp.n_primals()]
new_x = x + dx
print(new_x)

#################################################################
m = create_model(4.45, 1.05)
opt = pyo.SolverFactory('ipopt')
results = opt.solve(m, tee=True)
nlp = PyomoNLP(m)
print(nlp.init_primals())