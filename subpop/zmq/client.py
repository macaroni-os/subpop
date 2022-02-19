#!/usr/bin/env python3

import asyncio
import logging
import os
import platform
import random
import string
from datetime import datetime
from enum import Enum

from subpop.zmq.app_core_asyncio import DealerConnection
from subpop.zmq.zmq_msg_breezyops import BreezyMessage, MessageType


# TODO: add local socket support.
class HubClientMode(Enum):
	LOCAL = "local"
	REMOTE = "remote"


class HubClient(DealerConnection):

	"""
	A HubClient encapsulates the functionality of connecting to and communicating with a service hub. It provides
	methods for synchronous as well as asynchronous messaging.
	"""

	register_args = {}
	hub_connection_mode = HubClientMode.LOCAL
	in_flight_messages: dict = {}
	msg_id_counter = 0

	def __init__(self, keyname, register_args=None, hub_connection_mode: HubClientMode = None):
		self.keyname = keyname
		if register_args is not None:
			self.register_args = register_args
		if hub_connection_mode is not None:
			self.hub_connection_mode = hub_connection_mode
		if self.hub_connection_mode == HubClientMode.LOCAL:
			endpoint = "tcp://127.0.0.1:5556"
		else:
			endpoint = "tcp://hivemind.funtoo.org:5556"

		# Generate our own identity so that is can persist across connections if needed:

		self.client_id = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(16)) + ":" + platform.node() + ':' + str(os.getpid())

		logging.info("Setting up HubClient, service %s, client ID %s" % (self.keyname, self.client_id))

		DealerConnection.__init__(self, keyname=self.keyname.replace("/", ":"), register_args=self.register_args, remote_keyname="client-hub", identity=self.client_id, endpoint=endpoint)

	def ping(self):
		self.send_nowait(
			BreezyMessage(
				msg_type=MessageType.REQUEST,
				service="hub",
				action="ping",
				json_dict=self.register_args if self.register_args else {}
			)
		)

	async def ping_task(self):
		while True:
			await asyncio.sleep(45)
			self.ping()

	async def start_tasks(self):
		asyncio.create_task(self.ping_task())

	async def start(self):
		self.send_nowait(
			BreezyMessage(
				msg_type=MessageType.INFO,
				service="hub",
				action="client-register",
				json_dict=self.register_args if self.register_args else {}
			)
		)
		await self.start_tasks()
		while True:
			msg = await self.client.recv_multipart()
			await self.on_recv(msg)

	def send_nowait(self, msg_obj: BreezyMessage):
		"""
		Send a message to Service Hub asynchronously, without waiting for a reply. This method is typically
		used by clients or agents who are communicating with the Service Hub.

		:param msg_obj: The fully-formed BreezyMessage to send. We will send it as-is so all fields should
		  be set as needed.
		:return: None
		"""

		msg_obj.send(self.client)

	def async_send(self, msg_obj: BreezyMessage) -> asyncio.Future:
		"""
		The async_send() method is used to send a BreezyMessage to the Service Hub asynchronously and wait for
		a response. It can be used by client tools as well as by RequestHandlers that need to wait for a reply
		to satisfy an HTTP request (and in this case, use BasePageHandler.async_send(), which is a wrapper for
		this method.)

		:param msg_obj: The BreezyMessage to send.
		:return: a Future which can be awaited upon.

		It can be used as follows, although this is not ideal:

		bzm = BreezyMessage()
		bzm_resp = await hub_client.async_send(bzm)

		Be careful to only send messages that expect replies as this async implementation has no built-in
		concept of a timeout and your code could potentially block forever. Thus, a safer and much more
		recommended way to use async_send() is as follows:

		bzm = BreezyMessage()

		try:
			bzm_resp = await asyncio.wait_for(hub_client.async_send(bzm), timeout=10)
			# do other things here with the response.
		except asyncio.TimeoutError:
			# error!

		"""

		msg_obj.msg_id = str(self.msg_id_counter)
		self.msg_id_counter += 1

		fut = asyncio.Future()
		self.in_flight_messages[msg_obj.msg_id] = (fut, datetime.utcnow())
		msg_obj.send(self.client)
		return fut

	async def on_recv(self, msg):
		msg_obj = BreezyMessage.from_msg(msg)
		if msg_obj.msg_type == MessageType.RESPONSE:
			if msg_obj.service == "hub" and msg_obj.action == "ping":
				pass
			elif msg_obj.msg_id in self.in_flight_messages:
				# our agent has received an async response to a request
				fut, orig_date = self.in_flight_messages.pop(msg_obj.msg_id)
				try:
					fut.set_result(msg_obj)
					return fut
				except asyncio.InvalidStateError:
					logging.error(f"Received InvalidStateError when trying set future return response {msg}")
					logging.error("Awaiter may have timed out.")
					return
			else:
				logging.error(f"{self.keyname} received an unexpected message: {msg}")
		elif msg_obj.msg_type == MessageType.REQUEST and msg_obj.service.endswith("/*"):
			# An agent is getting a broadcast....
			resp_obj = None
			action_method_name = "action_" + msg_obj.action.replace('-', '_')
			action_method = getattr(self, action_method_name, None)
			if action_method:
				resp_obj = await action_method(msg_obj)
			else:
				logging.error("Action method not found: %s" % action_method_name)
			if resp_obj:
				# Note that this is not really a response. This is a new message "info" or "req" going out...
				resp_obj.send(self.client)
		else:
			logging.error(f"I really did not expect this: {msg}")

# vim: ts=4 sw=4 noet

