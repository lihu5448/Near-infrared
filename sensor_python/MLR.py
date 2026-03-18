import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from sklearn import preprocessing
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_squared_error
from numpy.matlib import repmat
import csv
import os
import glob


class SensorMLR:
    def __init__(self, data_directory):
        self.data_directory = data_directory
        self.combined_data = None
        self.processed_file = "combined_sensor_data.csv"
        self.expected_feature_count = None  # 特征数量一致性校验
        self.model = None  # 存储MLR模型

    def load_sensor_data(self):
        """加载所有传感器特征文件并合并，保持与原代码一致的数据校验逻辑"""
        all_data = []

        # 查找所有特征文件
        feature_files = glob.glob(os.path.join(self.data_directory, "*_feature.txt"))
        print(f"找到 {len(feature_files)} 个特征文件")

        for file_path in feature_files:
            try:
                filename = os.path.basename(file_path)

                # 读取并清洗数据行
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]

                if len(lines) < 2:
                    print(f"跳过文件 {filename}，有效数据行数不足（至少需要2行）")
                    continue

                # 解析湿度值（第一行）并校验范围
                try:
                    humidity_value = float(lines[0])
                    if not (0 <= humidity_value <= 100):
                        print(f"跳过文件 {filename}，湿度值 {humidity_value} 超出合理范围（0-100）")
                        continue
                except ValueError:
                    print(f"跳过文件 {filename}，第一行不是有效的湿度值: {lines[0]}")
                    continue

                # 解析特征值（从第二行开始）
                feature_values = []
                for i, line in enumerate(lines[1:]):
                    try:
                        value = float(line)
                        feature_values.append(value)
                    except ValueError:
                        print(f"警告: 文件 {filename} 第{i + 2}行包含非数值数据，已跳过该行特征")

                if not feature_values:
                    print(f"跳过文件 {filename}，无有效特征值")
                    continue

                # 特征数量一致性校验
                if self.expected_feature_count is None:
                    self.expected_feature_count = len(feature_values)
                    print(f"确定预期特征数量: {self.expected_feature_count}")
                else:
                    if len(feature_values) != self.expected_feature_count:
                        print(f"跳过文件 {filename}，特征数量不符（实际: {len(feature_values)}, 预期: {self.expected_feature_count}）")
                        continue

                # 组合特征与湿度值
                data_row = feature_values + [humidity_value]
                all_data.append(data_row)
                print(f"处理文件: {filename}, 湿度: {humidity_value}, 特征数: {len(feature_values)}")

            except Exception as e:
                print(f"处理文件 {file_path} 时出错: {e}")
                continue

        if not all_data:
            raise ValueError("没有成功加载任何有效数据")

        # 创建DataFrame
        n_features = len(all_data[0]) - 1
        feature_columns = [f'feature_{i + 1}' for i in range(n_features)]
        columns = feature_columns + ['humidity']
        self.combined_data = pd.DataFrame(all_data, columns=columns)

        # 数据校验
        non_numeric_cols = self.combined_data.select_dtypes(exclude=['number']).columns
        if not non_numeric_cols.empty:
            print(f"警告：以下列包含非数值数据，可能影响分析结果：{non_numeric_cols.tolist()}")

        # 缺失值处理
        missing_values = self.combined_data.isnull().sum()
        if missing_values.sum() > 0:
            print("\n检测到缺失值，使用列均值填充")
            self.combined_data = self.combined_data.fillna(self.combined_data.mean())

        # 保存合并数据
        self.combined_data.to_csv(self.processed_file, index=False, encoding='GBK')
        print(f"\n合并数据保存到: {self.processed_file}")
        print(f"数据形状: {self.combined_data.shape} (样本数: {self.combined_data.shape[0]}, 特征数: {self.combined_data.shape[1]-1})")

        # 数据统计概要
        print("\n数据统计概要:")
        print(self.combined_data.describe(include='all').transpose())

        # 湿度分布详情
        humidity_unique = sorted(self.combined_data['humidity'].unique())
        print(f"\n湿度值分布:")
        print(f"  范围: {self.combined_data['humidity'].min():.2f} - {self.combined_data['humidity'].max():.2f}")
        print(f"  均值: {self.combined_data['humidity'].mean():.2f} ± {self.combined_data['humidity'].std():.2f}")
        print(f"  unique值: {humidity_unique}")

        return self.combined_data

    def perform_mlr(self):
        """执行多元线性回归分析"""
        if self.combined_data is None:
            self.load_sensor_data()

        df = self.combined_data

        # 划分自变量（特征）和因变量（湿度）
        X = df.iloc[:, :-1]  # 所有特征列
        y = df.iloc[:, -1]   # 湿度列（因变量）

        print(f"\nMLR分析设置:")
        print(f"自变量 (特征) 形状: {X.shape}")
        print(f"因变量 (湿度) 形状: {y.shape}")
        print(f"特征名称: {list(X.columns)}")

        # 初始化并训练MLR模型
        self.model = LinearRegression()
        self.model.fit(X, y)

        # 模型结果分析
        mlr_analyzer = MLRAnalysis(X, y, self.model)
        results = mlr_analyzer.run_analysis()

        return results


