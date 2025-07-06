"""
The default menu of the dice

Features:
1. Switching strategies
2. Manual calibration of the IMU
3. Battery level (requires supported battery)
4. Shutdown

How it works:
- Loads default menu items from menu tree
"""

class ActionItem:
	def __init__(self, fn, *args, **kwargs):
		"""
		Initialize an action item with a function and its arguments.
		
		Args:
			fn: The function to call when the action is triggered.
			args: Positional arguments for the function.
			kwargs: Keyword arguments for the function.
		"""
		self.fn = fn
		self.args = args
		self.kwargs = kwargs
	
	def __call__(self):
		"""
		Call the stored function with its arguments.
		
		Returns:
			The result of the function call.
		"""
		return self.fn(*self.args, **self.kwargs)

class MenuManager:
	def __init__(self):
		self.menu_tree = {
			"Switch Strategy":{}, 		# Populate later
			"Calibrate IMU": ActionItem(self._calibrate_imu),
			"Shutdown": ActionItem(self._shutdown),
		}

	def _load_strategies(self):
		"""From strategy manager, load all strategies discovered, and display"""

	def _calibrate_imu(self):
		"""
		Call the IMU calibration service
		"""
		print("Calibrating IMU...")
		# Add actual IMU calibration logic here, e.g., calling a service or running a calibration routine.
		# This is a placeholder for the actual implementation.

	def _shutdown(self):
		"""
		Shutdown the system.
		
		This method should handle any necessary cleanup before shutting down.
		"""
		print("Shutting down the system...")
		# Add actual shutdown logic here, e.g., stopping services, saving state, etc.
