import struct
import numpy as np
import os
import json
import argparse
import sys
from datetime import datetime
import re
import glob


class KalmanFilter1D:
    """
    一维卡尔曼滤波器
    用于对电压序列进行平滑，提高稳定性
    状态模型:
        x_k = x_(k-1) + w_k
        z_k = x_k + v_k
    """

    def __init__(self, process_variance=1e-7, measurement_variance=1e-5,
                 initial_estimate=0.0, initial_error=1.0):
        # 过程噪声方差 Q
        self.Q = process_variance
        # 测量噪声方差 R
        self.R = measurement_variance

        # 当前状态估计
        self.x = initial_estimate
        # 当前误差协方差
        self.P = initial_error

        # 是否已初始化
        self.initialized = False

    def reset(self):
        """重置滤波器状态"""
        self.x = 0.0
        self.P = 1.0
        self.initialized = False

    def update(self, measurement):
        """
        输入一个观测值，输出滤波后的估计值
        """
        if not self.initialized:
            self.x = measurement
            self.P = 1.0
            self.initialized = True
            return self.x

        # 1. 预测
        x_pred = self.x
        P_pred = self.P + self.Q

        # 2. 更新
        K = P_pred / (P_pred + self.R)  # 卡尔曼增益
        self.x = x_pred + K * (measurement - x_pred)
        self.P = (1 - K) * P_pred

        return self.x


class DataProcessor:
    def __init__(self, humidity=0.0, process_variance=1e-7, measurement_variance=1e-5):
        self.humidity = humidity  # 湿度作为全局变量
        self.reference_data = []  # 存储参考光数据
        self.measurement_data = []  # 存储测量光数据

        # 原始数据（可选保存，便于调试）
        self.raw_reference_data = []
        self.raw_measurement_data = []

        # 分别为参考光和测量光配置卡尔曼滤波器
        self.ref_kf = KalmanFilter1D(
            process_variance=process_variance,
            measurement_variance=measurement_variance,
            initial_estimate=0.0,
            initial_error=1.0
        )
        self.meas_kf = KalmanFilter1D(
            process_variance=process_variance,
            measurement_variance=measurement_variance,
            initial_estimate=0.0,
            initial_error=1.0
        )

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
        """解析电压数据包，每包10字节"""
        packets = []
        packet_size = 10

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

        # 数据部分为 data_bytes[3:7]
        data_part = data_bytes[3:7]

        # 全0
        if data_part == b'\x00\x00\x00\x00':
            return True

        # 全FF
        if data_part == b'\xFF\xFF\xFF\xFF':
            return True

        return False

    def parse_serial_data(self, data_bytes):
        """解析串口数据"""
        if len(data_bytes) != 10:
            return None, None

        # 协议头
        if data_bytes[0] != 0x5A or data_bytes[1] != 0xA5:
            return None, None

        # 协议尾
        if data_bytes[8] != 0x0D:
            return None, None
        if data_bytes[9] != 0x0A:
            return None, None

        # 异常帧过滤
        if self.is_abnormal_frame(data_bytes):
            return None, None

        # 数据类型
        data_type = data_bytes[2]

        # 校验和验证
        checksum = sum(data_bytes[3:7]) & 0xFF
        if checksum != data_bytes[7]:
            return None, None

        # 小端序解析电压
        voltage_bytes = bytes(data_bytes[3:7])
        voltage = struct.unpack('<I', voltage_bytes)[0] / 1000000.0

        return data_type, voltage

    def process_txt_data(self, file_path):
        """处理TXT格式原始数据文件，并在解算后进行卡尔曼滤波"""
        reference_voltages = []
        measurement_voltages = []
        raw_reference_voltages = []
        raw_measurement_voltages = []

        # 每个文件处理前重置滤波器，避免跨文件串扰
        self.ref_kf.reset()
        self.meas_kf.reset()

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text_content = f.read().strip()

            # 十六进制转二进制
            binary_data = self.hex_string_to_binary(text_content)
            if binary_data is None:
                return False

            # 分包
            packets = self.parse_voltage_packets(binary_data)

            valid_packets = 0
            abnormal_packets = 0
            checksum_error_packets = 0

            for packet in packets:
                data_type, voltage = self.parse_serial_data(packet)

                if data_type is None and voltage is None:
                    if self.is_abnormal_frame(packet):
                        abnormal_packets += 1
                    else:
                        checksum_error_packets += 1
                    continue

                if data_type == 0x01:  # 测量光
                    raw_measurement_voltages.append(voltage)
                    filtered_voltage = self.meas_kf.update(voltage)
                    measurement_voltages.append(filtered_voltage)
                    valid_packets += 1

                elif data_type == 0x02:  # 参考光
                    raw_reference_voltages.append(voltage)
                    filtered_voltage = self.ref_kf.update(voltage)
                    reference_voltages.append(filtered_voltage)
                    valid_packets += 1

            print(f"  有效数据包: {valid_packets}, 异常帧: {abnormal_packets}, 校验错误: {checksum_error_packets}")
            print(f"  参考光点数: {len(reference_voltages)}, 测量光点数: {len(measurement_voltages)}")

        except Exception as e:
            print(f"处理TXT文件错误: {e}")
            return False

        self.raw_reference_data = np.array(raw_reference_voltages, dtype=float)
        self.raw_measurement_data = np.array(raw_measurement_voltages, dtype=float)
        self.reference_data = np.array(reference_voltages, dtype=float)
        self.measurement_data = np.array(measurement_voltages, dtype=float)

        return len(self.reference_data) > 0 and len(self.measurement_data) > 0

    def calculate_features(self):
        """计算所有特征"""
        if len(self.reference_data) == 0 or len(self.measurement_data) == 0:
            return None

        features = []

        # 1. 湿度
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

        features.extend([
            q25_ref, median_ref, q75_ref,
            q25_meas, median_meas, q75_meas
        ])

        # 12. 稳健比值
        robust_ratio = median_meas / median_ref if median_ref != 0 else 0
        features.append(robust_ratio)

        # 13. 信号质量指数
        signal_quality_ref = mean_ref / std_ref if std_ref != 0 else 0
        signal_quality_meas = mean_meas / std_meas if std_meas != 0 else 0
        signal_quality = (signal_quality_ref + signal_quality_meas) / 2
        features.append(signal_quality)

        # 14-15. 范围
        range_ref = np.max(self.reference_data) - np.min(self.reference_data)
        range_meas = np.max(self.measurement_data) - np.min(self.measurement_data)
        features.extend([range_ref, range_meas])

        # 16-17. 差值特征和归一化差值
        diff_mean = mean_ref - mean_meas
        norm_diff = diff_mean / (mean_ref + mean_meas) if (mean_ref + mean_meas) != 0 else 0
        features.extend([diff_mean, norm_diff])

        # 18. 反射率比值
        reflectance_ratio = mean_meas / mean_ref if mean_ref != 0 else 0
        features.append(reflectance_ratio)

        # 19. 表面均匀性指数
        surface_uniformity = 1 - (abs(std_ref - std_meas) / (std_ref + std_meas)) if (std_ref + std_meas) != 0 else 0
        features.append(surface_uniformity)

        # 20. 吸收对比度
        absorption_contrast = diff_mean / mean_ref if mean_ref != 0 else 0
        features.append(absorption_contrast)

        return features

    def save_features_to_txt(self, features, output_path):
        """保存特征到TXT文件"""
        if features is None:
            print("没有特征数据可保存")
            return False

        try:
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                for value in features:
                    f.write(f"{value:.6f}\n")
            return True

        except Exception as e:
            print(f"保存文件错误: {e}")
            return False

    def save_filtered_series(self, output_path):
        """
        可选：保存滤波后的参考光/测量光序列，便于分析稳定性
        """
        try:
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            max_len = max(len(self.reference_data), len(self.measurement_data),
                          len(self.raw_reference_data), len(self.raw_measurement_data))

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("index,raw_reference,filtered_reference,raw_measurement,filtered_measurement\n")
                for i in range(max_len):
                    raw_ref = self.raw_reference_data[i] if i < len(self.raw_reference_data) else ""
                    fil_ref = self.reference_data[i] if i < len(self.reference_data) else ""
                    raw_meas = self.raw_measurement_data[i] if i < len(self.raw_measurement_data) else ""
                    fil_meas = self.measurement_data[i] if i < len(self.measurement_data) else ""
                    f.write(f"{i},{raw_ref},{fil_ref},{raw_meas},{fil_meas}\n")
            return True

        except Exception as e:
            print(f"保存滤波序列错误: {e}")
            return False


