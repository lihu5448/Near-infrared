import struct
import numpy as np
import os
import json
import argparse
import sys
from datetime import datetime


class DataProcessor:
    def __init__(self, humidity=0.0):
        self.humidity = humidity  # 湿度作为全局变量
        self.reference_data = []  # 存储参考光数据
        self.measurement_data = []  # 存储测量光数据

    def set_humidity(self, humidity):
        """设置湿度值"""
        self.humidity = humidity

    def hex_string_to_binary(self, hex_string):
        """将十六进制字符串转换为二进制数据"""
        try:
            # 移除空格、换行等空白字符
            hex_string = ''.join(hex_string.split())
            # 确保十六进制字符串长度为偶数
            if len(hex_string) % 2 != 0:
                print("警告: 十六进制字符串长度不是偶数")
                return None
            # 转换为二进制数据
            binary_data = bytes.fromhex(hex_string)
            return binary_data
        except Exception as e:
            print(f"十六进制转换错误: {e}")
            return None

    def parse_voltage_packets(self, binary_data):
        """解析电压数据包"""
        packets = []
        packet_size = 10  # 每个数据包10字节

        for i in range(0, len(binary_data), packet_size):
            if i + packet_size > len(binary_data):
                break

            packet = binary_data[i:i + packet_size]
            packets.append(packet)

        return packets

    def is_abnormal_frame(self, data_bytes):
        """判断是否为异常帧"""
        if len(data_bytes) < 7:
            return True

        # 检查数据部分是否为 00 00 00 00 或者 FF FF FF FF
        data_part = data_bytes[3:7]

        # 检查全0
        if data_part == b'\x00\x00\x00\x00':
            return True

        # 检查全1 (FF FF FF FF)
        if data_part == b'\xFF\xFF\xFF\xFF':
            return True

        return False

    def parse_serial_data(self, data_bytes):
        """解析串口数据"""
        if len(data_bytes) != 10:
            return None, None

        # 检查协议头
        if data_bytes[0] != 0x5A or data_bytes[1] != 0xA5:
            return None, None

        # 检查协议尾
        if data_bytes[8] != 0x0D:
            return None, None

        if data_bytes[9] != 0x0A:
            return None, None

        # 检查是否为异常帧
        if self.is_abnormal_frame(data_bytes):
            print("检测到异常帧，跳过处理")
            return None, None

        # 获取数据类型
        data_type = data_bytes[2]

        # 验证校验和
        checksum = sum(data_bytes[3:7]) & 0xFF
        if checksum != data_bytes[7]:
            print("校验和错误，跳过数据包")
            return None, None

        # 解析电压值 (小端序)
        voltage_bytes = bytes(data_bytes[3:7])
        voltage = struct.unpack('<I', voltage_bytes)[0] / 1000000.0

        return data_type, voltage

    def process_txt_data(self, file_path):
        """处理TXT格式的原始数据文件"""
        reference_voltages = []
        measurement_voltages = []

        try:
            # 读取TXT文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                text_content = f.read().strip()

            print(f"读取到 {len(text_content)} 个字符的十六进制数据")

            # 步骤1: 将十六进制字符串转换为二进制数据
            binary_data = self.hex_string_to_binary(text_content)
            if binary_data is None:
                return False
            print(f"转换为 {len(binary_data)} 字节的二进制数据")

            # 步骤2: 协议解析
            packets = self.parse_voltage_packets(binary_data)
            print(f"解析出 {len(packets)} 个数据包")

            # 处理每个数据包
            valid_packets = 0
            abnormal_packets = 0
            checksum_error_packets = 0

            for packet in packets:
                data_type, voltage = self.parse_serial_data(packet)

                if data_type is None and voltage is None:
                    # 异常帧或校验错误
                    if self.is_abnormal_frame(packet):
                        abnormal_packets += 1
                    else:
                        checksum_error_packets += 1
                    continue

                if data_type == 0x01:  # 测量光
                    measurement_voltages.append(voltage)
                    valid_packets += 1
                elif data_type == 0x02:  # 参考光
                    reference_voltages.append(voltage)
                    valid_packets += 1
                # 忽略数据类型为0x00的数据

            print(
                f"有效数据包: {valid_packets} (参考光: {len(reference_voltages)}, 测量光: {len(measurement_voltages)})")
            if abnormal_packets > 0:
                print(f"异常帧数据包: {abnormal_packets}")
            if checksum_error_packets > 0:
                print(f"校验错误数据包: {checksum_error_packets}")

        except Exception as e:
            print(f"处理TXT文件错误: {e}")
            return False

        self.reference_data = np.array(reference_voltages)
        self.measurement_data = np.array(measurement_voltages)

        return len(self.reference_data) > 0 and len(self.measurement_data) > 0

    def calculate_features(self):
        """计算所有特征"""
        if len(self.reference_data) == 0 or len(self.measurement_data) == 0:
            return None

        features = []

        # 1. 湿度 (使用设置的全局变量)
        features.append(self.humidity)

        # 2-3. 均值
        mean_ref = np.mean(self.reference_data)
        mean_meas = np.mean(self.measurement_data)
        features.extend([mean_ref, mean_meas])

        # 4-5. 标准差
        std_ref = np.std(self.reference_data)
        std_meas = np.std(self.measurement_data)
        features.extend([std_ref, std_meas])

        # 6-11. 分位数特征
        q25_ref = np.percentile(self.reference_data, 25)
        median_ref = np.median(self.reference_data)
        q75_ref = np.percentile(self.reference_data, 75)

        q25_meas = np.percentile(self.measurement_data, 25)
        median_meas = np.median(self.measurement_data)
        q75_meas = np.percentile(self.measurement_data, 75)

        features.extend([q25_ref, median_ref, q75_ref, q25_meas, median_meas, q75_meas])

        # 11. 稳健比值 (注意: 这里假设1450nm和1300nm对应测量光和参考光)
        robust_ratio = median_meas / median_ref if median_ref != 0 else 0
        features.append(robust_ratio)

        # 12. 信号质量指数
        signal_quality_ref = mean_ref / std_ref if std_ref != 0 else 0
        signal_quality_meas = mean_meas / std_meas if std_meas != 0 else 0
        signal_quality = (signal_quality_ref + signal_quality_meas) / 2
        features.append(signal_quality)

        # 13-14. 范围
        range_ref = np.max(self.reference_data) - np.min(self.reference_data)
        range_meas = np.max(self.measurement_data) - np.min(self.measurement_data)
        features.extend([range_ref, range_meas])

        # 15-16. 差值特征和归一化差值
        diff_mean = mean_ref - mean_meas
        norm_diff = diff_mean / (mean_ref + mean_meas) if (mean_ref + mean_meas) != 0 else 0
        features.extend([diff_mean, norm_diff])

        # 17. 反射率比值
        reflectance_ratio = mean_meas / mean_ref if mean_ref != 0 else 0
        features.append(reflectance_ratio)

        # 18. 表面均匀性指数
        surface_uniformity = 1 - (abs(std_ref - std_meas) / (std_ref + std_meas)) if (std_ref + std_meas) != 0 else 0
        features.append(surface_uniformity)

        # 19. 吸收对比度
        absorption_contrast = diff_mean / mean_ref if mean_ref != 0 else 0
        features.append(absorption_contrast)

        return features

    def save_features_to_txt(self, features, output_path):
        """保存特征到TXT文件"""
        if features is None:
            print("没有特征数据可保存")
            return False

        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                # 写入特征名称
                feature_names = [
                    "湿度",
                    "mean_refer",
                    "mean_measure",
                    "std_refer",
                    "std_measure",
                    "q25_refer",
                    "median_refer",
                    "q75_refer",
                    "q25_measure",
                    "median_measure",
                    "q75_measure",
                    "robust_ratio",
                    "signal_quality",
                    "range_refer",
                    "range_measure",
                    "mean_diff",
                    "norm_diff",
                    "reflectance_ratio",
                    "surface_uniformity",
                    "absorption_contrast"
                ]

                # 写入特征值 --》将数据写入TXT
                for i, (name, value) in enumerate(zip(feature_names, features)):
                    # f.write(f"{i + 1}. {name}: {value:.6f}\n")
                    f.write(f"{value:.6f}\n")

            print(f"特征已保存到: {output_path}")
            return True

        except Exception as e:
            print(f"保存文件错误: {e}")
            return False


