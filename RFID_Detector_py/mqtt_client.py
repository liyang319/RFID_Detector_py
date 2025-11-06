import paho.mqtt.client as mqtt
import time
import json
import queue
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment
import threading
import datetime
import sys


class MqttClient:

    def __init__(self, broker, port=1883, keepalive=60, username=None, password=None, client_id=None):
        self.broker = broker
        self.port = port
        self.keepalive = keepalive
        self.username = username
        self.password = password
        # self.client_id = client_id or ""
        self.client_id = "RFID_DETECTOR_" + client_id
        self.client = mqtt.Client(client_id=self.client_id)

        # 设置回调函数
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.subscriptions = []

        self.data_topic = "DEVICE/DATA/DTU/" + client_id
        self.response_topic = "DEVICE/RESPONSE/DTU/" + client_id
        self.command_topic = "DEVICE/COMMAND/DTU/" + client_id
        self.connected = False

        # 消息队列
        self.message_queue = queue.Queue()

        # 如果提供了用户名和密码，则设置它们
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)

    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code " + str(rc))
        for topic in self.subscriptions:
            client.subscribe(topic)
        self.connected = True

    def on_message(self, client, userdata, msg):
        message = msg.payload.decode()
        # print(f"type={type(message)}")
        print(f"Received message '{message}' on topic '{msg.topic}'")
        self.message_queue.put((msg.topic, message))
        # print(f"recv size={self.message_queue.qsize()}")

    def connect(self):
        self.client.connect(self.broker, self.port, self.keepalive)
        self.client.loop_start()

    def subscribe(self, topic):
        self.subscriptions.append(topic)
        self.client.subscribe(topic)
        print(topic)

    def publish(self, topic, message):
        if self.connected:
            self.client.publish(topic, message)
            print(f"Published message: '{message}' to topic: '{topic}'")
            # 一定要加这一行！！！否则第一条收不到
            self.client.loop()
        else:
            print("Cannot publish message, client is not connected.")

    def loop_forever(self):
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Exiting...")
        finally:
            self.disconnect()

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def get_message(self):
        """从消息队列中获取消息，如果队列为空则返回 None"""
        try:
            return self.message_queue.get_nowait()  # 非阻塞获取消息
        except queue.Empty:
            return None

    def clear_message_queue(self):
        """清空消息队列"""
        with self.message_queue.mutex:  # 访问队列的 mutex
            self.message_queue.queue.clear()  # 清空队列
        print("Message queue cleared.")

    def message_count(self):
        """获取消息队列中的消息个数"""
        return self.message_queue.qsize()  # 返回队列的大小

    def mqtt_report_rfid_tags(self):
        self.clear_message_queue()
        cmd = 'report_tags'
        print('mqtt_report_rfid_tags')
        data = [
            {
                "cmd": "parameters",
                "type": cmd
            }
        ]
        json_string = json.dumps(data)
        # print(json_string)
        self.publish(self.command_topic, json_string)
        return True
