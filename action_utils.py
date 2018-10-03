from pysc2.lib import actions, features, units
from enum import Enum, auto
import random

valid_actions = [
	'NOTHING',
	'SELECT_SCV',
	'TRAIN_BARRACKS_MARINE',
	'TRAIN_SCV',
	'TRAIN_BARRACKS_REAPER',
	'TRAIN_FACTORY_HELLION',
	'TRAIN_FACTORY_TANK',
	'TRAIN_BARRACKS_MARAUDER',
	'SELECT_BARRACKS',
	'SELECT_COMMANDCENTER',
	'SELECT_FACTORY',
	'BUILD_BARRACKS',
	'BUILD_BARRACKS_TECH_LAB',
	'SELECT_ENGBAY',
	'BUILD_SUPPLYDEPOT',
	'BUILD_COMMAND_CENTER',
	'BUILD_REFINERY',
	'BUILD_FACTORY',
	'BUILD_FACTORY_TECH_LAB',
	'BUILD_ENGBAY',
	'SELECT_ARMY',
	'RESEARCH_INFANTRY_WEAPONS_UPGRADE',
	'SIEGE',
	'UNSIEGE',
	'LAND',
]

unit_mapping = {
	'BARRACKS':units.Terran.Barracks,
	'ENGBAY':units.Terran.EngineeringBay,
	'FACTORY':units.Terran.Factory,
	'TANK':units.Terran.SiegeTank,
	'SIEGEDTANK':units.Terran.SiegeTankSieged
}

for x in range(64):
	for y in range(64):
		# valid_actions.append('MOVE_%d_%d' % (x, y))
		if (x + 1) % 16 == 0 and (y + 1) % 16 == 0:
			valid_actions.append('ATTACK_%d_%d' % (x - 8, y - 8))