class MLRAnalysis:
    def __init__(self, X, y, model):
        self.X = X  # 特征数据（DataFrame）
        self.y = y  # 目标变量（Series）
        self.model = model  # 训练好的MLR模型
        self.n_samples, self.n_features = X.shape
        self.feature_names = X.columns.tolist()

    def run_analysis(self):
        """运行完整的MLR分析流程"""
        # 计算预测值
        y_pred = self.model.predict(self.X)

        # 计算相关系数矩阵（特征与目标变量）
        data_matrix = pd.concat([self.X, self.y], axis=1)
        correlation_matrix = data_matrix.corr()
        correlation_matrix.to_csv("sensor_correlation_matrix.csv", encoding='GBK')
        print("相关系数矩阵已保存到: sensor_correlation_matrix.csv")

        # 保存回归结果
        self._save_results()

        # 绘制分析图表
        self._plot_results(y_pred)

        # 返回关键结果
        return {
            'coefficients': self.model.coef_,
            'intercept': self.model.intercept_,
            'r2': r2_score(self.y, y_pred),
            'rmse': np.sqrt(mean_squared_error(self.y, y_pred))
        }

    def _save_results(self):
        """保存MLR回归系数到CSV文件"""
        # 构建结果矩阵（截距 + 各特征系数）
        result_data = []
        result_data.append(['intercept', f'{self.model.intercept_:.6f}'])

        for name, coef in zip(self.feature_names, self.model.coef_):
            result_data.append([name, f'{coef:.6f}'])

        # 保存到文件
        with open("sensor_mlr_results.csv", "w", newline="", encoding='GBK') as f:
            writer = csv.writer(f)
            writer.writerow(['Variable', 'Coefficient'])  # 变量名 + 系数
            writer.writerows(result_data)

        print("MLR回归结果已保存到: sensor_mlr_results.csv")

        # 打印系数（控制台输出）
        print("\nMLR回归系数:")
        print(f"{'变量':<15} {'系数':<10}")
        print("-" * 25)
        print(f"{'截距':<15} {self.model.intercept_:.6f}")
        for name, coef in zip(self.feature_names, self.model.coef_):
            print(f"{name:<15} {coef:.6f}")

    def _plot_results(self, y_pred):
        """绘制MLR结果可视化图表"""
        plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Micro Hei', 'Heiti TC']
        plt.rcParams['axes.unicode_minus'] = False

        # 计算残差
        residuals = self.y - y_pred

        # 创建2x2图表
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))

        # 1. 预测值 vs 实际值
        axes[0, 0].scatter(y_pred, self.y, alpha=0.7, color='blue', s=50)
        y_min = min(self.y.min(), y_pred.min())
        y_max = max(self.y.max(), y_pred.max())
        axes[0, 0].plot([y_min, y_max], [y_min, y_max], 'r--', alpha=0.8, linewidth=2)
        axes[0, 0].set_xlabel('预测湿度')
        axes[0, 0].set_ylabel('实际湿度')
        axes[0, 0].set_title('预测值 vs 实际值')
        axes[0, 0].grid(True, alpha=0.3)

        # 模型性能指标（R²和RMSE）
        r2 = r2_score(self.y, y_pred)
        rmse = np.sqrt(mean_squared_error(self.y, y_pred))
        axes[0, 0].text(0.05, 0.95, f'R² = {r2:.4f}\nRMSE = {rmse:.4f}',
                        transform=axes[0, 0].transAxes, fontsize=12,
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

        # 2. 残差图（预测值 vs 残差）
        axes[0, 1].scatter(y_pred, residuals, alpha=0.7, color='green', s=50)
        axes[0, 1].axhline(y=0, color='red', linestyle='--', linewidth=2)
        axes[0, 1].set_xlabel('预测湿度')
        axes[0, 1].set_ylabel('残差（实际值-预测值）')
        axes[0, 1].set_title('残差图')
        axes[0, 1].grid(True, alpha=0.3)

        # 3. 特征重要性（系数绝对值排序）
        coef_abs = np.abs(self.model.coef_)
        sorted_idx = np.argsort(coef_abs)[::-1]  # 从大到小排序
        sorted_coef = coef_abs[sorted_idx]
        sorted_names = [self.feature_names[i] for i in sorted_idx]

        bars = axes[1, 0].bar(range(len(sorted_coef)), sorted_coef,
                              color='skyblue', alpha=0.7)
        axes[1, 0].set_xlabel('特征')
        axes[1, 0].set_ylabel('系数绝对值（重要性）')
        axes[1, 0].set_title('特征重要性排序')
        axes[1, 0].set_xticks(range(len(sorted_names)))
        axes[1, 0].set_xticklabels(sorted_names, rotation=45, ha='right')

        # 添加系数值标签
        for bar, coef in zip(bars, sorted_coef):
            axes[1, 0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                            f'{coef:.3f}', ha='center', va='bottom', fontsize=8)

        # 4. 系数符号图（正/负相关）
        coefficients = self.model.coef_[sorted_idx]
        colors = ['red' if c < 0 else 'blue' for c in coefficients]
        bars2 = axes[1, 1].bar(range(len(coefficients)), coefficients,
                               color=colors, alpha=0.7)
        axes[1, 1].axhline(y=0, color='black', linestyle='-')
        axes[1, 1].set_xlabel('特征')
        axes[1, 1].set_ylabel('系数值（正/负相关）')
        axes[1, 1].set_title('特征系数符号（红色负相关，蓝色正相关）')
        axes[1, 1].set_xticks(range(len(sorted_names)))
        axes[1, 1].set_xticklabels(sorted_names, rotation=45, ha='right')

        # 添加系数值标签
        for bar, coef in zip(bars2, coefficients):
            axes[1, 1].text(bar.get_x() + bar.get_width()/2,
                            bar.get_height() + (0.01 if coef >=0 else -0.01),
                            f'{coef:.3f}', ha='center',
                            va='bottom' if coef >=0 else 'top', fontsize=8)

        plt.tight_layout()
        plt.savefig('sensor_mlr_analysis.jpg', dpi=300, bbox_inches='tight')
        plt.show()

        # 打印模型性能
        print(f"\n模型性能:")
        print(f"R²分数: {r2:.4f}（越接近1，拟合越好）")
        print(f"RMSE: {rmse:.4f}（均方根误差，越小精度越高）")


def main():
    """主函数：运行MLR分析流程"""
    # 数据目录路径（根据实际情况修改）
    data_dir = "D:\\Desktop\\sensor_python\\data_output"

    try:
        # 创建MLR分析器实例
        sensor_analyzer = SensorMLR(data_dir)

        # 执行多元线性回归分析
        print("开始处理传感器数据（多元线性回归）...")
        results = sensor_analyzer.perform_mlr()

        print("\n分析完成！")
        print("生成的文件:")
        print("- combined_sensor_data.csv: 合并后的数据")
        print("- sensor_correlation_matrix.csv: 特征与湿度的相关系数矩阵")
        print("- sensor_mlr_results.csv: MLR回归系数表")
        print("- sensor_mlr_analysis.jpg: 分析可视化图表")

    except Exception as e:
        print(f"分析过程中出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()