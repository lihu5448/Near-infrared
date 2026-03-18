import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.preprocessing import StandardScaler
import csv
import os
import glob
from scipy.spatial.distance import cdist


class SensorRandomForest:
    def __init__(self, data_directory, n_estimators=100, selected_features=None,
                 split_ratio=0.6, random_seed=42):
        self.data_dir = data_directory
        self.n_estimators = n_estimators
        self.selected_features = selected_features
        self.split_ratio = split_ratio
        self.random_seed = random_seed
        self.combined_data = None
        self.model = None
        self.scaler = StandardScaler()

        # 定义数据集
        self.X_train = None
        self.X_test = None
        self.y_train = None
        self.y_test = None

        # 定义特征中文名称
        self.feature_names = [
            "mean_refer", "mean_measure", "std_refer", "std_measure",
            "q25_refer", "median_refer", "q75_refer", "q25_measure",
            "median_measure", "q75_measure", "robust_ratio", "signal_quality",
            "range_refer", "range_measure", "mean_diff", "norm_diff",
            "reflectance_ratio", "surface_uniformity", "absorption_contrast"
        ]

    def _kennard_stone_split(self, X, y, test_size=0.4):
        """
        Kennard-Stone算法划分数据集
        Args:
            X: 特征矩阵
            y: 目标变量
            test_size: 测试集比例
        Returns:
            划分后的数据集
        """
        n_samples = X.shape[0]
        n_train = int(n_samples * (1 - test_size))

        # 确保有足够的样本
        if n_train < 2:
            raise ValueError(f"样本数不足，无法划分。总样本数: {n_samples}，需要至少2个训练样本")

        # 标准化特征
        X_scaled = self.scaler.fit_transform(X)

        # 1. 选择第一个点：选择离所有点中心最远的点
        center = np.mean(X_scaled, axis=0)
        distances = cdist(X_scaled, center.reshape(1, -1)).flatten()
        selected_indices = [np.argmax(distances)]  # 选择最远的点作为起始

        # 2. 逐步选择训练集样本
        while len(selected_indices) < n_train:
            selected = X_scaled[selected_indices]
            remaining_indices = [i for i in range(n_samples) if i not in selected_indices]

            if not remaining_indices:
                break  # 没有剩余样本了

            remaining = X_scaled[remaining_indices]

            # 计算每个剩余样本到已选样本的最小距离
            distances = cdist(remaining, selected).min(axis=1)
            next_idx = remaining_indices[np.argmax(distances)]  # 选择距离最大的样本
            selected_indices.append(next_idx)

        # 创建训练集和测试集索引
        train_indices = selected_indices
        test_indices = [i for i in range(n_samples) if i not in train_indices]

        print(f"训练集索引: {len(train_indices)} 个样本")
        print(f"测试集索引: {len(test_indices)} 个样本")

        return (X.iloc[train_indices], X.iloc[test_indices],
                y.iloc[train_indices], y.iloc[test_indices])

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

        # 确定特征列名
        if self.selected_features:
            feat_cols = self.selected_features
        else:
            if len(all_data[0]) - 1 == 19:
                feat_cols = self.feature_names
            else:
                feat_cols = [f'feature_{i + 1}' for i in range(len(all_data[0]) - 1)]

        self.combined_data = pd.DataFrame(all_data, columns=feat_cols + ['humidity'])

        # 处理缺失值
        if self.combined_data.isnull().sum().sum() > 0:
            print("检测到缺失值，用列均值填充")
            self.combined_data = self.combined_data.fillna(self.combined_data.mean())

        print(f"加载数据形状: {self.combined_data.shape}")
        return self.combined_data

    def _is_numeric(self, s):
        """判断字符串是否为数值"""
        try:
            float(s)
            return True
        except:
            return False

    def split_data(self):
        """使用K-S方法划分数据集"""
        X = self.combined_data.iloc[:, :-1]
        y = self.combined_data['humidity']

        print(f"\n使用K-S方法划分数据集...")
        print(f"总样本数: {len(X)}")
        print(f"划分比例: {self.split_ratio}:{1 - self.split_ratio}")

        # 使用K-S算法划分
        self.X_train, self.X_test, self.y_train, self.y_test = self._kennard_stone_split(
            X, y, test_size=1 - self.split_ratio
        )

        print(f"\n数据集划分结果:")
        print(f"校正集样本数: {len(self.X_train)}")
        print(f"预测集样本数: {len(self.X_test)}")
        print(f"校正集特征形状: {self.X_train.shape}")
        print(f"预测集特征形状: {self.X_test.shape}")

        # 计算数据集统计信息
        self._calculate_dataset_stats()

        return self.X_train, self.X_test, self.y_train, self.y_test

    def _calculate_dataset_stats(self):
        """计算校正集和预测集的统计特征"""
        print("\n" + "=" * 60)
        print("数据集统计信息")
        print("=" * 60)

        # 校正集统计
        train_mean = self.y_train.mean()
        train_std = self.y_train.std()
        train_range = (self.y_train.min(), self.y_train.max())

        # 预测集统计
        test_mean = self.y_test.mean()
        test_std = self.y_test.std()
        test_range = (self.y_test.min(), self.y_test.max())

        print(f"{'统计量':<15} {'校正集':<20} {'预测集':<20}")
        print(f"{'-' * 60}")
        print(f"{'样本数':<15} {len(self.y_train):<20} {len(self.y_test):<20}")
        print(f"{'均值':<15} {train_mean:<20.4f} {test_mean:<20.4f}")
        print(f"{'标准差':<15} {train_std:<20.4f} {test_std:<20.4f}")
        print(f"{'最小值':<15} {train_range[0]:<20.4f} {test_range[0]:<20.4f}")
        print(f"{'最大值':<15} {train_range[1]:<20.4f} {test_range[1]:<20.4f}")
        print(f"{'范围':<15} {train_range[1] - train_range[0]:<20.4f} {test_range[1] - test_range[0]:<20.4f}")

        # 保存数据集信息到文件
        self._save_dataset_info(train_mean, train_std, test_mean, test_std)

        return train_mean, train_std, test_mean, test_std

    def _save_dataset_info(self, train_mean, train_std, test_mean, test_std):
        """保存数据集划分信息到CSV文件"""
        with open("dataset_split_info.csv", "w", newline="", encoding='GBK') as f:
            writer = csv.writer(f)
            writer.writerow(['项目', '校正集', '预测集'])
            writer.writerow(['样本数', len(self.y_train), len(self.y_test)])
            writer.writerow(['均值', f'{train_mean:.4f}', f'{test_mean:.4f}'])
            writer.writerow(['标准差', f'{train_std:.4f}', f'{test_std:.4f}'])
            writer.writerow(['最小值', f'{self.y_train.min():.4f}', f'{self.y_test.min():.4f}'])
            writer.writerow(['最大值', f'{self.y_train.max():.4f}', f'{self.y_test.max():.4f}'])
            writer.writerow(['范围', f'{self.y_train.max() - self.y_train.min():.4f}',
                             f'{self.y_test.max() - self.y_test.min():.4f}'])
            writer.writerow(['', '', ''])
            writer.writerow(['划分比例', f'{self.split_ratio}:{1 - self.split_ratio}', ''])
            writer.writerow(['划分方法', 'Kennard-Stone (K-S)', ''])

        print(f"\n数据集划分信息已保存到 dataset_split_info.csv")

    def train(self):
        """训练随机森林模型"""
        # 1. 加载数据
        self.load_data()

        # 2. 划分数据集
        self.split_data()

        print(f"\n特征数量: {self.X_train.shape[1]}")
        if self.selected_features:
            print(f"使用的特征: {self.selected_features}")
        else:
            print("使用所有特征")

        # 3. 训练模型
        self.model = RandomForestRegressor(
            n_estimators=self.n_estimators,
            random_state=self.random_seed,
            n_jobs=-1
        )
        self.model.fit(self.X_train, self.y_train)

        # 4. 在训练集上评估
        train_pred = self.model.predict(self.X_train)
        train_r2 = r2_score(self.y_train, train_pred)
        train_rmse = np.sqrt(mean_squared_error(self.y_train, train_pred))

        print(f"\n校正集性能：")
        print(f"R² = {train_r2:.4f}")
        print(f"RMSE = {train_rmse:.4f}")

        # 5. 在测试集上评估
        test_pred = self.model.predict(self.X_test)
        test_r2 = r2_score(self.y_test, test_pred)
        test_rmse = np.sqrt(mean_squared_error(self.y_test, test_pred))

        print(f"\n预测集性能：")
        print(f"R² = {test_r2:.4f}")
        print(f"RMSE = {test_rmse:.4f}")

        # 6. 分析结果
        self._analyze_results(train_pred, test_pred)

        return train_r2, train_rmse, test_r2, test_rmse

    def _analyze_results(self, train_pred, test_pred):
        """分析并保存结果"""
        # 保存特征重要性
        self._save_importance()

        # 可视化结果
        self._plot_results(train_pred, test_pred)

        # 保存预测结果
        self._save_predictions(train_pred, test_pred)

    def _save_importance(self):
        """保存特征重要性"""
        feat_names = self.combined_data.columns[:-1]
        importance = self.model.feature_importances_
        sorted_idx = np.argsort(importance)[::-1]

        with open("rf_importance_ks_split.csv", "w", newline="", encoding='GBK') as f:
            writer = csv.writer(f)
            writer.writerow(['特征', '特征名称', '重要性', '排名'])
            for rank, idx in enumerate(sorted_idx, 1):
                feature_col = feat_names[idx]
                if feature_col in self.feature_names:
                    feature_name = feature_col
                elif feature_col.startswith('feature_'):
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

                writer.writerow([feature_col, feature_name, f'{importance[idx]:.6f}', rank])

        print("特征重要性已保存到 rf_importance_ks_split.csv")

    def _save_predictions(self, train_pred, test_pred):
        """保存预测结果到CSV文件（分别保存校正集和预测集）"""
        # 校正集预测结果
        train_results = pd.DataFrame({
            '样本编号': range(1, len(self.y_train) + 1),
            '实际值': self.y_train.values,
            '预测值': train_pred,
            '残差': self.y_train.values - train_pred,
            '数据集': '校正集'
        })

        # 预测集预测结果
        test_results = pd.DataFrame({
            '样本编号': range(1, len(self.y_test) + 1),
            '实际值': self.y_test.values,
            '预测值': test_pred,
            '残差': self.y_test.values - test_pred,
            '数据集': '预测集'
        })

        # 保存到两个文件
        train_results.to_csv('train_predictions.csv', index=False, encoding='GBK')
        test_results.to_csv('test_predictions.csv', index=False, encoding='GBK')

        # 也可以保存到一个合并的文件（添加起始索引来区分）
        train_results['样本编号'] = 'T' + train_results['样本编号'].astype(str)
        test_results['样本编号'] = 'P' + test_results['样本编号'].astype(str)
        all_results = pd.concat([train_results, test_results], ignore_index=True)
        all_results.to_csv('all_predictions.csv', index=False, encoding='GBK')

        print("预测结果已保存到 train_predictions.csv, test_predictions.csv, all_predictions.csv")

    def _plot_results(self, train_pred, test_pred):
        """可视化结果"""
        plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Micro Hei', 'Heiti TC']
        plt.rcParams['axes.unicode_minus'] = False

        # 计算指标
        train_r2 = r2_score(self.y_train, train_pred)
        train_rmse = np.sqrt(mean_squared_error(self.y_train, train_pred))
        test_r2 = r2_score(self.y_test, test_pred)
        test_rmse = np.sqrt(mean_squared_error(self.y_test, test_pred))

        fig, axes = plt.subplots(2, 2, figsize=(15, 12))

        # 1. 校正集预测 vs 实际值
        axes[0, 0].scatter(train_pred, self.y_train, color='blue', alpha=0.7,
                           edgecolors='k', linewidths=0.5, label='校正集')
        axes[0, 0].plot([self.y_train.min(), self.y_train.max()],
                        [self.y_train.min(), self.y_train.max()],
                        'r--', alpha=0.8, linewidth=2)
        axes[0, 0].set_xlabel('预测湿度 (%)', fontsize=12)
        axes[0, 0].set_ylabel('实际湿度 (%)', fontsize=12)
        axes[0, 0].set_title('校正集：预测值 vs 实际值', fontsize=13, fontweight='bold')
        axes[0, 0].grid(alpha=0.3, linestyle='--')
        axes[0, 0].legend()

        # 添加性能指标
        axes[0, 0].text(0.05, 0.95,
                        f'R² = {train_r2:.4f}\nRMSE = {train_rmse:.4f}\nN = {len(self.y_train)}',
                        transform=axes[0, 0].transAxes,
                        bbox=dict(facecolor='white', alpha=0.8, boxstyle='round,pad=0.5'),
                        fontsize=10,
                        verticalalignment='top')

        # 2. 预测集预测 vs 实际值
        axes[0, 1].scatter(test_pred, self.y_test, color='green', alpha=0.7,
                           edgecolors='k', linewidths=0.5, label='预测集')
        axes[0, 1].plot([self.y_test.min(), self.y_test.max()],
                        [self.y_test.min(), self.y_test.max()],
                        'r--', alpha=0.8, linewidth=2)
        axes[0, 1].set_xlabel('预测湿度 (%)', fontsize=12)
        axes[0, 1].set_ylabel('实际湿度 (%)', fontsize=12)
        axes[0, 1].set_title('预测集：预测值 vs 实际值', fontsize=13, fontweight='bold')
        axes[0, 1].grid(alpha=0.3, linestyle='--')
        axes[0, 1].legend()

        # 添加性能指标
        axes[0, 1].text(0.05, 0.95,
                        f'R² = {test_r2:.4f}\nRMSE = {test_rmse:.4f}\nN = {len(self.y_test)}',
                        transform=axes[0, 1].transAxes,
                        bbox=dict(facecolor='white', alpha=0.8, boxstyle='round,pad=0.5'),
                        fontsize=10,
                        verticalalignment='top')

        # 3. 残差图
        train_residuals = self.y_train.values - train_pred
        test_residuals = self.y_test.values - test_pred

        axes[1, 0].scatter(train_pred, train_residuals, color='blue', alpha=0.7,
                           edgecolors='k', linewidths=0.5, label='校正集')
        axes[1, 0].scatter(test_pred, test_residuals, color='green', alpha=0.7,
                           edgecolors='k', linewidths=0.5, label='预测集')
        axes[1, 0].axhline(y=0, color='r', linestyle='--', alpha=0.8, linewidth=2)
        axes[1, 0].set_xlabel('预测湿度 (%)', fontsize=12)
        axes[1, 0].set_ylabel('残差 (%)', fontsize=12)
        axes[1, 0].set_title('残差分析', fontsize=13, fontweight='bold')
        axes[1, 0].grid(alpha=0.3, linestyle='--')
        axes[1, 0].legend()

        # 添加残差统计
        train_res_mean = np.mean(train_residuals)
        train_res_std = np.std(train_residuals)
        test_res_mean = np.mean(test_residuals)
        test_res_std = np.std(test_residuals)

        axes[1, 0].text(0.05, 0.95,
                        f'校正集残差:\n均值={train_res_mean:.3f}\n标准差={train_res_std:.3f}',
                        transform=axes[1, 0].transAxes,
                        bbox=dict(facecolor='lightblue', alpha=0.8, boxstyle='round,pad=0.5'),
                        fontsize=9,
                        verticalalignment='top')

        axes[1, 0].text(0.05, 0.75,
                        f'预测集残差:\n均值={test_res_mean:.3f}\n标准差={test_res_std:.3f}',
                        transform=axes[1, 0].transAxes,
                        bbox=dict(facecolor='lightgreen', alpha=0.8, boxstyle='round,pad=0.5'),
                        fontsize=9,
                        verticalalignment='top')

        # 4. 特征重要性
        feat_names = self.combined_data.columns[:-1]
        importance = self.model.feature_importances_
        sorted_idx = np.argsort(importance)[::-1]

        # 获取显示名称
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

        # 只显示前15个最重要的特征
        max_features = min(15, len(feat_names))
        if max_features > 0:
            colors = plt.cm.Oranges(np.linspace(0.5, 1, max_features))

            bars = axes[1, 1].bar(range(max_features), importance[sorted_idx][:max_features], color=colors)
            axes[1, 1].set_xticks(range(max_features))
            axes[1, 1].set_xticklabels([display_names[i] for i in sorted_idx[:max_features]],
                                       rotation=45, ha='right', fontsize=9)
            axes[1, 1].set_xlabel('特征', fontsize=12)
            axes[1, 1].set_ylabel('重要性得分', fontsize=12)
            axes[1, 1].set_title(f'特征重要性 (Top {max_features})', fontsize=13, fontweight='bold')
            axes[1, 1].grid(alpha=0.3, axis='y', linestyle='--')

            # 在柱子上添加数值
            for i, rect in enumerate(bars):
                height = rect.get_height()
                if height > 0.001:  # 降低阈值以显示更多特征
                    axes[1, 1].text(rect.get_x() + rect.get_width() / 2., height,
                                    f'{height:.3f}', ha='center', va='bottom', fontsize=8)
        else:
            axes[1, 1].text(0.5, 0.5, '无特征数据', ha='center', va='center', fontsize=12)
            axes[1, 1].set_title('特征重要性', fontsize=13, fontweight='bold')

        plt.suptitle(f'随机森林模型分析 (K-S方法划分，校正集:预测集={self.split_ratio}:{1 - self.split_ratio})',
                     fontsize=14, fontweight='bold', y=1.02)
        plt.tight_layout()
        plt.savefig('rf_analysis_ks_split.jpg', dpi=300, bbox_inches='tight', facecolor='white')
        print("分析图表已保存到 rf_analysis_ks_split.jpg")
        plt.show()

    def predict(self, feature_values):
        """使用训练好的模型进行预测"""
        if self.model is None:
            raise ValueError("模型尚未训练，请先调用 train() 方法")

        if len(feature_values) != len(self.combined_data.columns) - 1:
            raise ValueError(
                f"输入特征数量不匹配，预期 {len(self.combined_data.columns) - 1}，实际 {len(feature_values)}")

        if isinstance(feature_values, list):
            feature_values = np.array(feature_values).reshape(1, -1)

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
        n_estimators=500,  # 决策树数量
        selected_features=selected_feats,
        split_ratio=0.8,  # 校正集比例
        random_seed=42
    )

    try:
        # 训练模型并分析
        train_r2, train_rmse, test_r2, test_rmse = rf.train()

        print("\n" + "=" * 60)
        print("模型训练完成！")
        print("=" * 60)
        print(f"校正集: R² = {train_r2:.4f}, RMSE = {train_rmse:.4f}")
        print(f"预测集: R² = {test_r2:.4f}, RMSE = {test_rmse:.4f}")

        # 可选：进行预测示例
        # 注意：需要提供正确数量的特征值
        # if rf.combined_data is not None:
        #     feature_count = len(rf.combined_data.columns) - 1
        #     print(f"\n模型需要 {feature_count} 个特征值进行预测")
        #     # 示例：使用第一个样本的特征进行预测
        #     sample_features = rf.X_train.iloc[0].values
        #     predicted_humidity = rf.predict(sample_features)
        #     actual_humidity = rf.y_train.iloc[0]
        #     print(f"示例预测 - 实际值: {actual_humidity:.2f}%, 预测值: {predicted_humidity:.2f}%")

    except Exception as e:
        print(f"训练过程中出现错误: {e}")
        import traceback

        traceback.print_exc()