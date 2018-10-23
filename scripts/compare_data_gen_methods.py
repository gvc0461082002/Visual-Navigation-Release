import numpy as np
import tensorflow as tf
tf.enable_eager_execution()
import tensorflow.contrib.eager as tfe
import matplotlib
import matplotlib.pyplot as plt
from costs.quad_cost_with_wrapping import QuadraticRegulatorRef
from trajectory.spline.spline_3rd_order import Spline3rdOrder
from obstacles.circular_obstacle_map import CircularObstacleMap
from data_gen.data_gen import Data_Generator
from systems.dubins_v1 import Dubins_v1
from optCtrl.lqr import LQRSolver
from dotmap import DotMap
from utils import utils

def create_params():
    p = DotMap()
    p.seed = 1
    p.n = 1
    p.k = 15
    p.map_bounds = [[-2.0, -2.0], [2.0, 2.0]]
    p.dx, p.dt = .05, .1
      
    p.lqr_coeffs = DotMap({'quad' : [1.0, 1.0, 1.0, 1e-10, 1e-10],
                                    'linear' : [0.0, 0.0, 0.0, 0.0, 0.0]})
    p.ctrl = 1.

    p.avoid_obstacle_objective = DotMap(obstacle_margin=0.3,
                                        power=2,
                                        obstacle_cost=25.0)
    # Angle Distance parameters
    p.goal_angle_objective = DotMap(power=1,
                                    angle_cost=25.0)
    # Goal Distance parameters
    p.goal_distance_objective = DotMap(power=2,
                                       goal_cost=25.0)

    return p 

def create_obj_params(p, cs, rs):
    C, c = tf.diag(p.lqr_coeffs.quad, name='lqr_coeffs_quad'), tf.constant(p.lqr_coeffs.linear, name='lqr_coeffs_linear', dtype=tf.float32)

    params = DotMap()
    params.cost_params = {'C' : C, 'c' : c}
    params.obstacle_params = {'centers_m2':cs, 'radii_m1':rs}
    params.plant_params = {'dt' : p.dt}
    params.spline_params = {}
     
    params._cost = QuadraticRegulatorRef
    params._spline = Spline3rdOrder
    params._obstacle_map = CircularObstacleMap
    params._plant = Dubins_v1 
    return params

def build_data_gen(n):
    p = create_params()
    p.n=int(n)
    np.random.seed(seed=p.seed)
    tf.set_random_seed(seed=p.seed)
    n,k = p.n, p.k
    map_bounds = p.map_bounds
    dx, dt = p.dx, p.dt 
    v0, vf = 0., 0.
    wx = np.random.uniform(map_bounds[0][0], map_bounds[1][0], size=n)
    wy = np.random.uniform(map_bounds[0][1], map_bounds[1][1], size=n)
    wt = np.random.uniform(-np.pi, np.pi, size=n)
    vf = np.ones(n)*vf
    wf = np.zeros(n)
    
    start_15 = np.array([-2., -2., 0., v0, 0.])[None]
    map_origin_2 = (start_15[0,:2]/dx).astype(np.int32)
    goal_pos_12 = np.array([0., 0.])[None]  
    
    waypt_n5 = np.stack([wx,wy,wt,vf,wf], axis=1)
    start_n5 = np.repeat(start_15, n, axis=0)
    goal_pos_n2 = np.repeat(goal_pos_12, n, axis=0)
    
 
    cs = np.array([[-1.0, -1.5]])
    rs = np.array([[.5]])
    obj_params = create_obj_params(p, cs, rs) 

    data_gen = Data_Generator(exp_params=p,
                            obj_params=obj_params,
                            start_n5=start_n5,
                            goal_pos_n2=goal_pos_n2,
                            k=k,
                            map_origin_2=map_origin_2)
    waypt_n5 = tfe.Variable(waypt_n5, name='waypt', dtype=tf.float32)
    return data_gen, waypt_n5

def test_random_data_gen(n=5e4, visualize=False):
    data_gen, waypt_n5 = build_data_gen(n=n)
    obj_vals = data_gen.eval_objective(waypt_n5)
    min_idx = tf.argmin(obj_vals)
    min_waypt = waypt_n5[min_idx]
    min_cost = obj_vals[min_idx]
    print(min_cost.numpy())
    if visualize:
        fig, _, axes = utils.subplot2(plt, (2,2), (8,8), (.4, .4))
        fig.suptitle('Random Based Opt (n=%.02e), Cost*: %.03f, Waypt*: [%.03f, %.03f, %.03f]'%(n, min_cost, min_waypt[0], min_waypt[1], min_waypt[2]))
        axes = axes[::-1]
        data_gen.render(axes, batch_idx=min_idx.numpy())
        plt.show()
    else:
        print('rerun test_random_based_data_gen with visualize=True to see visualization')

def test_gradient_based_data_gen(visualize=False):
    data_gen, waypt_n5 = build_data_gen(n=1)
    num_iter = 30
    learning_rate = 1e-1
    opt = tf.train.AdamOptimizer(learning_rate=learning_rate)
    waypt_n5 = tfe.Variable(waypt_n5, name='waypt', dtype=tf.float32)
    objs = []
    for i in range(num_iter):
        obj_val, grads, variables = data_gen.compute_obj_val_and_grad(waypt_n5)
        objs.append(obj_val)
        print('Iter %d: %.02f'%(i+1, obj_val))
        opt.apply_gradients(zip(grads, variables)) 
    obj_vals = data_gen.eval_objective(waypt_n5)
    min_waypt = waypt_n5[0]
    min_cost = obj_vals[0]
    
    if visualize:
        fig, _, axes = utils.subplot2(plt, (3,3), (8,8), (.4, .4))
        fig.suptitle('Gradient Based Opt, Cost*: %.03f, Waypt*: [%.03f, %.03f, %.03f]'%(min_cost, min_waypt[0], min_waypt[1], min_waypt[2]))
        axes = axes[::-1]
        ax4, axes = axes[:4], axes[4:]
        data_gen.render(ax4, batch_idx=0)
        ax = axes[0]
        ax.plot(objs, 'r--')
        ax.set_title('Cost Vs Opt Iter')
        plt.show()
    else:
        print('rerun test_gradient_based_data_gen with visualize=True to see visualization')
    
def main():
    plt.style.use('ggplot')
    test_random_data_gen(n=5e4, visualize=True)
    test_gradient_based_data_gen(visualize=True)

if __name__=='__main__':
    main()
    