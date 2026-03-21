import struct
import numpy as np
import os
import re
import glob
import pywt
import matplotlib.pyplot as plt
from collections import defaultdict


# =========================================================
# 全局配置区：直接修改这里即可
# =========================================================

# 输入/输出目录
INPUT_FOLDER = r"D:\Desktop\sensor_data"
OUTPUT_FOLDER = r"D:\Desktop\sensor_python\data_output"

# 是否保存处理链各阶段序列到 CSV
SAVE_PROCESSING_SERIES = False

# -------------------------
# 处理流程标志位
# -------------------------
ENABLE_OUTLIER_SUPPRESSION = False   # 是否启用异常值抑制
ENABLE_KALMAN_FILTER = False         # 是否启用卡尔曼滤波
ENABLE_WAVELET_DENOISE = False       # 是否启用小波去噪

# -------------------------
# 绘图标志位
# -------------------------
ENABLE_PLOT_DISTRIBUTION = False     # 是否绘制湿度-平均电压分布图
PLOT_USE_FINAL_SIGNAL = False        # True: 用最终处理后数据求均值; False: 用原始数据求均值
PLOT_JITTER = False                  # 是否给同一湿度下的点增加轻微横向抖动
PLOT_JITTER_SCALE = 0.005           # 抖动强度

# -------------------------
# 卡尔曼滤波参数
# -------------------------
PROCESS_VARIANCE = 1e-7       # Q: 过程噪声方差，越小越平滑
MEASUREMENT_VARIANCE = 1e-5   # R: 测量噪声方差，越大越平滑

# -------------------------
# 异常值抑制参数
# -------------------------
OUTLIER_WINDOW = 5            # 滑动窗口大小，建议奇数
OUTLIER_SIGMA = 3.0           # 超过局部均值 ± sigma*std 判为异常点

# -------------------------
# 小波去噪参数
# -------------------------
WAVELET_NAME = 'db4'          # 可选: db4 / sym4 / coif3
WAVELET_LEVEL = 3             # 小波分解层数
THRESHOLD_SCALE = 2.0         # 阈值缩放系数，越大去噪越强

# -------------------------
# 文件过滤参数
# -------------------------
SKIP_FILES = {"amaoComDataLogT.txt"}   # 跳过的文件名集合


class KalmanFilter1D:
    """
    一维卡尔曼滤波器
    模型:
        x_k = x_(k-1) + w_k
        z_k = x_k + v_k
    """

    def __init__(self, process_variance=1e-7, measurement_variance=1e-5,
                 initial_estimate=0.0, initial_error=1.0):
        self.Q = process_variance
        self.R = measurement_variance
        self.x = initial_estimate
        self.P = initial_error
        self.initialized = False

    def reset(self):
        self.x = 0.0
        self.P = 1.0
        self.initialized = False

    def update(self, measurement):
        if not self.initialized:
            self.x = measurement
            self.P = 1.0
            self.initialized = True
            return self.x

        x_pred = self.x
        P_pred = self.P + self.Q

        K = P_pred / (P_pred + self.R)
        self.x = x_pred + K * (measurement - x_pred)
        self.P = (1 - K) * P_pred

        return self.x


