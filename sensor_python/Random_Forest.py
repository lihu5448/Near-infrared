import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score, mean_squared_error
import csv
import os
import glob


class SensorRandomForest:
    def __init__(self, data_directory, n_estimators=100, selected_features=None):
        self.data_dir = data_directory
        self.n_estimators = n_estimators  # 决策树数量
        self.selected_features = selected_features
        self.combined_data = None  # 初始化为None
        self.model = None
        # 定义特征中文名称（19个特征，对应特征1-19）
        self.feature_names = [
            "mean_refer", "mean_measure", "std_refer", "std_measure",
            "q25_refer", "median_refer", "q75_refer", "q25_measure",
            "median_measure", "q75_measure", "robust_ratio", "signal_quality",
            "range_refer", "range_measure", "mean_diff", "norm_diff",
            "reflectance_ratio", "surface_uniformity", "absorption_contrast"
        ]

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
            # 如果特征数量是19，使用中文名称，否则使用通用名称
            if len(all_data[0]) - 1 == 19:
                feat_cols = self.feature_names
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
        X = self.combined_data.iloc[:, :-1]  # 特征
        y = self.combined_data['humidity']  # 目标变量

        print(f"数据形状: {self.combined_data.shape}")
        print(f"特征数量: {X.shape[1]}")
        print(f"样本数量: {X.shape[0]}")

        # 显示特征名称
        if self.selected_features:
            print(f"使用的特征: {self.selected_features}")
        else:
            print("使用所有特征")

        # 训练随机森林模型
        self.model = RandomForestRegressor(
            n_estimators=self.n_estimators,
            random_state=42,
            n_jobs=-1  # 用所有CPU核心加速训练
        )
        self.model.fit(X, y)

        # 分析结果
        self._analyze_results(X, y)

    def _analyze_results(self, X, y):
        y_pred = self.model.predict(X)
        r2 = r2_score(y, y_pred)
        rmse = np.sqrt(mean_squared_error(y, y_pred))

        # 保存特征重要性
        self._save_importance()

        # 可视化
        self._plot_results(y, y_pred)

        print(f"\n随机森林性能：R² = {r2:.4f}, RMSE = {rmse:.4f}")

    def _save_importance(self):
        """保存特征重要性到CSV"""
        feat_names = self.combined_data.columns[:-1]
        importance = self.model.feature_importances_
        sorted_idx = np.argsort(importance)[::-1]  # 从高到低排序

        with open("rf_importance.csv", "w", newline="", encoding='GBK') as f:
            writer = csv.writer(f)
            writer.writerow(['特征', '特征名称', '重要性', '排名'])
            for rank, idx in enumerate(sorted_idx, 1):
                feature_col = feat_names[idx]
                # 获取特征中文名称
                if feature_col in self.feature_names:
                    feature_name = self.feature_names[self.feature_names.index(feature_col)]
                elif feature_col.startswith('feature_'):
                    # 如果是通用特征名，尝试映射到中文
                    try:
                        feat_num = int(feature_col.split('_')[1]) - 1
                        if 0 <= feat_num < len(self.feature_names):
                            feature_name = self.feature_names[feat_num]
                        else:
                            feature_name = feature_col
                    except:
                        feature_name = feature_col
                else:
                    feature_name = feature_col

                writer.writerow([
                    feature_col,  # 特征列名
                    feature_name,  # 特征中文名称
                    f'{importance[idx]:.6f}',
                    rank
                ])
        print("特征重要性已保存到 rf_importance.csv")

    def _plot_results(self, y_true, y_pred):
        """可视化结果"""
        plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Micro Hei', 'Heiti TC']
        plt.rcParams['axes.unicode_minus'] = False

        # 计算指标
        r2 = r2_score(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))

        fig, axes = plt.subplots(2, 1, figsize=(12, 10))

        # 1. 预测值 vs 实际值
        axes[0].scatter(y_pred, y_true, color='green', alpha=0.7, edgecolors='k', linewidths=0.5)
        axes[0].plot([y_true.min(), y_true.max()], [y_true.min(), y_true.max()], 'r--', alpha=0.8, linewidth=2)
        axes[0].set_xlabel('预测湿度 (%)', fontsize=12)
        axes[0].set_ylabel('实际湿度 (%)', fontsize=12)
        axes[0].set_title('预测值 vs 实际值', fontsize=14, fontweight='bold')
        axes[0].grid(alpha=0.3, linestyle='--')

        # 添加性能指标 - 使用原始R²字符
        axes[0].text(0.05, 0.95,
                     f'R2 = {r2:.4f}\nRMSE = {rmse:.4f}',
                     transform=axes[0].transAxes,
                     bbox=dict(facecolor='white', alpha=0.8, boxstyle='round,pad=0.5'),
                     fontsize=11,
                     verticalalignment='top')

        # 2. 特征重要性排序
        feat_names = self.combined_data.columns[:-1]
        importance = self.model.feature_importances_
        sorted_idx = np.argsort(importance)[::-1]

        # 获取特征的中文名称用于显示
        display_names = []
        for feat in feat_names:
            if feat in self.feature_names:
                display_names.append(feat)
            elif feat.startswith('feature_'):
                try:
                    feat_num = int(feat.split('_')[1]) - 1
                    if 0 <= feat_num < len(self.feature_names):
                        display_names.append(self.feature_names[feat_num])
                    else:
                        display_names.append(feat)
                except:
                    display_names.append(feat)
            else:
                display_names.append(feat)

        # 只显示前20个最重要的特征，避免图表过于拥挤
        max_features = min(20, len(feat_names))
        if len(sorted_idx) > max_features:
            sorted_idx = sorted_idx[:max_features]

        # 创建颜色渐变
        colors = plt.cm.Oranges(np.linspace(0.5, 1, max_features))

        bars = axes[1].bar(range(max_features), importance[sorted_idx][:max_features], color=colors)
        axes[1].set_xticks(range(max_features))
        axes[1].set_xticklabels([display_names[i] for i in sorted_idx[:max_features]],
                                rotation=45, ha='right', fontsize=10)
        axes[1].set_xlabel('特征', fontsize=12)
        axes[1].set_ylabel('重要性得分', fontsize=12)
        axes[1].set_title('特征重要性 (Top {})'.format(max_features), fontsize=14, fontweight='bold')
        axes[1].grid(alpha=0.3, axis='y', linestyle='--')

        # 在柱子上添加数值（只显示前10个或重要的）
        for i, rect in enumerate(bars):
            height = rect.get_height()
            if height > 0.01:  # 只显示重要性大于0.01的值
                axes[1].text(rect.get_x() + rect.get_width() / 2., height,
                             f'{height:.3f}',
                             ha='center', va='bottom', fontsize=9)

        plt.tight_layout()
        plt.savefig('rf_analysis.jpg', dpi=300, bbox_inches='tight', facecolor='white')
        print("分析图表已保存到 rf_analysis.jpg")
        plt.show()

    def predict(self, feature_values):
        """使用训练好的模型进行预测"""
        if self.model is None:
            raise ValueError("模型尚未训练，请先调用 train() 方法")

        # 确保输入特征数量匹配
        if len(feature_values) != len(self.combined_data.columns) - 1:
            raise ValueError(
                f"输入特征数量不匹配，预期 {len(self.combined_data.columns) - 1}，实际 {len(feature_values)}")

        # 转换为DataFrame
        if isinstance(feature_values, list):
            feature_values = np.array(feature_values).reshape(1, -1)

        # 进行预测
        prediction = self.model.predict(feature_values)[0]
        return prediction


# 使用示例
if __name__ == '__main__':
    # 可选：指定要使用的特征
    # selected_feats = ['feature_9', 'feature_11', 'feature_1', 'feature_6',
    #                   'feature_17', 'feature_19', 'feature_15', 'feature_16']

    selected_feats = None  # 使用所有特征

    # 创建随机森林分析器
    rf = SensorRandomForest(
        data_directory="D:\\Desktop\\sensor_python\\data_output",
        n_estimators=500,  # 可调整决策树数量（越大精度可能越高，但速度变慢）
        selected_features=selected_feats
    )

    # 训练模型并分析
    rf.train()

    # 可选：进行预测示例
    # 假设有一个新的特征向量
    # new_features = [0.1, 0.2, 0.3, ...]  # 19个特征值
    # predicted_humidity = rf.predict(new_features)
    # print(f"预测湿度: {predicted_humidity:.2f}%")