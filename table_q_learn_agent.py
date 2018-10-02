
import random
from action_utils import valid_actions, ActionUtils
from qlearn import QLearningTable
from pysc2.agents import base_agent
from pysc2.lib import actions, features, units
import numpy as np
import math
import os
import pandas as pd
import datetime
from collections import deque

_PLAYER_HOSTILE = 4
_PLAYER_SELF = 1

action_mapping = {
	'NOTHING':['NOTHING'],
	'TRAIN_BARRACKS_MARINE':['SELECT_BARRACKS_ALL','TRAIN_BARRACKS_MARINE'],
	'TRAIN_BARRACKS_REAPER':['SELECT_BARRACKS','TRAIN_BARRACKS_REAPER'],
	'TRAIN_BARRACKS_MARAUDER':['SELECT_BARRACKS','TRAIN_BARRACKS_MARAUDER'],
	'TRAIN_FACTORY_HELLION':['SELECT_FACTORY','TRAIN_FACTORY_HELLION'],
	'TRAIN_FACTORY_TANK':['SELECT_FACTORY','TRAIN_FACTORY_TANK'],
	'TRAIN_SCV':['SELECT_COMMAND_CENTER','TRAIN_SCV'],
	'BUILD_COMMANDCENTER':['SELECT_SCV','BUILD_COMMANDCENTER'],
	'BUILD_BARRACKS':['SELECT_SCV','BUILD_BARRACKS'],
	'BUILD_SUPPLYDEPOT':['SELECT_SCV','BUILD_SUPPLYDEPOT'],
	'BUILD_REFINERY':['SELECT_SCV','BUILD_REFINERY'],
	'BUILD_ENGBAY':['SELECT_SCV','BUILD_ENGBAY'],
	'BUILD_FACTORY':['SELECT_SCV','BUILD_FACTORY'],
	'BUILD_FACTORY_TECH_LAB':['SELECT_FACTORY','BUILD_FACTORY_TECH_LAB'],
	'BUILD_BARRACKS_TECH_LAB':['SELECT_BARRACKS','BUILD_BARRACKS_TECH_LAB']
}

for mm_x in range(0, 64):
	for mm_y in range(0, 64):
		if (mm_x + 1) % 32 == 0 and (mm_y + 1) % 32 == 0:
			attack = 'ATTACK_' + str(mm_x - 16) + '_' + str(mm_y - 16)
			action_mapping[attack] = ['SELECT_ARMY', attack]

high_actions = list(action_mapping.keys())