def load_config(config_file="config.json"):
    """加载配置文件"""
    default_config = {
        "input_file": "./input/data.txt",
        "output_folder": "./output_features",
        "default_humidity": 0.0,
        "output_filename": "output_features.txt"
    }

    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                # 合并配置，用户配置覆盖默认配置
                default_config.update(user_config)
            print(f"已加载配置文件: {config_file}")
        except Exception as e:
            print(f"配置文件加载失败，使用默认配置: {e}")

    return default_config


def save_config(config, config_file="config.json"):
    """保存配置文件"""
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        print(f"配置文件已保存: {config_file}")
    except Exception as e:
        print(f"保存配置文件失败: {e}")


def generate_output_filename(output_folder, output_filename):
    """生成输出文件路径"""
    return os.path.join(output_folder, output_filename)


def main():
    parser = argparse.ArgumentParser(description='数据处理程序 - 提取光学特征')
    parser.add_argument('humidity', type=float, nargs='?', help='湿度值')
    parser.add_argument('-i', '--input', type=str, help='输入TXT文件路径')
    parser.add_argument('-o', '--output-folder', type=str, help='输出文件夹路径')
    parser.add_argument('-of', '--output-filename', type=str, help='输出文件名')
    parser.add_argument('-c', '--config', type=str, default='config.json', help='配置文件路径')
    parser.add_argument('--create-config', action='store_true', help='创建默认配置文件')

    args = parser.parse_args()

    # 如果指定创建配置文件
    if args.create_config:
        default_config = {
            "input_file": "D:\\Desktop\\sensor_data\\amaoComDataLog12.86",
            "output_folder": "D:\\Desktop\\sensor_python\\data_output",
            "default_humidity": 12.86,
            "output_filename": "sensor_features.txt"
        }
        save_config(default_config, args.config)
        print("默认配置文件已创建，请根据需要修改路径和文件名")
        return

    # 加载配置
    config = load_config(args.config)

    # 确定湿度值 (优先级: 命令行参数 > 配置文件 > 交互输入)
    if args.humidity is not None:
        humidity = args.humidity
    else:
        humidity = config.get('default_humidity', 0.0)

    # 确定输入文件路径 (优先级: 命令行参数 > 配置文件)
    if args.input:
        input_file = args.input
    else:
        input_file = config.get('input_file')
        if not input_file:
            input_file = input("请输入原始数据TXT文件路径: ").strip()

    # 确定输出文件夹 (优先级: 命令行参数 > 配置文件 > 默认)
    if args.output_folder:
        output_folder = args.output_folder
    else:
        output_folder = config.get('output_folder', './output_features')

    # 确定输出文件名 (优先级: 命令行参数 > 配置文件 > 默认)
    if args.output_filename:
        output_filename = args.output_filename
    else:
        output_filename = config.get('output_filename', 'output_features.txt')

    # 生成输出文件路径
    output_file = generate_output_filename(output_folder, output_filename)

    # 创建处理器并设置湿度
    processor = DataProcessor(humidity=humidity)

    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        print(f"输入文件不存在: {input_file}")
        return

    # 处理原始数据
    print(f"正在处理TXT文件: {input_file}")
    print(f"使用湿度值: {humidity}")
    print(f"输出文件夹: {output_folder}")
    print(f"输出文件: {output_file}")

    # 使用新的TXT文件处理方法
    if not processor.process_txt_data(input_file):
        print("数据处理失败!")
        return

    # 计算特征
    print("正在计算特征...")
    features = processor.calculate_features()

    if features is None:
        print("特征计算失败!")
        return

    # 保存特征
    if processor.save_features_to_txt(features, output_file):
        print("处理完成!")

        # 显示特征摘要
        print("\n特征摘要:")
        feature_names = [
            "湿度", "mean_refer", "mean_measure", "std_refer", "std_measure",
            "q25_refer", "median_refer", "q75_refer", "q25_measure",
            "median_measure", "q75_measure", "robust_ratio", "signal_quality",
            "range_refer", "range_measure", "mean_diff", "norm_diff",
            "reflectance_ratio", "surface_uniformity", "absorption_contrast"
        ]

        for name, value in zip(feature_names, features):
            print(f"{name}: {value:.6f}")

if __name__ == "__main__":
    main()