def load_config(config_file="config.json"):
    """加载配置文件"""
    default_config = {
        "input_folder": "D:/Desktop/sensor_data",
        "output_folder": "D:/Desktop/sensor_python/data_output",
        "process_variance": 1e-7,
        "measurement_variance": 1e-5,
        "save_filtered_series": False
    }

    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
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
    pattern1 = r'(\d+\.\d+)_(\d+)\.txt$'   # 14.86_1.txt
    pattern2 = r'(\d+\.\d+)\.txt$'         # 16.67.txt

    data_files = []
    txt_files = glob.glob(os.path.join(input_folder, "*.txt"))

    for file_path in txt_files:
        filename = os.path.basename(file_path)

        # 跳过非数据文件
        if filename == "amaoComDataLogT.txt":
            continue
        if filename.endswith("_feature.txt"):
            continue
        if filename.endswith("_series.csv"):
            continue

        match1 = re.match(pattern1, filename)
        match2 = re.match(pattern2, filename)

        if match1:
            humidity_level = float(match1.group(1))
            file_number = int(match1.group(2))
            data_files.append((humidity_level, file_number, file_path, filename))
        elif match2:
            humidity_level = float(match2.group(1))
            file_number = 1
            data_files.append((humidity_level, file_number, file_path, filename))

    data_files.sort(key=lambda x: (x[0], x[1]))
    return data_files


