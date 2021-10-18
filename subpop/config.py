import logging
import os


class ConfigurationError(Exception):
	pass


class SubPopModel:

	_files = {}

	config_files = {}
	# Any config files that simply *must* exist:
	required_files = set()

	def __init__(self, config: dict = None):
		if config is None:
			config = {}

		# See if we have received a custom environment. If not, use our default environment:

		self.env = config.get("env", None)
		if self.env is None:
			self.env = os.environ

		file_override = config.get("files", {})
		stream_override = config.get("streams", {})

		for key, fn in self.config_files.items():
			file_like = None
			if key in file_override:
				fn = file_override[key]
			elif key in stream_override:
				file_like = stream_override[key]

			if file_like:
				self._files[key] = file_like.read()
			else:
				# Poor man's tilde expansion, only supporting current user and using specified env:
				if fn.startswith("~/"):
					home = self.home()
					if home is None:
						raise ConfigurationError(f"Use of '~/' in {fn} without HOME being defined in environment.")
					fn = os.path.join(home, fn[2:].lstrip("/"))
				try:
					with open(fn, 'r') as myf:
						self._files[key] = myf.read()
				except FileNotFoundError as fe:
					if key in self.required_files:
						raise fe
					# Configuration files might be optional. In this case, we'll provide an
					# 'empty' (empty string) configuration file.
					logging.debug(f"Configuration file {fn} not found. Using empty configuration.")
					self._files[key] = ""

	def get_file(self, key):
		if key not in self._files:
			raise KeyError(f"Config file specified by '{key}' not found.")
		return self._files[key]

	async def initialize(self, **config_kwargs):
		"""
		Subclasses should override this to perform any config file parsing, etc.
		"""
		pass

	async def start(self, **config_kwargs):
		await self.initialize(**config_kwargs)

	def home(self):
		try:
			return self.env["HOME"]
		except IndexError:
			return None
