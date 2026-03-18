import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from sklearn.linear_model import Lasso  # 关键：正确导入sklearn的Lasso模型
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.preprocessing import StandardScaler
import csv
import os
import glob


# 类名改为SensorLasso，与导入的Lasso模型区分开
class SensorLasso:
    def __init__(self, data_directory, alpha=1.0, selected_features=None):
        self.data_dir = data_directory
        self.alpha = alpha  # L1正则化强度（越大，特征系数越容易被压缩为0）
        self.selected_features = selected_features
        self.combined_data = None
        self.model = None  # 用于存储Lasso模型实例
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
                        idx = int(feat.split('_')[1]) - 1
                        if idx < len(all_feats):
                            feats.append(all_feats[idx])
                        else:
                            print(f"警告：{filename} 中无 {feat}，用NaN填充")
                            feats.append(np.nan)
                else:
                    feats = all_feats

                all_data.append(feats + [humidity])

            except Exception as e:
                print(f"处理 {filename} 出错：{e}")
                continue

        if not all_data:
            raise ValueError("未加载到任何有效数据")

        # 创建DataFrame
        feat_cols = self.selected_features if self.selected_features else [f'feature_{i + 1}' for i in
                                                                           range(len(all_data[0]) - 1)]
        self.combined_data = pd.DataFrame(all_data, columns=feat_cols + ['humidity'])

        # 填充缺失值（修正时序问题）
        if self.combined_data.isnull().sum().sum() > 0:
            print("检测到缺失值，用列均值填充")
            self.combined_data = self.combined_data.fillna(self.combined_data.mean())

        return self.combined_data

    def _is_numeric(self, s):
        try:
            float(s)
            return True
        except:
            return False

    def train(self):
        self.load_data()
        X = self.combined_data.iloc[:, :-1].values
        y = self.combined_data['humidity'].values

        # 标准化（Lasso对特征尺度敏感，必须标准化）
        X_scaled = self.scaler.fit_transform(X)

        # 关键修正：明确使用sklearn的Lasso模型，与类名区分
        self.model = Lasso(alpha=self.alpha, random_state=42, max_iter=10000)  # 增加迭代次数避免收敛警告
        self.model.fit(X_scaled, y)

        self._analyze_results(X_scaled, y)

    def _analyze_results(self, X_scaled, y):
        y_pred = self.model.predict(X_scaled)
        r2 = r2_score(y, y_pred)
        rmse = np.sqrt(mean_squared_error(y, y_pred))

        self._save_coefficients()
        self._plot_results(y, y_pred)

        print(f"\nLasso回归性能：R²={r2:.4f}, RMSE={rmse:.4f}")
        print(f"被Lasso压缩为0的特征数：{np.sum(self.model.coef_ == 0)}")  # Lasso的特征选择特性

    def _save_coefficients(self):
        feat_names = self.combined_data.columns[:-1]
        coefficients = self.model.coef_
        intercept = self.model.intercept_

        with open("lasso_coefficients.csv", "w", newline="", encoding='GBK') as f:
            writer = csv.writer(f)
            writer.writerow(['Variable', 'Coefficient', 'Status'])  # Status：是否被保留
            writer.writerow(['Intercept', f'{intercept:.6f}', '保留'])
            for feat, coef in zip(feat_names, coefficients):
                status = '保留' if coef != 0 else '被压缩为0'
                writer.writerow([feat, f'{coef:.6f}', status])
        print("特征系数已保存到 lasso_coefficients.csv")

    def _plot_results(self, y_true, y_pred):
        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.rcParams['axes.unicode_minus'] = False

        fig, axes = plt.subplots(2, 1, figsize=(10, 10))

        # 1. 预测值vs实际值
        axes[0].scatter(y_pred, y_true, color='green', alpha=0.7)
        axes[0].plot([y_true.min(), y_true.max()], [y_true.min(), y_true.max()], 'r--')
        axes[0].set_xlabel('预测湿度')
        axes[0].set_ylabel('实际湿度')
        axes[0].set_title('Lasso回归：预测值vs实际值')
        axes[0].grid(alpha=0.3)

        # 2. 特征系数（显示哪些被压缩为0）
        feat_names = self.combined_data.columns[:-1]
        coefficients = self.model.coef_
        sorted_idx = np.argsort(np.abs(coefficients))[::-1]

        colors = ['blue' if coef != 0 else 'gray' for coef in coefficients[sorted_idx]]
        axes[1].bar(range(len(feat_names)), coefficients[sorted_idx], color=colors)
        axes[1].axhline(y=0, color='black', linestyle='--', alpha=0.3)
        axes[1].set_xticks(range(len(feat_names)))
        axes[1].set_xticklabels([feat_names[i] for i in sorted_idx], rotation=45, ha='right')
        axes[1].set_xlabel('特征')
        axes[1].set_ylabel('系数值（非零=保留，灰色=压缩为0）')
        axes[1].set_title('Lasso特征系数')
        axes[1].grid(alpha=0.3, axis='y')

        plt.tight_layout()
        plt.savefig('lasso_analysis.jpg', dpi=300)
        plt.show()


# 使用示例
if __name__ == '__main__':
    # selected_feats = ['feature_9', 'feature_11', 'feature_1', 'feature_6',
    #                   'feature_17', 'feature_19', 'feature_15', 'feature_16']
    selected_feats = None
    lasso = SensorLasso(
        data_directory="D:\\Desktop\\sensor_python\\data_output",
        alpha=0.1,  # alpha越小，保留的特征越多；alpha=0退化为线性回归
        selected_features=selected_feats
    )
    lasso.train()