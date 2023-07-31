import numpy as np
import pandas as pd
from sklearn.neighbors import KDTree
import geopandas as gpd
import gurobipy as gp

# return a binary (only contain 0 or 1) array  
# the array [a, b] indicates if the point y[b] is within the r distance of x[a] 
def distance_matrix_binary(x, y, r):
    x = np.asarray(x)
    y = np.asarray(y)
    (M, k) = x.shape
    (N, kk) = y.shape
    if k != kk:
        raise ValueError('The length of the second dimensions of x and y must be equal'
                         )
    if r < 0:
        raise ValueError('Radius must be a non-negative number.')
    mat = np.zeros((M, N), dtype=bool)
    if M < N:
        tree = KDTree(y)
        idx = tree.query_radius(x, r, count_only=False,
                                return_distance=False)
        for i in range(M):
            mat[i, idx[i]] = 1
        return mat
    else:
        tree = KDTree(x)
        idx = tree.query_radius(y, r, count_only=False,
                                return_distance=False)
        for i in range(N):
            mat[idx[i], i] = 1
        return mat
 
# I and J are the number of demand points and potential facility locations, 
# The s parameter is a dictionary that indicates whether a demand point i is within the service range of location j
# The c parameter is the maximum number of facilities that can be opened.
# v representing the value associated with each demand point. 
# budget = 0 means no budget limit
def solve_mclp(I, J, D, max_count, cost, budget, v, opened):
    # Create a new model
    m = gp.Model("mclp_update")

    # Add variables
    x = {}
    y = {}

    for i in range(I):
        y[i] = m.addVar(vtype=gp.GRB.BINARY, name='y%d' % i)

    for j in range(J):
        x[j] = m.addVar(vtype=gp.GRB.BINARY, name='x%d' % j)

    # Add constraints
    m.addConstr(gp.quicksum(x[j] for j in range(J)) <= max_count)

    # facilities that are already opened
    for j in opened:
        m.addConstr(x[j] == 1)

    # the distance coverage constraints
    for i in range(I):
        m.addConstr(gp.quicksum(x[j] for j in np.where(D[i] == 1)[0]) >= y[i])

    # the budget coverage constraint
    if budget > 0:
        m.addConstr(gp.quicksum(x[j] * cost[j] for j in range(J)) <= budget, "budget")

    m.setObjective(gp.quicksum(y[i] * v[i] for i in range(I)), gp.GRB.MAXIMIZE)
    m.setParam('OutputFlag', 0)
    m.optimize()
    # Optimize model

    solution = []
    if m.status == gp.GRB.Status.OPTIMAL:
        for v in m.getVars():
            if v.x == 1 and v.varName[0] == 'x':
                solution.append(int(v.varName[1:]))

    return (solution, m.objVal)
    

# the actual function to solve the result
def solve_result(demand_filepath, bb_filepath, radius, max_count, cost_field, budget, value_field, opened):
    # read from demand file and facilities file
    demand_ls = gpd.read_file(demand_filepath)
    billboards_ls = pd.read_csv(bb_filepath)
    demand_ls['easting'] = demand_ls.geometry.x
    demand_ls['northing'] = demand_ls.geometry.y
    I = len(demand_ls)
    J = len(billboards_ls)
    s = distance_matrix_binary(demand_ls[['easting', 'northing']].values, billboards_ls[['POINT_X', 'POINT_Y']].values, radius)
    # pricing of the billboard array
    cost = billboards_ls[cost_field]
    # value of the demand pts array
    v = demand_ls[value_field]
    # Run mclp opt_sites is the location of optimal sites and f is the points covered
    opt_billboards, total_covered_val = solve_mclp(I, J, s, max_count, cost, budget, v, opened)
    billboards = billboards_ls.iloc[opt_billboards]
    return billboards, total_covered_val




