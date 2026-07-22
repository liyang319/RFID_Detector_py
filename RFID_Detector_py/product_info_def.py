# product_info_def.py
# 产品信息编码与名称映射关系

# 产品种类代码 → 产品名称
PRODUCT_CODE_MAP = {
    "02W": "乳化炸药",
    "03W": "铵油炸药",
    "04W": "膨化硝铵炸药",
    "05W": "水胶炸药",
    "06W": "乳化铵油炸药",
}

# 生产企业代码 → 企业名称
MANUFACTURER_CODE_MAP = {
    "D6": "山西太原江阳化工厂",
    "D7": "XX化工有限公司",
    "D8": "YY民爆公司",
}

# 生产企业代码 → 许可证编号
MANUFACTURER_LICENSE_MAP = {
    "D6": "SC20240001",
    "D7": "SC20240002",
    "D8": "SC20240003",
}

# 包装方式编码 → 名称
PACKAGE_MAP = {
    0x58: "袋装",  # 'X'
    0x4C: "袋装",  # 'L'
    # 其他默认为"箱装"
}


def get_product_name(code: str) -> str:
    """根据产品代码获取产品名称"""
    return PRODUCT_CODE_MAP.get(code, f"未知产品({code})")


def get_manufacturer_name(code: str) -> str:
    """根据企业代码获取企业名称"""
    return MANUFACTURER_CODE_MAP.get(code, f"未知企业({code})")


def get_license_number(code: str) -> str:
    """根据企业代码获取许可证编号"""
    return MANUFACTURER_LICENSE_MAP.get(code, "未知许可证")


def get_package_name(pkg_byte: int) -> str:
    """根据包装方式编码获取包装名称"""
    return PACKAGE_MAP.get(pkg_byte, "箱装")