class DataProcessor:
    def __init__(self, humidity=0.0):
        self.humidity = humidity

        # 最终输出数据
        self.reference_data = []
        self.measurement_data = []

        # 中间过程数据
        self.raw_reference_data = []
        self.raw_measurement_data = []

        self.outlier_reference_data = []
        self.outlier_measurement_data = []

        self.kalman_reference_data = []
        self.kalman_measurement_data = []

        # 初始化卡尔曼滤波器
        self.ref_kf = KalmanFilter1D(
            process_variance=PROCESS_VARIANCE,
            measurement_variance=MEASUREMENT_VARIANCE
        )
        self.meas_kf = KalmanFilter1D(
            process_variance=PROCESS_VARIANCE,
            measurement_variance=MEASUREMENT_VARIANCE
        )

    def hex_string_to_binary(self, hex_string):
        """将十六进制字符串转换为二进制数据"""
        try:
            hex_string = ''.join(hex_string.split())

            if len(hex_string) % 2 != 0:
                print("警告: 十六进制字符串长度不是偶数")
                return None

            return bytes.fromhex(hex_string)

        except Exception as e:
            print(f"十六进制转换错误: {e}")
            return None

    def parse_voltage_packets(self, binary_data):
        """按 10 字节分包"""
        packets = []
        packet_size = 10

        for i in range(0, len(binary_data), packet_size):
            if i + packet_size > len(binary_data):
                break
            packets.append(binary_data[i:i + packet_size])

        return packets

    def is_abnormal_frame(self, data_bytes):
        """判断协议层异常帧"""
        if len(data_bytes) < 7:
            return True

        data_part = data_bytes[3:7]

        if data_part == b'\x00\x00\x00\x00':
            return True

        if data_part == b'\xFF\xFF\xFF\xFF':
            return True

        return False

    def parse_serial_data(self, data_bytes):
        """解析串口协议数据"""
        if len(data_bytes) != 10:
            return None, None

        # 协议头
        if data_bytes[0] != 0x5A or data_bytes[1] != 0xA5:
            return None, None

        # 协议尾
        if data_bytes[8] != 0x0D or data_bytes[9] != 0x0A:
            return None, None

        # 异常帧
        if self.is_abnormal_frame(data_bytes):
            return None, None

        data_type = data_bytes[2]

        # 校验和
        checksum = sum(data_bytes[3:7]) & 0xFF
        if checksum != data_bytes[7]:
            return None, None

        # 小端序解析电压值
        voltage_bytes = bytes(data_bytes[3:7])
        voltage = struct.unpack('<I', voltage_bytes)[0] / 1000000.0

        return data_type, voltage

    def suppress_outliers(self, signal):
        """
        异常值抑制:
        若当前点偏离局部窗口均值超过 OUTLIER_SIGMA * std，
        则用局部均值替代
        """
        signal = np.asarray(signal, dtype=float)

        if len(signal) < OUTLIER_WINDOW + 2:
            return signal.copy()

        filtered = signal.copy()
        half_w = max(1, OUTLIER_WINDOW // 2)

        for i in range(len(signal)):
            left = max(0, i - half_w)
            right = min(len(signal), i + half_w + 1)

            window_data = np.concatenate([signal[left:i], signal[i + 1:right]])
            if len(window_data) < 2:
                continue

            local_mean = np.mean(window_data)
            local_std = np.std(window_data)

            if local_std == 0:
                continue

            if abs(signal[i] - local_mean) > OUTLIER_SIGMA * local_std:
                filtered[i] = local_mean

        return filtered

    def apply_kalman_filter(self, signal, kf):
        """对一维信号序列应用卡尔曼滤波"""
        signal = np.asarray(signal, dtype=float)
        if len(signal) == 0:
            return signal.copy()

        kf.reset()
        filtered = []

        for value in signal:
            filtered.append(kf.update(value))

        return np.array(filtered, dtype=float)

    def wavelet_denoise(self, signal):
        """小波去噪"""
        try:
            signal = np.asarray(signal, dtype=float)

            if len(signal) < 4:
                return signal.copy()

            wavelet_obj = pywt.Wavelet(WAVELET_NAME)
            max_level = pywt.dwt_max_level(len(signal), wavelet_obj.dec_len)
            level = min(WAVELET_LEVEL, max_level)

            if level < 1:
                return signal.copy()

            coeffs = pywt.wavedec(signal, WAVELET_NAME, level=level)

            detail_coeffs = coeffs[-1]
            if len(detail_coeffs) == 0:
                return signal.copy()

            sigma = np.median(np.abs(detail_coeffs)) / 0.6745
            threshold = THRESHOLD_SCALE * sigma * np.sqrt(2 * np.log(len(signal)))

            new_coeffs = [coeffs[0]]
            for c in coeffs[1:]:
                new_coeffs.append(pywt.threshold(c, threshold, mode='soft'))

            denoised = pywt.waverec(new_coeffs, WAVELET_NAME)
            denoised = denoised[:len(signal)]

            return np.array(denoised, dtype=float)

        except Exception as e:
            print(f"小波去噪错误: {e}")
            return signal.copy()

    def process_signal_pipeline(self, raw_signal, signal_type="signal"):
        """
        单路信号处理流程:
        原始 -> [异常值抑制] -> [卡尔曼滤波] -> [小波去噪]
        通过全局标志位决定是否启用各步骤
        """
        raw_signal = np.asarray(raw_signal, dtype=float)

        if len(raw_signal) == 0:
            return raw_signal.copy(), raw_signal.copy(), raw_signal.copy()

        current_signal = raw_signal.copy()

        # 1. 异常值抑制
        if ENABLE_OUTLIER_SUPPRESSION:
            outlier_suppressed = self.suppress_outliers(current_signal)
        else:
            outlier_suppressed = current_signal.copy()

        current_signal = outlier_suppressed.copy()

        # 2. 卡尔曼滤波
        if ENABLE_KALMAN_FILTER:
            if signal_type == "reference":
                kalman_filtered = self.apply_kalman_filter(current_signal, self.ref_kf)
            else:
                kalman_filtered = self.apply_kalman_filter(current_signal, self.meas_kf)
        else:
            kalman_filtered = current_signal.copy()

        current_signal = kalman_filtered.copy()

        # 3. 小波去噪
        if ENABLE_WAVELET_DENOISE:
            final_signal = self.wavelet_denoise(current_signal)
        else:
            final_signal = current_signal.copy()

        return outlier_suppressed, kalman_filtered, final_signal

    def process_txt_data(self, file_path):
        """处理单个 TXT 原始数据文件"""
        reference_voltages = []
        measurement_voltages = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text_content = f.read().strip()

            binary_data = self.hex_string_to_binary(text_content)
            if binary_data is None:
                return False

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
                    measurement_voltages.append(voltage)
                    valid_packets += 1

                elif data_type == 0x02:  # 参考光
                    reference_voltages.append(voltage)
                    valid_packets += 1

            print(f"  有效数据包: {valid_packets}, 异常帧: {abnormal_packets}, 校验错误: {checksum_error_packets}")
            print(f"  原始参考光点数: {len(reference_voltages)}, 原始测量光点数: {len(measurement_voltages)}")

        except Exception as e:
            print(f"处理TXT文件错误: {e}")
            return False

        self.raw_reference_data = np.array(reference_voltages, dtype=float)
        self.raw_measurement_data = np.array(measurement_voltages, dtype=float)

        if len(self.raw_reference_data) == 0 or len(self.raw_measurement_data) == 0:
            return False

        # 参考光处理
        ref_outlier, ref_kalman, ref_final = self.process_signal_pipeline(
            self.raw_reference_data, signal_type="reference"
        )

        # 测量光处理
        meas_outlier, meas_kalman, meas_final = self.process_signal_pipeline(
            self.raw_measurement_data, signal_type="measurement"
        )

        self.outlier_reference_data = ref_outlier
        self.outlier_measurement_data = meas_outlier

        self.kalman_reference_data = ref_kalman
        self.kalman_measurement_data = meas_kalman

        self.reference_data = ref_final
        self.measurement_data = meas_final

        print(f"  最终参考光点数: {len(self.reference_data)}, 最终测量光点数: {len(self.measurement_data)}")

        return len(self.reference_data) > 0 and len(self.measurement_data) > 0

    def calculate_features(self):
        """基于最终稳定序列计算特征"""
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

        # 16-17. 差值与归一化差值
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
        """保存特征到 TXT 文件"""
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
            print(f"保存特征文件错误: {e}")
            return False

    def save_processing_series(self, output_path):
        """保存处理链各阶段序列到 CSV"""
        try:
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            max_len = max(
                len(self.raw_reference_data),
                len(self.outlier_reference_data),
                len(self.kalman_reference_data),
                len(self.reference_data),
                len(self.raw_measurement_data),
                len(self.outlier_measurement_data),
                len(self.kalman_measurement_data),
                len(self.measurement_data)
            )

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(
                    "index,"
                    "raw_reference,outlier_reference,kalman_reference,final_reference,"
                    "raw_measurement,outlier_measurement,kalman_measurement,final_measurement\n"
                )

                for i in range(max_len):
                    raw_ref = self.raw_reference_data[i] if i < len(self.raw_reference_data) else ""
                    out_ref = self.outlier_reference_data[i] if i < len(self.outlier_reference_data) else ""
                    kal_ref = self.kalman_reference_data[i] if i < len(self.kalman_reference_data) else ""
                    fin_ref = self.reference_data[i] if i < len(self.reference_data) else ""

                    raw_meas = self.raw_measurement_data[i] if i < len(self.raw_measurement_data) else ""
                    out_meas = self.outlier_measurement_data[i] if i < len(self.outlier_measurement_data) else ""
                    kal_meas = self.kalman_measurement_data[i] if i < len(self.kalman_measurement_data) else ""
                    fin_meas = self.measurement_data[i] if i < len(self.measurement_data) else ""

                    f.write(
                        f"{i},"
                        f"{raw_ref},{out_ref},{kal_ref},{fin_ref},"
                        f"{raw_meas},{out_meas},{kal_meas},{fin_meas}\n"
                    )

            return True

        except Exception as e:
            print(f"保存处理链序列错误: {e}")
            return False


def find_data_files(input_folder):
    """
    查找符合命名规则的数据文件
    支持:
    - 14.86_1.txt
    - 16.67.txt
    """
    pattern1 = r'(\d+\.\d+)_(\d+)\.txt$'
    pattern2 = r'(\d+\.\d+)\.txt$'

    data_files = []
    txt_files = glob.glob(os.path.join(input_folder, "*.txt"))

    for file_path in txt_files:
        filename = os.path.basename(file_path)

        if filename in SKIP_FILES:
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


def plot_mean_voltage_distribution(humidity_ref_dict, humidity_meas_dict, output_folder):
    """
    绘制每个湿度下“每个文件平均电压”的散点分布图
    横坐标：湿度
    纵坐标：平均电压
    蓝色：参考光平均电压
    红色：测量光平均电压
    """
    humidities = sorted(set(list(humidity_ref_dict.keys()) + list(humidity_meas_dict.keys())))
    if not humidities:
        print("没有可用于绘图的数据")
        return

    plt.figure(figsize=(14, 7))

    first_ref = True
    first_meas = True

    for h in humidities:
        ref_means = humidity_ref_dict[h]
        meas_means = humidity_meas_dict[h]

        # 参考光点，略向左偏移
        if len(ref_means) > 0:
            if PLOT_JITTER:
                x_ref = np.random.normal(loc=h - 0.03, scale=PLOT_JITTER_SCALE, size=len(ref_means))
            else:
                x_ref = np.full(len(ref_means), h - 0.03)

            plt.scatter(
                x_ref, ref_means,
                s=40, alpha=0.8, color='blue',
                label='参考光平均电压' if first_ref else ""
            )
            first_ref = False

        # 测量光点，略向右偏移
        if len(meas_means) > 0:
            if PLOT_JITTER:
                x_meas = np.random.normal(loc=h + 0.03, scale=PLOT_JITTER_SCALE, size=len(meas_means))
            else:
                x_meas = np.full(len(meas_means), h + 0.03)

            plt.scatter(
                x_meas, meas_means,
                s=40, alpha=0.8, color='red',
                label='测量光平均电压' if first_meas else ""
            )
            first_meas = False

    plt.xlabel("湿度")
    plt.ylabel("平均电压")
    plt.title("各湿度对应文件平均电压分布图")
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.3)
    plt.tight_layout()

    output_path = os.path.join(output_folder, "humidity_mean_voltage_scatter.png")
    plt.savefig(output_path, dpi=300)
    plt.close()

    print("✓ 各湿度平均电压分布图已保存:")
    print(f"  {output_path}")


