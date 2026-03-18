import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from sklearn.svm import SVR
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.preprocessing import StandardScaler
import csv
import os
import glob


class SensorSVR:
    def __init__(self, data_directory, kernel='rbf', selected_features=None):
        self.data_dir = data_directory
        self.kernel = kernel  # 核函数：'rbf'（默认）、'linear'、'poly'等
        self.selected_features = selected_features
        self.combined_data = None  # 初始化为None
        self.model = None
        self.scaler_X = StandardScaler()  # 特征标准化器
        self.scaler_y = StandardScaler()  # 目标变量标准化器（SVR对尺度敏感）

    def load_data(self):
        all_data = []
        feature_files = glob.glob(os.path.join(self.data_dir, "*_feature.txt"))
        print(f"找到 {len(feature_files)} 个特征文件")

        for file_path in feature_files:
            try:
                filename = os.path.basename(file_path)
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]

                if len(lines) < 2:
                    print(f"跳过 {filename}：有效行数不足（至少2行）")
                    continue

                # 解析湿度值
                try:
                    humidity = float(lines[0])
                    if not (0 <= humidity <= 100):
                        print(f"跳过 {filename}：湿度值 {humidity} 超出合理范围（0-100）")
                        continue
                except ValueError:
                    print(f"跳过 {filename}：第一行不是有效湿度值")
                    continue

                # 解析特征值
                all_feats = []
                for line in lines[1:]:
                    if self._is_numeric(line):
                        all_feats.append(float(line))
                    else:
                        print(f"警告：{filename} 中特征值非数值，已跳过")

                if not all_feats:
                    print(f"跳过 {filename}：无有效特征值")
                    continue

                # 筛选指定特征
                if self.selected_features:
                    feats = []
                    for feat in self.selected_features:
                        idx = int(feat.split('_')[1]) - 1  # 转换为0-based索引
                        if idx < len(all_feats):
                            feats.append(all_feats[idx])
                        else:
                            print(f"警告：{filename} 中无 {feat}，用NaN填充")
                            feats.append(np.nan)
                else:
                    feats = all_feats  # 使用全部特征

                all_data.append(feats + [humidity])

            except Exception as e:
                print(f"处理 {filename} 出错：{e}")
                continue

        if not all_data:
            raise ValueError("未加载到任何有效数据")

        # 确定特征列名
        if self.selected_features:
            feat_cols = self.selected_features
        else:
            feat_cols = [f'feature_{i + 1}' for i in range(len(all_data[0]) - 1)]

        # 关键修正：先创建DataFrame，再单独填充缺失值
        self.combined_data = pd.DataFrame(all_data, columns=feat_cols + ['humidity'])

        # 此时self.combined_data已赋值，可安全调用mean()
        if self.combined_data.isnull().sum().sum() > 0:
            print("检测到缺失值，用列均值填充")
            self.combined_data = self.combined_data.fillna(self.combined_data.mean())

        return self.combined_data

    def _is_numeric(self, s):
        """判断字符串是否为数值"""
        try:
            float(s)
            return True
        except:
            return False

    def train(self):
        self.load_data()  # 加载并处理数据
        X = self.combined_data.iloc[:, :-1].values  # 特征
        y = self.combined_data['humidity'].values.reshape(-1, 1)  # 目标变量（二维数组格式）

        # SVR对特征和目标变量的尺度敏感，必须标准化
        X_scaled = self.scaler_X.fit_transform(X)
        y_scaled = self.scaler_y.fit_transform(y).flatten()  # 转为一维数组

        # 训练SVR模型
        self.model = SVR(
            kernel=self.kernel,
            C=1.0,  # 正则化强度（越大越容易过拟合）
            gamma='scale',  # 核系数（自动根据特征数调整）
            epsilon=0.1  # 不敏感损失函数的阈值
        )
        self.model.fit(X_scaled, y_scaled)

        # 分析结果
        self._analyze_results(X_scaled, y)

    def _analyze_results(self, X_scaled, y_true):
        # 预测并反标准化（将预测值转回原始湿度尺度）
        y_pred_scaled = self.model.predict(X_scaled)
        y_pred = self.scaler_y.inverse_transform(y_pred_scaled.reshape(-1, 1)).flatten()

        # 计算性能指标
        r2 = r2_score(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))

        # 可视化
        self._plot_results(y_true, y_pred)

        print(f"\nSVR性能（核函数：{self.kernel}）：R²={r2:.4f}, RMSE={rmse:.4f}")

    def _plot_results(self, y_true, y_pred):
        """可视化结果"""
        plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Micro Hei', 'Heiti TC']
        plt.rcParams['axes.unicode_minus'] = False

        fig, ax = plt.subplots(1, 1, figsize=(10, 6))

        # 预测值 vs 实际值
        ax.scatter(y_pred, y_true, color='purple', alpha=0.7, label='预测样本')
        ax.plot([y_true.min(), y_true.max()], [y_true.min(), y_true.max()], 'r--', alpha=0.8, label='理想线')
        ax.set_xlabel('预测湿度')
        ax.set_ylabel('实际湿度')
        ax.set_title(f'SVR（核函数：{self.kernel}）：预测值 vs 实际值')
        ax.legend()
        ax.grid(alpha=0.3)

        # 添加性能指标
        ax.text(0.05, 0.95,
                f'R²={r2_score(y_true, y_pred):.4f}\nRMSE={np.sqrt(mean_squared_error(y_true, y_pred)):.4f}',
                transform=ax.transAxes, bbox=dict(facecolor='white', alpha=0.8))

        plt.tight_layout()
        plt.savefig('svr_analysis.jpg', dpi=300, bbox_inches='tight')
        plt.show()


# 使用示例
if __name__ == '__main__':
    selected_feats = ['feature_9', 'feature_11', 'feature_1', 'feature_6',
                      'feature_17', 'feature_19', 'feature_15', 'feature_16']
    svr = SensorSVR(
        data_directory="D:\\Desktop\\sensor_python\\data_output",
        kernel='rbf',  # 推荐用'rbf'处理非线性数据
        selected_features=selected_feats
    )
    svr.train()