def process_batch_files(input_folder, output_folder,
                        process_variance=1e-7,
                        measurement_variance=1e-5,
                        save_filtered_series=False):
    """批量处理文件，每个输入文件对应一个输出文件"""
    data_files = find_data_files(input_folder)

    if not data_files:
        print("未找到符合命名规则的文件（格式：数字.数字_数字.txt 或 数字.数字.txt）")
        txt_files = glob.glob(os.path.join(input_folder, "*.txt"))
        if txt_files:
            print("文件夹中的文件:")
            for file in txt_files:
                print(f"  {os.path.basename(file)}")
        return False

    print(f"找到 {len(data_files)} 个数据文件")
    print(f"卡尔曼滤波参数: Q={process_variance}, R={measurement_variance}")

    total_processed = 0
    os.makedirs(output_folder, exist_ok=True)

    for humidity_level, file_number, file_path, filename in data_files:
        print(f"\n{'=' * 50}")
        print(f"处理文件: {filename}")
        print(f"湿度值: {humidity_level}")
        print(f"{'=' * 50}")

        output_filename = os.path.splitext(filename)[0] + "_feature.txt"
        output_file = os.path.join(output_folder, output_filename)

        processor = DataProcessor(
            humidity=humidity_level,
            process_variance=process_variance,
            measurement_variance=measurement_variance
        )

        if processor.process_txt_data(file_path):
            features = processor.calculate_features()

            if features is not None:
                if processor.save_features_to_txt(features, output_file):
                    total_processed += 1
                    print("✓ 成功处理")
                    print(f"输出特征文件: {output_filename}")

                    if save_filtered_series:
                        series_filename = os.path.splitext(filename)[0] + "_series.csv"
                        series_file = os.path.join(output_folder, series_filename)
                        if processor.save_filtered_series(series_file):
                            print(f"输出滤波序列文件: {series_filename}")
                else:
                    print("✗ 保存失败")
            else:
                print("✗ 特征计算失败")
        else:
            print("✗ 数据处理失败")

    print(f"\n{'=' * 50}")
    print("批量处理完成！")
    print(f"共成功处理 {total_processed}/{len(data_files)} 个文件")
    print(f"输出文件夹: {output_folder}")
    print("每个输入文件对应一个独立的输出文件")
    print(f"{'=' * 50}")

    return total_processed > 0


def main():
    parser = argparse.ArgumentParser(description='数据处理程序 - 提取光学特征 + 卡尔曼滤波')
    parser.add_argument('-if', '--input-folder', type=str, help='输入文件夹路径（批量处理）')
    parser.add_argument('-of', '--output-folder', type=str, help='输出文件夹路径')
    parser.add_argument('-c', '--config', type=str, default='config.json', help='配置文件路径')
    parser.add_argument('--create-config', action='store_true', help='创建默认配置文件')
    parser.add_argument('--batch', action='store_true', help='批量处理模式（默认模式）')

    # 新增卡尔曼滤波参数
    parser.add_argument('--q', type=float, help='卡尔曼滤波过程噪声方差 Q')
    parser.add_argument('--r', type=float, help='卡尔曼滤波测量噪声方差 R')
    parser.add_argument('--save-series', action='store_true', help='保存滤波前后序列对比文件')

    args = parser.parse_args()

    if args.create_config:
        default_config = {
            "input_folder": "D:\\Desktop\\sensor_data",
            "output_folder": "D:\\Desktop\\sensor_python\\data_output",
            "process_variance": 1e-7,
            "measurement_variance": 1e-5,
            "save_filtered_series": False
        }
        save_config(default_config, args.config)
        print("默认配置文件已创建，请根据需要修改路径和滤波参数")
        return

    config = load_config(args.config)

    if args.batch or not any([args.input_folder, args.output_folder]):
        # 输入目录
        if args.input_folder:
            input_folder = args.input_folder
        else:
            input_folder = config.get('input_folder')
            if not input_folder:
                print("请指定输入文件夹路径")
                print("使用方法: python script.py --input-folder <路径>")
                print("或修改配置文件中的 input_folder 设置")
                return

        # 输出目录
        if args.output_folder:
            output_folder = args.output_folder
        else:
            output_folder = config.get('output_folder', './output_features')

        # 滤波参数
        process_variance = args.q if args.q is not None else config.get('process_variance', 1e-7)
        measurement_variance = args.r if args.r is not None else config.get('measurement_variance', 1e-5)

        # 是否保存序列
        save_filtered_series = args.save_series or config.get('save_filtered_series', False)

        if not os.path.exists(input_folder):
            print(f"输入文件夹不存在: {input_folder}")
            return

        print(f"输入文件夹: {input_folder}")
        print(f"输出文件夹: {output_folder}")
        print(f"过程噪声方差 Q: {process_variance}")
        print(f"测量噪声方差 R: {measurement_variance}")
        print(f"保存滤波序列: {save_filtered_series}")
        print(f"{'=' * 50}")

        process_batch_files(
            input_folder=input_folder,
            output_folder=output_folder,
            process_variance=process_variance,
            measurement_variance=measurement_variance,
            save_filtered_series=save_filtered_series
        )
        return

    print("单文件处理模式已简化，建议使用批量处理模式")
    print("使用方法: python script.py --batch --input-folder <输入文件夹> --output-folder <输出文件夹>")


if __name__ == "__main__":
    main()