def process_batch_files():
    """批量处理文件"""
    if not os.path.exists(INPUT_FOLDER):
        print(f"输入文件夹不存在: {INPUT_FOLDER}")
        return False

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    data_files = find_data_files(INPUT_FOLDER)

    if not data_files:
        print("未找到符合命名规则的文件（格式：数字.数字_数字.txt 或 数字.数字.txt）")
        txt_files = glob.glob(os.path.join(INPUT_FOLDER, "*.txt"))
        if txt_files:
            print("文件夹中的文件:")
            for file in txt_files:
                print(f"  {os.path.basename(file)}")
        return False

    print(f"输入文件夹: {INPUT_FOLDER}")
    print(f"输出文件夹: {OUTPUT_FOLDER}")
    print(f"找到 {len(data_files)} 个数据文件")
    print("=" * 60)
    print("当前配置参数:")
    print(f"  SAVE_PROCESSING_SERIES       = {SAVE_PROCESSING_SERIES}")
    print(f"  ENABLE_OUTLIER_SUPPRESSION   = {ENABLE_OUTLIER_SUPPRESSION}")
    print(f"  ENABLE_KALMAN_FILTER         = {ENABLE_KALMAN_FILTER}")
    print(f"  ENABLE_WAVELET_DENOISE       = {ENABLE_WAVELET_DENOISE}")
    print(f"  ENABLE_PLOT_DISTRIBUTION     = {ENABLE_PLOT_DISTRIBUTION}")
    print(f"  PLOT_USE_FINAL_SIGNAL        = {PLOT_USE_FINAL_SIGNAL}")
    print(f"  PLOT_JITTER                  = {PLOT_JITTER}")
    print(f"  PLOT_JITTER_SCALE            = {PLOT_JITTER_SCALE}")
    print(f"  PROCESS_VARIANCE             = {PROCESS_VARIANCE}")
    print(f"  MEASUREMENT_VARIANCE         = {MEASUREMENT_VARIANCE}")
    print(f"  OUTLIER_WINDOW               = {OUTLIER_WINDOW}")
    print(f"  OUTLIER_SIGMA                = {OUTLIER_SIGMA}")
    print(f"  WAVELET_NAME                 = {WAVELET_NAME}")
    print(f"  WAVELET_LEVEL                = {WAVELET_LEVEL}")
    print(f"  THRESHOLD_SCALE              = {THRESHOLD_SCALE}")
    print("=" * 60)

    total_processed = 0

    # 用于绘制“每个湿度下各文件平均电压分布图”
    humidity_ref_dict = defaultdict(list)
    humidity_meas_dict = defaultdict(list)

    for humidity_level, file_number, file_path, filename in data_files:
        print(f"\n{'=' * 60}")
        print(f"处理文件: {filename}")
        print(f"湿度值: {humidity_level}")
        print(f"{'=' * 60}")

        output_filename = os.path.splitext(filename)[0] + "_feature.txt"
        output_file = os.path.join(OUTPUT_FOLDER, output_filename)

        processor = DataProcessor(humidity=humidity_level)

        if processor.process_txt_data(file_path):
            features = processor.calculate_features()

            if features is not None:
                if processor.save_features_to_txt(features, output_file):
                    total_processed += 1
                    print("✓ 成功处理")
                    print(f"输出特征文件: {output_filename}")

                    if SAVE_PROCESSING_SERIES:
                        series_filename = os.path.splitext(filename)[0] + "_series.csv"
                        series_file = os.path.join(OUTPUT_FOLDER, series_filename)
                        if processor.save_processing_series(series_file):
                            print(f"输出处理链序列文件: {series_filename}")

                    # 收集“每个文件的平均电压”
                    if ENABLE_PLOT_DISTRIBUTION:
                        if PLOT_USE_FINAL_SIGNAL:
                            ref_mean = np.mean(processor.reference_data)
                            meas_mean = np.mean(processor.measurement_data)
                        else:
                            ref_mean = np.mean(processor.raw_reference_data)
                            meas_mean = np.mean(processor.raw_measurement_data)

                        humidity_ref_dict[humidity_level].append(ref_mean)
                        humidity_meas_dict[humidity_level].append(meas_mean)

                        print(f"  文件参考光平均电压: {ref_mean:.6f}")
                        print(f"  文件测量光平均电压: {meas_mean:.6f}")

                else:
                    print("✗ 特征保存失败")
            else:
                print("✗ 特征计算失败")
        else:
            print("✗ 数据处理失败")

    # 绘图
    if ENABLE_PLOT_DISTRIBUTION and total_processed > 0:
        plot_mean_voltage_distribution(humidity_ref_dict, humidity_meas_dict, OUTPUT_FOLDER)

    print(f"\n{'=' * 60}")
    print("批量处理完成！")
    print(f"共成功处理 {total_processed}/{len(data_files)} 个文件")
    print(f"输出文件夹: {OUTPUT_FOLDER}")
    print(f"{'=' * 60}")

    return total_processed > 0


if __name__ == "__main__":
    process_batch_files()
