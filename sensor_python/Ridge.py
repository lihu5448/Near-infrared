import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.preprocessing import StandardScaler
import csv
import os
import glob


class SensorRidge:
    def __init__(self, data_directory, alpha=1.0, selected_features=None):
        self.data_dir = data_directory
        self.alpha = alpha  # 正则化强度
        self.selected_features = selected_features
        self.combined_data = None  # 初始化为None
        self.model = None
        self.scaler = StandardScaler()

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
                    print(f"跳过 {filename}：有效行数不足")
                    continue

                # 解析湿度值
                try:
                    humidity = float(lines[0])
                    if not (0 <= humidity <= 100):
                        print(f"跳过 {filename}：湿度值超出合理范围（0-100）")
                        continue
                except ValueError:
                    print(f"跳过 {filename}：第一行不是有效湿度值")
                    continue

                # 解析所有特征值
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

        # 先创建DataFrame，再单独处理缺失值（关键修正）
        self.combined_data = pd.DataFrame(all_data, columns=feat_cols + ['humidity'])

        # 修正：用当前DataFrame的均值填充缺失值（此时self.combined_data已赋值）
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
        y = self.combined_data['humidity'].values  # 目标变量

        # 标准化特征
        X_scaled = self.scaler.fit_transform(X)

        # 训练岭回归模型
        self.model = Ridge(alpha=self.alpha, random_state=42)
        self.model.fit(X_scaled, y)

        # 分析结果
        self._analyze_results(X_scaled, y)

    def _analyze_results(self, X_scaled, y):
        y_pred = self.model.predict(X_scaled)
        r2 = r2_score(y, y_pred)
        rmse = np.sqrt(mean_squared_error(y, y_pred))

        # 保存系数
        self._save_coefficients()

        # 可视化
        self._plot_results(y, y_pred)

        print(f"\n岭回归性能：R²={r2:.4f}, RMSE={rmse:.4f}")

    def _save_coefficients(self):
        """保存特征系数到CSV"""
        feat_names = self.combined_data.columns[:-1]
        coefficients = self.model.coef_
        intercept = self.model.intercept_

        with open("ridge_coefficients.csv", "w", newline="", encoding='GBK') as f:
            writer = csv.writer(f)
            writer.writerow(['Variable', 'Coefficient'])
            writer.writerow(['Intercept', f'{intercept:.6f}'])
            for feat, coef in zip(feat_names, coefficients):
                writer.writerow([feat, f'{coef:.6f}'])
        print("特征系数已保存到 ridge_coefficients.csv")

    def _plot_results(self, y_true, y_pred):
        """可视化结果"""
        plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Micro Hei', 'Heiti TC']
        plt.rcParams['axes.unicode_minus'] = False

        fig, axes = plt.subplots(2, 1, figsize=(10, 10))

        # 1. 预测值 vs 实际值
        axes[0].scatter(y_pred, y_true, color='blue', alpha=0.7, label='预测值')
        axes[0].plot([y_true.min(), y_true.max()], [y_true.min(), y_true.max()], 'r--', label='理想线')
        axes[0].set_xlabel('预测湿度')
        axes[0].set_ylabel('实际湿度')
        axes[0].set_title('岭回归：预测值 vs 实际值')
        axes[0].legend()
        axes[0].grid(alpha=0.3)

        # 2. 特征重要性（系数绝对值）
        feat_names = self.combined_data.columns[:-1]
        coef_abs = np.abs(self.model.coef_)
        sorted_idx = np.argsort(coef_abs)[::-1]  # 从大到小排序

        axes[1].bar(range(len(feat_names)), coef_abs[sorted_idx], color='skyblue')
        axes[1].set_xticks(range(len(feat_names)))
        axes[1].set_xticklabels([feat_names[i] for i in sorted_idx], rotation=45, ha='right')
        axes[1].set_xlabel('特征')
        axes[1].set_ylabel('系数绝对值（重要性）')
        axes[1].set_title('特征重要性排序')
        axes[1].grid(alpha=0.3, axis='y')

        plt.tight_layout()
        plt.savefig('ridge_analysis.jpg', dpi=300, bbox_inches='tight')
        plt.show()


# 使用示例
if __name__ == '__main__':
    # 可修改为任意数量的特征
    # selected_feats = [
    #     'feature_1', 'feature_2','feature_6','feature_9','feature_11',
    #          'feature_16','feature_17', 'feature_19', 'feature_15'
    # ]
    selected_feats = None
    # 初始化模型并训练
    ridge = SensorRidge(
        data_directory="D:\\Desktop\\sensor_python\\data_output",
        alpha=1.0,
        selected_features=selected_feats
    )
    ridge.train()