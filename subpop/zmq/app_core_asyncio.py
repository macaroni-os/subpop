#!/usr/bin/python3

import random
import string
import sys
import traceback

from zmq.asyncio import Context
from zmq.auth.asyncio import AsyncioAuthenticator

from subpop.zmq.key_monkey import *
from subpop.zmq.zmq_msg_breezyops import BreezyMessage, MessageType


class DealerConnection(object):

	def __init__(self, app=None, keyname="client", remote_keyname="server", register_args=None, endpoint="tcp://127.0.0.1:5556", identity=None, crypto=True):
		self.app = app
		self.keyname = keyname
		self.remote_keyname = remote_keyname
		self.endpoint = endpoint
		self.crypto = crypto
		self.register_args = register_args
		self.ctx = Context.instance()
		self.client = self.ctx.socket(zmq.DEALER)
		if identity is None:
			self.client.setsockopt(zmq.IDENTITY, (''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(16)).encode("ascii")))
		else:
			self.client.setsockopt(zmq.IDENTITY, identity.encode('utf-8'))
		if self.crypto:
			self.keymonkey = KeyMonkey(keyname)
			self.client = self.keymonkey.setupClient(self.client, self.endpoint, remote_keyname)
		logging.info("Connecting to " + self.endpoint)
		self.client.connect(self.endpoint)

	def send_traceback(self, service_name, exception=None):
		if exception:
			exc_type = type(exception)
			exc_value = exception
			exc_traceback = exception.__traceback__
		else:
			exc_type, exc_value, exc_traceback = sys.exc_info()
		msg_obj = BreezyMessage(msg_type=MessageType.INFO,
		                        service="messaging",
		                        action="infra-message",
		                        json_dict={
			                        "message": f"Exception encountered in {service_name}:\n" + ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))})
		msg_obj.send(self.client)

	async def setup(self):
		pass

	async def start(self):
		await self.setup()


class RouterListener(object):

	zap_socket_count = 0

	def __init__(self, app=None, keyname="server", bind_addr="tcp://127.0.0.1:5556", crypto=True, zap_auth=True):

		self.app = app
		self.keyname = keyname
		self.bind_addr = bind_addr
		self.crypto = crypto
		self.zap_auth = zap_auth

		self.ctx = Context.instance()
		self.identities = {}

		self.server = self.ctx.socket(zmq.ROUTER)

		if self.crypto:
			self.keymonkey = KeyMonkey(self.keyname)
			self.server = self.keymonkey.setupServer(self.server, self.bind_addr)

		self.server.bind(self.bind_addr)
		logging.debug("%s listening for new client connections at %s" % (self.keyname, self.bind_addr))
		# Setup ZAP:
		if self.zap_auth:
			zap_socket_bind = "inproc://zeromq.zap.%2d" % RouterListener.zap_socket_count
			RouterListener.zap_socket_count += 1
			if not self.crypto:
				logging.fatal("ZAP requires CurveZMQ (crypto) to be enabled. Exiting.")
				sys.exit(1)
			self.auth = AsyncioAuthenticator(self.ctx)
			self.auth.start(zap_socket_bind)
			self.auth.allow("127.0.0.1")
			logging.info("ZAP enabled. Authorizing clients in %s." % self.keymonkey.authorized_clients_dir)
			if not os.path.isdir(self.keymonkey.authorized_clients_dir):
				logging.fatal("Directory not found: %s. Exiting." % self.keymonkey.authorized_clients_dir)
				sys.exit(1)
			self.auth.configure_curve(domain='*', location=self.keymonkey.authorized_clients_dir)
		self.setup()

	def setup(self):
		pass

	async def start(self):
		pass

# vim: ts=4 sw=4 noet