class ActionUtils:

	def __init__(self):
		self.state = {}

	def count_units(self, obs, unit_type):
		return len(self.get_units(obs, unit_type))

	def get_units(self, obs, unit_type):
		return [unit for unit in obs.observation.feature_units if unit.unit_type == unit_type]

	def unit_type_is_selected(self, obs, unit_type):
		if (len(obs.observation.single_select) > 0 and obs.observation.single_select[0].unit_type == unit_type):
		  return True
		
		if (len(obs.observation.multi_select) > 0 and obs.observation.multi_select[0].unit_type == unit_type):
		  return True
		
		return False

	def can_do(self, action, obs):
		return action in obs.observation.available_actions

	def nothing(self):
		return actions.FUNCTIONS.no_op()

	def near(self, unit):
		x = ((-1)**random.randrange(2) * random.randint(0,30)) + unit.x
		y = ((-1)**random.randrange(2) * random.randint(0,30)) + unit.y
		return x,y

	def anywhere(self):
		return (random.randint(0, 83),random.randint(0, 83))

	def train(self, production_unit, action, obs):
		if self.unit_type_is_selected(obs, production_unit) and self.can_do(action.id, obs):
			return action("queued")
		else:
			return self.nothing()

	def build(self, production_unit, action, obs, loc=None):
		if loc is None:
			loc = self.anywhere()
		if self.unit_type_is_selected(obs, production_unit) and self.can_do(action.id, obs):
			return action("queued", loc)
		else:
			return self.nothing()

	def select(self,type, obs, all=True, random_choice=False):
		group = self.get_units(obs, type)
		group_unit = self.find_valid(group, random_choice)
		if group_unit is not None:
			if all:
				action_name = "select_all_type"
			else:
				action_name = "select"
				self.state['selected'] = group_unit
			return actions.FUNCTIONS.select_point(action_name, (group_unit.x, group_unit.y))
		else:
			return self.nothing()

	def find_valid(self, choices, random_choice=False):
		valid_choices = self.find_all_valid(choices)
		if len(valid_choices) > 0:
			if random_choice:
				return random.choice(valid_choices)
			else:
				return valid_choices[0]
		else:
			return None

	def find_all_valid(self, choices):
		return [s for s in choices if s.x >= 0 and s.y >= 0 and s.x < 84 and s.y < 84]

	def transform_distance(self, x, x_distance, y, y_distance, base_top_left):
		if not base_top_left:
			return [x - x_distance, y - y_distance]
		
		return [x + x_distance, y + y_distance]

	def transform_location(self, x, y, base_top_left):
		if not base_top_left:
			return [64 - x, 64 - y]
		
		return [x, y]

	def do(self, obs, choice, base_top_left, base_loc):
		# if obs.first():
		# 	player_y, player_x = (obs.observation.feature_minimap.player_relative == features.PlayerRelative.SELF).nonzero()
		# 	xmean = player_x.mean()
		# 	ymean = player_y.mean()

		# 	if xmean <= 31 and ymean <= 31:
		# 		self.attack_coordinates = (49, 49)
		# 	else:
		# 		self.attack_coordinates = (12, 16)

		print(choice)

		if choice == 'NOTHING':
			return self.nothing()
		elif choice.startswith('ATTACK_'):
			attack_elements = choice.split('_')
			#SCV Hack!
			# if self.can_do(actions.FUNCTIONS.Attack_minimap.id, obs):
			if self.can_do(actions.FUNCTIONS.Attack_minimap.id, obs) and not self.unit_type_is_selected(obs, units.Terran.SCV):

				x_offset = random.randint(-1, 1)
				y_offset = random.randint(-1, 1)

				x = int(attack_elements[1]) + (x_offset * 8)
				y = int(attack_elements[2]) + (y_offset * 8)

				return actions.FUNCTIONS.Attack_minimap("now", self.transform_location(x,y, base_top_left))
			else:
				return self.nothing()
		elif choice == "LAND":
			if self.can_do(actions.FUNCTIONS.Land_screen.id, obs):
				return actions.FUNCTIONS.Land_screen("queued", self.anywhere())
			else:
				return self.nothing()
		elif choice == "SIEGE":
			if self.can_do(actions.FUNCTIONS.Morph_SiegeMode_quick.id, obs):
				return actions.FUNCTIONS.Morph_SiegeMode_quick("now")
			else:
				return self.nothing()
		elif choice == "UNSIEGE":
			if self.can_do(actions.FUNCTIONS.Morph_Unsiege_quick.id, obs):
				return actions.FUNCTIONS.Morph_Unsiege_quick("now")
			else:
				return self.nothing()
		elif choice == 'BUILD_FACTORY_TECH_LAB':
			if 'selected' in self.state:
				loc = (self.state['selected'].x, self.state['selected'].y)
				return self.build(units.Terran.Factory, actions.FUNCTIONS.Build_TechLab_screen, obs, loc)
			else:
				return self.build(units.Terran.Factory, actions.FUNCTIONS.Build_TechLab_screen, obs)
		elif choice == 'BUILD_BARRACKS_TECH_LAB':
			if 'selected' in self.state:
				loc = (self.state['selected'].x, self.state['selected'].y)
				return self.build(units.Terran.Barracks, actions.FUNCTIONS.Build_TechLab_screen, obs, loc)
			else:
				return self.build(units.Terran.Barracks, actions.FUNCTIONS.Build_TechLab_screen, obs)
		elif choice == 'BUILD_COMMANDCENTER':
			return self.build(units.Terran.SCV, actions.FUNCTIONS.Build_CommandCenter_screen, obs)
		elif choice == 'BUILD_FACTORY':
			return self.build(units.Terran.SCV, actions.FUNCTIONS.Build_Factory_screen, obs)
		elif choice == 'BUILD_ENGBAY':
			return self.build(units.Terran.SCV, actions.FUNCTIONS.Build_EngineeringBay_screen, obs)
		elif choice == 'BUILD_BARRACKS':
			return self.build(units.Terran.SCV, actions.FUNCTIONS.Build_Barracks_screen, obs)
		elif choice == 'BUILD_SUPPLYDEPOT':
			return self.build(units.Terran.SCV, actions.FUNCTIONS.Build_SupplyDepot_screen, obs)
		elif choice == 'TRAIN_FACTORY_HELLION':
			return self.train(units.Terran.Factory, actions.FUNCTIONS.Train_Hellion_quick, obs)
		elif choice == 'TRAIN_FACTORY_TANK':
			return self.train(units.Terran.Factory, actions.FUNCTIONS.Train_SiegeTank_quick, obs)
		elif choice == 'TRAIN_BARRACKS_MARINE':
			return self.train(units.Terran.Barracks, actions.FUNCTIONS.Train_Marine_quick, obs)
		elif choice == 'TRAIN_BARRACKS_REAPER':
			return self.train(units.Terran.Barracks, actions.FUNCTIONS.Train_Reaper_quick, obs)
		elif choice == 'TRAIN_BARRACKS_MARAUDER':
			return self.train(units.Terran.Barracks, actions.FUNCTIONS.Train_Marauder_quick, obs)
		elif choice == 'TRAIN_SCV':
			return self.train(units.Terran.CommandCenter, actions.FUNCTIONS.Train_SCV_quick, obs)
		elif choice == 'RESEARCH_INFANTRY_WEAPONS_UPGRADE':
			return self.train(units.Terran.EngineeringBay, actions.FUNCTIONS.Research_TerranInfantryWeapons_quick, obs)
		elif choice == 'BUILD_REFINERY':
			geysers = self.find_all_valid(self.get_units(obs, units.Neutral.VespeneGeyser))
			extractors = self.find_all_valid(self.get_units(obs, units.Terran.Refinery))
			extractor_locs = set([(e.x, e.y) for e in extractors])

			open_geysers = [g for g in geysers if (g.x, g.y) not in extractor_locs]
			if len(open_geysers) > 0:
				return self.build(units.Terran.SCV, actions.FUNCTIONS.Build_Refinery_screen, obs, (open_geysers[0].x, open_geysers[0].y))
			else:
				return self.nothing()
		# elif choice == RETURN_SCV_MINING:
		# 	minerals = self.get_units(obs, units.Neutral.MineralField)
		# 	if len(minerals) > 0 and self.unit_type_is_selected(obs, units.Terran.SCV) and self.can_do(actions.FUNCTIONS.Harvest_Gather_screen.id, obs):
		# 		mineral = random.choice(minerals)
		# 		return actions.FUNCTIONS.Harvest_Gather_screen("now", (mineral.x, mineral.y))
		# 	else:
		# 		return self.nothing(obs)
		elif choice == 'SELECT_SCV':
			if obs.observation.player.idle_worker_count > 0:
				return actions.FUNCTIONS.select_idle_worker("select")
			return self.select(units.Terran.SCV, obs, all=False, random_choice=True)
		elif choice == 'SELECT_ARMY':
			if self.can_do(actions.FUNCTIONS.select_army.id, obs):
				return actions.FUNCTIONS.select_army("select")
			else:
				return self.nothing()
		elif choice.startswith('SELECT_'):
			select_elements = choice.split('_')
			if select_elements[1] in unit_mapping:
				if len(select_elements) == 3 and select_elements[2] == 'ALL':
					all = True
				else:
					all = False
				return self.select(unit_mapping[select_elements[1]], obs, all=all)
			else:
				return self.nothing()
		
		# elif choice == PATROL_ARMY:
		# 	if self.unit_type_is_selected(obs, units.Terran.Marine) and self.can_do(actions.FUNCTIONS.Move_screen.id, obs):
		# 		command_centers = self.get_units(obs, units.Terran.CommandCenter)
		# 		if len(command_centers) > 0:
		# 			command_center = random.choice(command_centers)
		# 			loc = self.near(command_center)
		# 		else:
		# 			loc = (random.randint(0, 83),random.randint(0, 83))
		# 		return actions.FUNCTIONS.Move_screen("now",loc)
		# 	else:
		# 		return self.nothing(obs)
		# elif choice == ATTACK:
		# 	if self.can_do(actions.FUNCTIONS.Attack_minimap.id, obs):
		# 		return actions.FUNCTIONS.Attack_minimap("now", self.attack_coordinates)
		# 	else:
		# 		return self.nothing(obs)
		return self.nothing()