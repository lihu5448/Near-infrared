import struct
import numpy as np
import os
import json
import argparse
import sys
from datetime import datetime
import re
import glob


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
            return None, None

        # 获取数据类型
        data_type = data_bytes[2]

        # 验证校验和
        checksum = sum(data_bytes[3:7]) & 0xFF
        if checksum != data_bytes[7]:
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

            # 步骤1: 将十六进制字符串转换为二进制数据
            binary_data = self.hex_string_to_binary(text_content)
            if binary_data is None:
                return False

            # 步骤2: 协议解析
            packets = self.parse_voltage_packets(binary_data)

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

            print(f"  有效数据包: {valid_packets}, 异常帧: {abnormal_packets}, 校验错误: {checksum_error_packets}")

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
                # 写入特征值
                for value in features:
                    f.write(f"{value:.6f}\n")
            return True

        except Exception as e:
            print(f"保存文件错误: {e}")
            return False


def load_config(config_file="config.json"):
    """加载配置文件"""
    default_config = {
        "input_folder": "D:/Desktop/sensor_data",
        "output_folder": "D:/Desktop/sensor_python/data_output"
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


def find_data_files(input_folder):
    """查找符合命名规则的数据文件"""
    # 匹配模式：数字.数字_数字.txt 或 数字.数字.txt
    pattern1 = r'(\d+\.\d+)_(\d+)\.txt'  # 匹配 14.86_1.txt 格式
    pattern2 = r'(\d+\.\d+)\.txt'  # 匹配 16.67.txt 格式

    data_files = []

    # 查找所有txt文件
    txt_files = glob.glob(os.path.join(input_folder, "*.txt"))

    for file_path in txt_files:
        filename = os.path.basename(file_path)

        # 跳过明显不是数据文件的文件
        if filename == "amaoComDataLogT.txt":
            continue

        match1 = re.match(pattern1, filename)  # 匹配 14.86_1.txt 格式
        match2 = re.match(pattern2, filename)  # 匹配 16.67.txt 格式

        if match1:
            humidity_level = float(match1.group(1))  # 湿度级别 (14.86)
            file_number = int(match1.group(2))  # 文件编号 (1)
            data_files.append((humidity_level, file_number, file_path, filename))

        elif match2:
            humidity_level = float(match2.group(1))  # 湿度级别 (16.67)
            file_number = 1  # 单文件默认为编号1
            data_files.append((humidity_level, file_number, file_path, filename))

    # 按湿度级别和文件编号排序
    data_files.sort(key=lambda x: (x[0], x[1]))

    return data_files


def process_batch_files(input_folder, output_folder):
    """批量处理文件，每个输入文件对应一个输出文件"""
    # 查找符合命名规则的文件
    data_files = find_data_files(input_folder)

    if not data_files:
        print("未找到符合命名规则的文件（格式：数字.数字_数字.txt 或 数字.数字.txt）")
        # 显示文件夹中实际的文件
        txt_files = glob.glob(os.path.join(input_folder, "*.txt"))
        if txt_files:
            print("文件夹中的文件:")
            for file in txt_files:
                print(f"  {os.path.basename(file)}")
        return False

    print(f"找到 {len(data_files)} 个数据文件")

    total_processed = 0

    # 确保输出文件夹存在
    os.makedirs(output_folder, exist_ok=True)

    # 处理每个文件
    for humidity_level, file_number, file_path, filename in data_files:
        print(f"\n{'=' * 50}")
        print(f"处理文件: {filename}")
        print(f"湿度值: {humidity_level}")
        print(f"{'=' * 50}")

        # 生成输出文件名（在原文件名基础上添加_特征）
        output_filename = os.path.splitext(filename)[0] + "_feature.txt"
        output_file = os.path.join(output_folder, output_filename)

        # 创建处理器，使用实际的湿度值
        processor = DataProcessor(humidity=humidity_level)

        # 处理数据
        if processor.process_txt_data(file_path):
            # 计算特征
            features = processor.calculate_features()

            if features is not None:
                # 保存特征
                if processor.save_features_to_txt(features, output_file):
                    total_processed += 1
                    print(f"✓ 成功处理")
                    print(f"输出文件: {output_filename}")
                else:
                    print(f"✗ 保存失败")
            else:
                print(f"✗ 特征计算失败")
        else:
            print(f"✗ 数据处理失败")

    print(f"\n{'=' * 50}")
    print(f"批量处理完成！")
    print(f"共成功处理 {total_processed}/{len(data_files)} 个文件")
    print(f"输出文件夹: {output_folder}")
    print(f"每个输入文件对应一个独立的输出文件")
    print(f"{'=' * 50}")

    return total_processed > 0


def main():
    parser = argparse.ArgumentParser(description='数据处理程序 - 提取光学特征')
    parser.add_argument('-if', '--input-folder', type=str, help='输入文件夹路径（批量处理）')
    parser.add_argument('-of', '--output-folder', type=str, help='输出文件夹路径')
    parser.add_argument('-c', '--config', type=str, default='config.json', help='配置文件路径')
    parser.add_argument('--create-config', action='store_true', help='创建默认配置文件')
    parser.add_argument('--batch', action='store_true', help='批量处理模式（默认模式）')

    args = parser.parse_args()

    # 如果指定创建配置文件
    if args.create_config:
        default_config = {
            "input_folder": "D:\\Desktop\\sensor_data",
            "output_folder": "D:\\Desktop\\sensor_python\\data_output"
        }
        save_config(default_config, args.config)
        print("默认配置文件已创建，请根据需要修改路径")
        return

    # 加载配置
    config = load_config(args.config)

    # 批量处理模式（现在作为主要模式）
    # 如果没有指定任何模式，默认使用批量处理
    if args.batch or not any([args.input_folder, args.output_folder]):
        # 确定输入文件夹 (优先级: 命令行参数 > 配置文件)
        if args.input_folder:
            input_folder = args.input_folder
        else:
            input_folder = config.get('input_folder')
            if not input_folder:
                print("请指定输入文件夹路径")
                print("使用方法: python script.py --input-folder <路径>")
                print("或修改配置文件中的 input_folder 设置")
                return

        # 确定输出文件夹 (优先级: 命令行参数 > 配置文件 > 默认)
        if args.output_folder:
            output_folder = args.output_folder
        else:
            output_folder = config.get('output_folder', './output_features')

        # 检查输入文件夹是否存在
        if not os.path.exists(input_folder):
            print(f"输入文件夹不存在: {input_folder}")
            return

        print(f"输入文件夹: {input_folder}")
        print(f"输出文件夹: {output_folder}")
        print(f"{'=' * 50}")

        # 批量处理
        process_batch_files(input_folder, output_folder)
        return

    # 单文件处理模式（保留但简化）
    print("单文件处理模式已简化，建议使用批量处理模式")
    print("使用方法: python script.py --batch --input-folder <输入文件夹> --output-folder <输出文件夹>")


if __name__ == "__main__":
    main()