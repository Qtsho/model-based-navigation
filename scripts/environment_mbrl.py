#!/usr/bin/env python

# Authors: Tien Tran, adapted from ROBOTIS 
# mail: quang.tran@fh-dortmund.de

import rospy
import numpy as np
import math
from math import pi
from geometry_msgs.msg import Twist, Point, Pose
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
from std_srvs.srv import Empty
from tf.transformations import euler_from_quaternion, quaternion_from_euler
from respawnGoal import Respawn

class Env():
    def __init__(self, action_size):
        self.goal_x = 0
        self.goal_y = 0
        self.heading = 0
        self.action_size = action_size
        self.action_space = np.arange(0,action_size,1)
        self.observation_space = (2,)
        self.max_scan = 5.5
        
        self.initGoal = True
        self.get_goalbox = False
        self.position = Pose()
        self.pub_cmd_vel = rospy.Publisher('cmd_vel', Twist, queue_size=5)
        self.sub_odom = rospy.Subscriber('odom', Odometry, self.getOdometry) # altomatically jump to callback
        self.reset_proxy = rospy.ServiceProxy('gazebo/reset_world', Empty)
        self.unpause_proxy = rospy.ServiceProxy('gazebo/unpause_physics', Empty)
        self.pause_proxy = rospy.ServiceProxy('gazebo/pause_physics', Empty)
        self.respawn_goal = Respawn()
        self.min_range = 0.13

    def getGoalDistace(self):
        goal_distance = round(math.hypot(self.goal_x - self.position.x, self.goal_y - self.position.y), 2)

        return goal_distance
    
    def getOdometry(self, odom):# call back when odometry data is receivee
        self.position = odom.pose.pose.position
        orientation = odom.pose.pose.orientation
        orientation_list = [orientation.x, orientation.y, orientation.z, orientation.w] # a list of orientation as quaternion
        _, _, yaw = euler_from_quaternion(orientation_list)

        goal_angle = math.atan2(self.goal_y - self.position.y, self.goal_x - self.position.x)

        heading = goal_angle - yaw
        if heading > pi:
            heading -= 2 * pi

        elif heading < -pi:
            heading += 2 * pi

        self.heading = round(heading, 2)


    def _get_obs(self):
    
        heading = self.heading
        self.obs_dict = {}
        self.obs_dict['position'] = np.append(self.position, self.heading)
        current_distance = round(math.hypot(self.goal_x - self.position.x, self.goal_y - self.position.y),2)
        data = None

        while data is None:
            try:
                data = rospy.wait_for_message('scan', LaserScan, timeout=5)
            except:
                print ("Error while waiting laser message!")
                pass
        scan_range = []
        for i in range(len(data.ranges)):
            if data.ranges[i] == float('Inf'):
                scan_range.append(self.max_scan)
            elif np.isnan(data.ranges[i]):
                scan_range.append(0)
            else:
                scan_range.append(data.ranges[i])

        done = 0
        if self.min_range > min(scan_range) > 0:
            done = 1
        scan  = np.array([scan_range])
        pos = np.array([heading, current_distance])
        observations = pos
        print(observations)
        return observations, done

    def step(self, action):
        # max_angular_vel = 1.5
        # ang_vel = ((self.action_size - 1)/2 - action) * max_angular_vel * 0.5
        linear = action[0]
        angular = action[1]
        #step
        vel_cmd = Twist()
        vel_cmd.linear.x = linear
        vel_cmd.angular.z = angular
        self.pub_cmd_vel.publish(vel_cmd)

        #obs/reward/done/score
        ob, done = self._get_obs()
        rew = self.getReward(ob, action)
        score = 0 #DUMMY, TODO: get score

        #return
        env_info = {'obs_dict': self.obs_dict,
                    'rewards': rew,
                    'score': score}
        return ob, rew, done, env_info

    def getReward(self, observations, actions): 
        
       
        if(len(observations.shape)==1): # 1D array
            observations = np.expand_dims(observations, axis = 0) #covert to 2D array with (1,obs)
            actions = np.expand_dims(actions, axis = 0)
            batch_mode = False
        else:
            batch_mode = True


        headings = observations[:,0]
        yaw_rewards = []
        current_distance = observations [:,1]
        self.reward_dict = {}

        distance_rate = 2 ** (current_distance / self.goal_distance) #reward for distance to goal

        #TODO: reward funtion
        self.reward_dict['distance reward'] = distance_rate
       
        # if current_distance:# batch mode, wont work
        #     self.get_goalbox = True
        #     rospy.loginfo("Goal!!")
        #     self.reward_dict['distance reward']  = 1000
        #     self.pub_cmd_vel.publish(Twist()) # stop
        #     self.goal_x, self.goal_y = self.respawn_goal.getPosition(True, delete=True)
        #     self.goal_distance = self.getGoalDistace()
        #     self.get_goalbox = False

        self.reward_dict['r_total'] = self.reward_dict['distance reward']

        if(not batch_mode):
            return self.reward_dict['r_total'][0]
        return self.reward_dict['r_total'] 


    def reset(self):
        rospy.wait_for_service('gazebo/reset_world')
        try:
            self.reset_proxy()
        except (rospy.ServiceException) as e:
            print("gazebo/reset_world service call failed")

        data = None
        while data is None:
            try:
                data = rospy.wait_for_message('scan', LaserScan, timeout=5)
            except:
                print ("Error while waiting laser message!")
                pass

        if self.initGoal:
            self.goal_x, self.goal_y = self.respawn_goal.getPosition()
            self.initGoal = False

        self.goal_distance = self.getGoalDistace()
        state, done = self._get_obs()

        return np.asarray(state)
        #later added funtion:pause the simulation
    def pause(self):
        rospy.wait_for_service('gazebo/pause_physics')
        try:
            self.pause_proxy()
        except (rospy.ServiceException) as e:
            print("gazebo/pause_physics service call failed")
    #later added funtion: unpause the simulation
    def unpause (self):
        rospy.wait_for_service('gazebo/unpause_physics')
        try:
            self.unpause_proxy()
        except (rospy.ServiceException) as e:
            print("gazebo/unpause_physics service call failed")

