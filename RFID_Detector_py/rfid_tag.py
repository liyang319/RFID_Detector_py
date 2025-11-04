# rfid_tag.py
from datetime import datetime
from typing import Optional, Dict, Any


class RFIDTag:
    """RFID标签类，用于存储和管理标签信息"""

    def __init__(self):
        # 基础RFID数据
        self.epc: str = ""  # EPC数据（十六进制字符串）
        self.tid: str = ""  # TID数据（十六进制字符串）
        self.user_data: str = ""  # USER数据（十六进制字符串）
        self.rssi: float = 0.0  # RSSI信号强度（dBm）
        self.antenna_num: int = 0  # 天线号
        self.pc: str = ""  # PC数据（十六进制字符串）

        # 产品信息
        self.product_name: str = ""  # 产品名称
        self.manufacturer: str = ""  # 生产企业
        self.license_number: str = ""  # 生产许可证编号
        self.production_date: str = ""  # 生产日期
        self.batch_number: str = ""  # 批号
        self.package_spec: str = ""  # 包装规格
        self.package_method: str = ""  # 包装方式
        self.quantity: int = 0  # 数量

        # 位置信息
        self.longitude: float = 0.0  # 经度
        self.latitude: float = 0.0  # 纬度

        # 系统信息
        self.timestamp: str = ""  # 读取时间戳
        self.success: bool = False  # 解析是否成功
        self.error_message: str = ""  # 错误信息

    def from_bytes(self, data: bytes) -> bool:
        """
        从字节数据解析RFID标签信息

        Args:
            data: 接收到的完整数据包

        Returns:
            bool: 解析是否成功
        """
        try:
            # 检查数据长度
            if len(data) < 51:  # 需要至少51字节
                self.error_message = f'数据长度不足，需要至少51字节，实际收到{len(data)}字节'
                self.success = False
                return False

            # 解析PC数据 (字节5-6，共2字节)
            pc_data = data[5:7]
            self.pc = ' '.join([f'{b:02X}' for b in pc_data])

            # 解析EPC数据 (字节8-19，共12字节)
            epc_data = data[7:19]
            self.epc = ' '.join([f'{b:02X}' for b in epc_data])

            # 解析TID数据 (字节20-31，共12字节)
            tid_data = data[19:31]
            self.tid = ' '.join([f'{b:02X}' for b in tid_data])

            # 解析USER数据 (字节32-47，共16字节)
            user_data = data[31:47]
            self.user_data = ' '.join([f'{b:02X}' for b in user_data])

            # 解析RSSI数据 (字节47-48，共2字节)
            rssi_data = data[47:49]
            rssi_int = int.from_bytes(rssi_data, byteorder='big', signed=True)
            self.rssi = rssi_int / 10.0  # 转换为实际值

            # 解析天线号 (字节50，第51个字节)
            self.antenna_num = data[49]

            # 设置时间戳
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 从USER数据中解析产品信息（根据实际协议实现）
            self._parse_product_info()

            self.success = True
            self.error_message = ""
            return True

        except Exception as e:
            self.error_message = f'解析RFID数据失败: {str(e)}'
            self.success = False
            return False

    def _parse_product_info(self):
        """从USER数据中解析产品信息（需要根据实际协议实现）"""
        try:
            # 示例解析逻辑，根据你的实际协议修改
            if self.user_data:
                # 假设USER数据包含产品信息，这里需要根据你的协议格式解析
                # 示例：从USER数据中提取信息
                user_bytes = bytes.fromhex(self.user_data.replace(' ', ''))

                # 这里添加你的产品信息解析逻辑
                # 例如：前几个字节表示产品名称编码等

                # 临时示例数据
                self.product_name = f"产品-{self.epc[:8]}"
                self.manufacturer = "默认生产企业"
                self.license_number = "SC20240001"
                self.production_date = "2024-08-15"
                self.batch_number = f"BATCH-{self.tid[:6]}"
                self.package_spec = "标准规格"
                self.package_method = "箱装"
                self.quantity = 1
                self.longitude = 116.3918173
                self.latitude = 39.9797956

        except Exception as e:
            # 解析失败时使用默认值
            self._set_default_product_info()

    def _set_default_product_info(self):
        """设置默认的产品信息"""
        self.product_name = "未知产品"
        self.manufacturer = "未知生产企业"
        self.license_number = "未知许可证"
        self.production_date = datetime.now().strftime("%Y-%m-%d")
        self.batch_number = f"BATCH-{self.tid[:6] if self.tid else 'UNKNOWN'}"
        self.package_spec = "标准规格"
        self.package_method = "箱装"
        self.quantity = 1
        self.longitude = 116.3918173
        self.latitude = 39.9797956

    def to_dict(self) -> Dict[str, Any]:
        """将标签信息转换为字典"""
        return {
            # RFID基础数据
            'epc': self.epc,
            'tid': self.tid,
            'user_data': self.user_data,
            'rssi': self.rssi,
            'antenna_num': self.antenna_num,
            'pc': self.pc,

            # 产品信息
            'product_name': self.product_name,
            'manufacturer': self.manufacturer,
            'license_number': self.license_number,
            'production_date': self.production_date,
            'batch_number': self.batch_number,
            'package_spec': self.package_spec,
            'package_method': self.package_method,
            'quantity': self.quantity,

            # 位置信息
            'longitude': self.longitude,
            'latitude': self.latitude,

            # 系统信息
            'timestamp': self.timestamp,
            'success': self.success,
            'error_message': self.error_message
        }

    def from_dict(self, data: Dict[str, Any]) -> bool:
        """从字典加载标签信息"""
        try:
            # RFID基础数据
            self.epc = data.get('epc', '')
            self.tid = data.get('tid', '')
            self.user_data = data.get('user_data', '')
            self.rssi = data.get('rssi', 0.0)
            self.antenna_num = data.get('antenna_num', 0)
            self.pc = data.get('pc', '')

            # 产品信息
            self.product_name = data.get('product_name', '')
            self.manufacturer = data.get('manufacturer', '')
            self.license_number = data.get('license_number', '')
            self.production_date = data.get('production_date', '')
            self.batch_number = data.get('batch_number', '')
            self.package_spec = data.get('package_spec', '')
            self.package_method = data.get('package_method', '')
            self.quantity = data.get('quantity', 0)

            # 位置信息
            self.longitude = data.get('longitude', 0.0)
            self.latitude = data.get('latitude', 0.0)

            # 系统信息
            self.timestamp = data.get('timestamp', '')
            self.success = data.get('success', False)
            self.error_message = data.get('error_message', '')

            return True

        except Exception as e:
            self.error_message = f'从字典加载数据失败: {str(e)}'
            self.success = False
            return False

    def get_summary(self) -> str:
        """获取标签摘要信息"""
        if not self.success:
            return f"标签解析失败: {self.error_message}"

        return (f"EPC: {self.epc}\n"
                f"TID: {self.tid}\n"
                f"产品: {self.product_name}\n"
                f"生产企业: {self.manufacturer}\n"
                f"批号: {self.batch_number}\n"
                f"信号强度: {self.rssi:.1f} dBm\n"
                f"天线: {self.antenna_num}\n"
                f"时间: {self.timestamp}")

    def is_valid(self) -> bool:
        """检查标签数据是否有效"""
        return (self.success and
                len(self.epc) > 0 and
                len(self.tid) > 0 and
                self.rssi != 0.0)

    def __str__(self) -> str:
        """字符串表示"""
        return self.get_summary()

    def __repr__(self) -> str:
        """详细表示"""
        return (f"RFIDTag(epc='{self.epc}', tid='{self.tid}', "
                f"product='{self.product_name}', rssi={self.rssi}, "
                f"antenna={self.antenna_num}, success={self.success})")