import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from sklearn.cross_decomposition import PLSRegression
from sklearn.svm import SVR
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.preprocessing import StandardScaler
import csv
import os
import glob
import random

# 固定随机种子，确保结果可复现
random.seed(42)
np.random.seed(42)


class SensorPLSSVR:
    def __init__(self, train_directory, test_directory, n_components=5, C=1.0, epsilon=0.1, selected_features=None):
        self.train_dir = train_directory  # 训练集数据路径
        self.test_dir = test_directory  # 测试集数据路径
        self.n_components = n_components  # PLS主成分数
        self.C = C  # SVR惩罚系数
        self.epsilon = epsilon  # SVR不敏感损失参数
        self.selected_features = selected_features
        self.combined_data = None  # 训练集数据
        self.test_data = None  # 测试集数据
        self.pls = None
        self.svr = None
        self.scaler_X = StandardScaler()
        self.scaler_y = StandardScaler()

    def _load_all_files_from_dir(self, directory, dataset_type):
        """从指定目录加载所有文件并转换为DataFrame"""
        feature_files = glob.glob(os.path.join(directory, "*_feature.txt"))
        print(f"在{dataset_type}路径中找到 {len(feature_files)} 个特征文件")

        if len(feature_files) == 0:
            raise ValueError(f"{dataset_type}路径中没有找到特征文件：{directory}")

        all_data = []
        invalid_files = []

        for file_path in feature_files:
            try:
                filename = os.path.basename(file_path)
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]

                if len(lines) < 2:
                    print(f"跳过 {filename}：有效行数不足（至少需要2行）")
                    invalid_files.append((filename, "有效行数不足"))
                    continue

                # 解析湿度值
                humidity = float(lines[0])
                if not (0 <= humidity <= 100):
                    print(f"跳过 {filename}：湿度值 {humidity} 超出合理范围")
                    invalid_files.append((filename, f"湿度值 {humidity} 超出范围"))
                    continue

                # 解析特征值
                all_feats = []
                for line in lines[1:]:
                    if self._is_numeric(line):
                        all_feats.append(float(line))
                    else:
                        print(f"警告：{filename} 中特征值 '{line}' 非数值，已跳过")

                if not all_feats:
                    print(f"跳过 {filename}：无有效特征值")
                    invalid_files.append((filename, "无有效特征值"))
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
                print(f"处理 {filename} 出错：{str(e)}，已跳过")
                invalid_files.append((filename, str(e)))
                continue

        if not all_data:
            raise ValueError(f"未加载到任何有效{dataset_type}数据")

        # 打印无效文件信息
        if invalid_files:
            print(f"\n{dataset_type}中发现 {len(invalid_files)} 个无效文件，已跳过：")
            for file, reason in invalid_files[:5]:  # 只显示前5个
                print(f"  - {file}: {reason}")
            if len(invalid_files) > 5:
                print(f"  ... 还有 {len(invalid_files) - 5} 个无效文件")

        # 确定特征列名
        if self.selected_features:
            feat_cols = self.selected_features
        else:
            feat_cols = [f'feature_{i + 1}' for i in range(len(all_data[0]) - 1)]

        # 创建DataFrame
        df = pd.DataFrame(all_data, columns=feat_cols + ['humidity'])

        # 填充缺失值
        if df.isnull().sum().sum() > 0:
            print(f"{dataset_type}检测到缺失值，开始填充...")
            if dataset_type == "测试集" and self.combined_data is not None:
                # 测试集用训练集的均值填充，避免数据泄露
                df = df.fillna(self.combined_data.mean())
                print(f"  测试集使用训练集均值填充完成")
            else:
                # 训练集用自身均值填充
                df = df.fillna(df.mean())
                print(f"  {dataset_type}使用自身均值填充完成")

        return df

    def _is_numeric(self, s):
        """判断字符串是否为数值"""
        try:
            float(s)
            return True
        except:
            return False

    def train(self):
        """主训练流程"""
        # 1. 加载训练集数据
        print(f"开始加载训练集数据...")
        self.combined_data = self._load_all_files_from_dir(self.train_dir, dataset_type="训练集")

        # 2. 加载测试集数据
        print(f"\n开始加载测试集数据...")
        self.test_data = self._load_all_files_from_dir(self.test_dir, dataset_type="测试集")

        # 3. 准备训练和测试数据
        X_train = self.combined_data.iloc[:, :-1]
        y_train = self.combined_data['humidity']
        X_test = self.test_data.iloc[:, :-1]
        y_test = self.test_data['humidity']

        print(f"\n数据维度信息：")
        print(f"  训练集：{X_train.shape[0]} 样本，{X_train.shape[1]} 特征")
        print(f"  测试集：{X_test.shape[0]} 样本，{X_test.shape[1]} 特征")

        # 检查训练集和测试集是否有重叠的湿度值
        train_humidities = set(y_train.unique())
        test_humidities = set(y_test.unique())
        common_humidities = train_humidities.intersection(test_humidities)

        print(f"  训练集湿度范围：{y_train.min():.1f}% - {y_train.max():.1f}%")
        print(f"  测试集湿度范围：{y_test.min():.1f}% - {y_test.max():.1f}%")
        print(f"  共同湿度值数量：{len(common_humidities)}")

        # 4. 数据标准化
        print(f"\n开始数据标准化...")
        X_train_scaled = self.scaler_X.fit_transform(X_train)
        X_test_scaled = self.scaler_X.transform(X_test)

        y_train_scaled = self.scaler_y.fit_transform(y_train.values.reshape(-1, 1)).ravel()
        y_test_scaled = self.scaler_y.transform(y_test.values.reshape(-1, 1)).ravel()

        # 5. PLS降维
        print(f"开始PLS降维（主成分数：{self.n_components}）...")
        self.pls = PLSRegression(n_components=self.n_components)
        X_train_pls = self.pls.fit_transform(X_train_scaled, y_train_scaled)[0]
        X_test_pls = self.pls.transform(X_test_scaled)

        print(f"  PLS降维后维度：{X_train_pls.shape[1]}")

        # 6. 训练SVR模型
        print(f"开始训练SVR模型（C={self.C}, epsilon={self.epsilon}）...")
        self.svr = SVR(C=self.C, epsilon=self.epsilon, kernel='rbf')
        self.svr.fit(X_train_pls, y_train_scaled)

        # 7. 分析模型结果
        self._analyze_results(X_train_pls, y_train_scaled, X_test_pls, y_test_scaled, y_train, y_test)

    def _analyze_results(self, X_train_pls, y_train_scaled, X_test_pls, y_test_scaled, y_train_orig, y_test_orig):
        """分析模型性能并可视化"""
        # 预测（标准化空间）
        y_train_pred_scaled = self.svr.predict(X_train_pls)
        y_test_pred_scaled = self.svr.predict(X_test_pls)

        # 反标准化到原始空间
        y_train_pred = self.scaler_y.inverse_transform(y_train_pred_scaled.reshape(-1, 1)).ravel()
        y_test_pred = self.scaler_y.inverse_transform(y_test_pred_scaled.reshape(-1, 1)).ravel()

        # 计算评估指标
        train_r2 = r2_score(y_train_orig, y_train_pred)
        train_rmse = np.sqrt(mean_squared_error(y_train_orig, y_train_pred))
        test_r2 = r2_score(y_test_orig, y_test_pred)
        test_rmse = np.sqrt(mean_squared_error(y_test_orig, y_test_pred))

        # 保存变量重要性（基于PLS权重）
        self._save_variable_importance()

        # 可视化结果
        self._plot_results(y_train_orig, y_train_pred, y_test_orig, y_test_pred,
                           train_r2, train_rmse, test_r2, test_rmse)

        # 打印性能指标
        print(f"\n=== PLS-SVR模型性能评估 ===")
        print(f"训练集 - R²: {train_r2:.4f}, RMSE: {train_rmse:.4f}")
        print(f"测试集 - R²: {test_r2:.4f}, RMSE: {test_rmse:.4f}")
        print(f"===========================")

        # 性能警告
        if train_r2 - test_r2 > 0.2:
            print("⚠️ 警告：测试集性能明显低于训练集，可能存在过拟合")
        elif test_r2 < 0.8:
            print("⚠️ 警告：测试集R²较低，模型泛化能力可能不足")
        else:
            print("✅ 模型性能良好")

    def _save_variable_importance(self):
        """保存变量重要性（基于PLS权重）到CSV文件"""
        feat_names = self.combined_data.columns[:-1]

        # 使用PLS的权重作为变量重要性指标
        if hasattr(self.pls, 'x_weights_'):
            importance = np.abs(self.pls.x_weights_[:, 0])  # 使用第一主成分的权重
            sorted_idx = np.argsort(importance)[::-1]

            with open("pls_svr_variable_importance.csv", "w", newline="", encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['排名', '变量名称', '重要性得分'])
                for rank, idx in enumerate(sorted_idx, 1):
                    writer.writerow([
                        rank,
                        feat_names[idx],
                        f"{importance[idx]:.6f}"
                    ])
            print(f"变量重要性已保存到 pls_svr_variable_importance.csv")
        else:
            print("无法计算变量重要性：PLS模型未包含权重信息")

    def _plot_results(self, y_train, y_train_pred, y_test, y_test_pred,
                      train_r2, train_rmse, test_r2, test_rmse):
        """可视化训练集和测试集结果"""
        plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Micro Hei', 'Heiti TC']
        plt.rcParams['axes.unicode_minus'] = False

        fig, axes = plt.subplots(2, 1, figsize=(10, 12))
        fig.suptitle(f'PLS-SVR湿度预测分析（PLS成分数：{self.n_components}）', fontsize=16)

        # 1. 训练集：预测值 vs 实际值
        axes[0].scatter(y_train_pred, y_train, color='green', alpha=0.6, label='训练样本', s=50)
        axes[0].plot([y_train.min() - 5, y_train.max() + 5],
                     [y_train.min() - 5, y_train.max() + 5],
                     'r--', alpha=0.8, label='理想拟合线(y=x)', linewidth=2)
        axes[0].set_xlabel('预测湿度')
        axes[0].set_ylabel('实际湿度')
        axes[0].set_title('训练集：预测值 vs 实际值')
        axes[0].grid(alpha=0.3)
        axes[0].legend(loc='lower right')

        # 显示评估指标
        axes[0].text(0.02, 0.98,
                     f'$R^2$ = {train_r2:.4f}\nRMSE = {train_rmse:.4f}',
                     transform=axes[0].transAxes,
                     bbox=dict(facecolor='white', alpha=0.9, boxstyle='round'),
                     verticalalignment='top',
                     fontsize=12,
                     fontweight='bold')

        # 2. 测试集：预测值 vs 实际值
        axes[1].scatter(y_test_pred, y_test, color='blue', alpha=0.6, label='测试样本', s=50)
        axes[1].plot([y_test.min() - 5, y_test.max() + 5],
                     [y_test.min() - 5, y_test.max() + 5],
                     'r--', alpha=0.8, label='理想拟合线(y=x)', linewidth=2)
        axes[1].set_xlabel('预测湿度')
        axes[1].set_ylabel('实际湿度')
        axes[1].set_title('测试集：预测值 vs 实际值')
        axes[1].grid(alpha=0.3)
        axes[1].legend(loc='lower right')

        # 显示评估指标
        axes[1].text(0.02, 0.98,
                     f'$R^2$ = {test_r2:.4f}\nRMSE = {test_rmse:.4f}',
                     transform=axes[1].transAxes,
                     bbox=dict(facecolor='white', alpha=0.9, boxstyle='round'),
                     verticalalignment='top',
                     fontsize=12,
                     fontweight='bold')

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.savefig('pls_svr_analysis_results.jpg', dpi=300, bbox_inches='tight')
        plt.show()


# 使用示例
if __name__ == '__main__':
    # selected_feats = ['feature_11', 'feature_12', 'feature_18',
    #                  'feature_17', 'feature_19', 'feature_15', 'feature_16']
    selected_feats = None  # 使用全部特征

    pls_svr = SensorPLSSVR(
        train_directory="D:\\Desktop\\sensor_python\\data_output\\",  # 训练集路径
        test_directory="D:\\Desktop\\sensor_python\\data_output\\test_data",  # 测试集路径
        n_components=5,  # PLS主成分数
        C=20,  # SVR惩罚系数
        epsilon=0.01,  # SVR不敏感损失参数
        selected_features=selected_feats
    )
    pls_svr.train()