class TableQLearnAgent(base_agent.BaseAgent):

	def __init__(self):
		super(TableQLearnAgent, self).__init__()
		self.utils = ActionUtils()
		self.qlearn = QLearningTable(actions=list(range(len(high_actions))))
		self.output_file = 'model/table_q_learn_agent.csv'
		self.output_actions_prefix = 'games/game_actions_%d.csv'
		self.output_game_outcome_file = 'game_state/game_outcome.csv'
		
		if os.path.exists(self.output_game_outcome_file):
			self.game_outcomes = pd.read_csv(self.output_game_outcome_file).to_dict('records')
		else:
			self.game_outcomes = []

		self.game_count = len([f for f in os.listdir('games') if os.path.splitext(f)[1] == ".csv"])
		if os.path.isfile(self.output_file + '.gz'):
			self.qlearn.q_table = pd.read_pickle(self.output_file + '.gz', compression='gzip')

	def reset(self):
		super(TableQLearnAgent, self).reset()
		self.previous_action = None
		self.previous_state = None
		self.queue = deque()
		self.game_actions = []
		self.game_count += 1
		print('Game %d' % (self.game_count))

	def create_state(self, obs):
		command_center_count = len(self.utils.get_units(obs, units.Terran.CommandCenter))
		barracks_count = len(self.utils.get_units(obs, units.Terran.Barracks))
		barracks_tech_lab_count = self.utils.count_units(obs, units.Terran.BarracksTechLab)
		supply_depot_count = len(self.utils.get_units(obs, units.Terran.SupplyDepot))
		refinery_count = len(self.utils.get_units(obs, units.Terran.Refinery))
		eng_bay_count = len(self.utils.get_units(obs, units.Terran.EngineeringBay))
		factory_count = len(self.utils.get_units(obs, units.Terran.Factory))
		factory_tech_lab_count = len(self.utils.get_units(obs, units.Terran.FactoryTechLab))
		army_supply = obs.observation.player.food_army
		worker_supply = obs.observation.player.food_workers
		supply_free = obs.observation.player.food_cap - obs.observation.player.food_used
		vespene = obs.observation.player.vespene

		state_elements = 8
		current_state = np.zeros(8 + 4 + 4)
		current_state[0] = command_center_count
		current_state[1] = supply_depot_count
		current_state[2] = barracks_count
		current_state[3] = refinery_count
		current_state[4] = eng_bay_count
		current_state[5] = factory_count
		current_state[6] = army_supply
		current_state[7] = worker_supply

		# current_state[3] = len(self.utils.get_units(obs, units.Terran.EngineeringBay))
		# current_state[4] = len(self.utils.get_units(obs, units.Terran.Factory))
		# current_state[2] = len(self.utils.get_units(obs, units.Terran.SCV))
		# current_state[3] = obs.observation.player.food_cap
		# current_state[6] = obs.observation.player.food_used / (obs.observation.player.food_cap + 0.01)
		# current_state[4] = obs.observation.player.army_count
		# current_state[0] = self.quantize(obs.observation.player.minerals)
		# current_state[0] = self.quantize(obs.observation.player.vespene)

		hot_squares = np.zeros(4)
		player_relative = obs.observation.feature_minimap.player_relative  
		enemy_y, enemy_x = (player_relative == features.PlayerRelative.ENEMY).nonzero()
		for i in range(0, len(enemy_y)):
			y = int(math.ceil((enemy_y[i] + 1) / 32))
			x = int(math.ceil((enemy_x[i] + 1) / 32))
			
			hot_squares[((y - 1) * 2) + (x - 1)] = 1

		if not self.base_top_left:
			hot_squares = hot_squares[::-1]

		for i in range(0, 4):
			current_state[i + state_elements] = hot_squares[i]

		state_elements += 4

		green_squares = np.zeros(4)        
		friendly_y, friendly_x = (player_relative == features.PlayerRelative.SELF).nonzero()
		for i in range(0, len(friendly_y)):
			y = int(math.ceil((friendly_y[i] + 1) / 32))
			x = int(math.ceil((friendly_x[i] + 1) / 32))
			
			green_squares[((y - 1) * 2) + (x - 1)] = 1

		if not self.base_top_left:
			green_squares = green_squares[::-1]

		for i in range(0, 4):
			current_state[i + state_elements] = green_squares[i]

		excluded_actions = []

		if command_center_count >= 1:
			excluded_actions.append(high_actions.index('BUILD_COMMANDCENTER'))

		if vespene == 0 or barracks_count == 0:
			excluded_actions.append(high_actions.index('BUILD_BARRACKS_TECH_LAB'))

		if vespene == 0 or factory_count == 0:
			excluded_actions.append(high_actions.index('BUILD_FACTORY_TECH_LAB'))

		if factory_count >= 1 or worker_supply == 0:
			excluded_actions.append(high_actions.index('BUILD_FACTORY'))

		if eng_bay_count >= 1 or worker_supply == 0:
			excluded_actions.append(high_actions.index('BUILD_ENGBAY'))

		if refinery_count >= 2 or worker_supply == 0:
			excluded_actions.append(high_actions.index('BUILD_REFINERY'))

		if supply_depot_count >= 5 or worker_supply == 0:
			excluded_actions.append(high_actions.index('BUILD_SUPPLYDEPOT'))

		if supply_depot_count == 0 or barracks_count >= 2 or worker_supply == 0:
			excluded_actions.append(high_actions.index('BUILD_BARRACKS'))

		if supply_free == 0 or barracks_count == 0 or barracks_tech_lab_count == 0:
			excluded_actions.append(high_actions.index('TRAIN_BARRACKS_MARINE'))
			excluded_actions.append(high_actions.index('TRAIN_BARRACKS_REAPER'))

		if supply_free == 0 or barracks_count == 0 or barracks_tech_lab_count == 0 or vespene == 0:
			excluded_actions.append(high_actions.index('TRAIN_BARRACKS_MARAUDER'))

		if supply_free == 0 or factory_count == 0 or factory_tech_lab_count == 0:
			excluded_actions.append(high_actions.index('TRAIN_FACTORY_HELLION'))

		if supply_free == 0 or factory_count == 0 or factory_tech_lab_count == 0 or vespene == 0:
			excluded_actions.append(high_actions.index('TRAIN_FACTORY_TANK'))

		if army_supply == 0:
			for i, a in enumerate(high_actions):
				if a.startswith('ATTACK_'):
					excluded_actions.append(i)
			
		return current_state, excluded_actions

	def step(self, obs):
		super(TableQLearnAgent, self).step(obs)

		# print(obs.observation.score_cumulative.score)
		if obs.last():
			reward = obs.reward

			print('\tGame end: Result: %d' % (reward))
			self.qlearn.learn(str(self.previous_state), self.previous_action, reward, 'terminal')
			self.qlearn.q_table.to_pickle(self.output_file + '.gz', 'gzip')
			self.qlearn.q_table.to_csv(self.output_file)

			if reward == -1:
				result = 'loss'
			elif reward == 0:
				result = 'tie'
			else:
				result = 'win'
			
			self.game_outcomes.append({'game':self.game_count, 'outcome':result, 'score':obs.observation.score_cumulative.score, 'time':datetime.datetime.now()})
			pd.DataFrame(self.game_outcomes).to_csv(self.output_game_outcome_file)
			return self.utils.nothing()

		if obs.first():
			player_y, player_x = (obs.observation.feature_minimap.player_relative == features.PlayerRelative.SELF).nonzero()
			self.base_top_left = True if player_y.any() and player_y.mean() <= 31 else False

			command_center = self.utils.get_units(obs, units.Terran.CommandCenter)[0]
			self.command_center_loc = (command_center.x, command_center.y)

		if len(self.queue) == 0:
			current_state, excluded_actions = self.create_state(obs)
			# print(current_state.tolist())

			if self.previous_action is not None:
				self.qlearn.learn(str(self.previous_state), self.previous_action, 0, str(current_state))
				
			rl_action = self.qlearn.choose_action(str(current_state), excluded_actions)

			high_action = high_actions[rl_action]
			new_actions = action_mapping[high_action]
			self.queue.extend(new_actions)

			self.game_actions.append({'action':high_action, 'time':datetime.datetime.now(), 'state':current_state.tolist(), 'score':obs.observation.score_cumulative.score})
			pd.DataFrame(self.game_actions).to_csv(self.output_actions_prefix % (self.game_count))

			self.previous_state = current_state
			self.previous_action = rl_action

		valid_action = self.queue.popleft()

		return self.utils.do(obs, valid_action, self.base_top_left, self.command_center_loc)