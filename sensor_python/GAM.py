import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from sklearn.metrics import r2_score, mean_squared_error
from pygam import LinearGAM, s
import csv
import os
import glob


class SensorGAM:
    def __init__(self, data_directory, n_splines=5):
        self.data_directory = data_directory
        self.combined_data = None
        self.processed_file = "combined_sensor_data.csv"
        self.expected_feature_count = None
        self.model = None
        self.n_splines = n_splines
        self.used_features = None  # 记录实际使用的特征数量

    def load_sensor_data(self):
        """加载传感器数据（逻辑不变）"""
        all_data = []
        feature_files = glob.glob(os.path.join(self.data_directory, "*_feature.txt"))
        print(f"找到 {len(feature_files)} 个特征文件")

        for file_path in feature_files:
            try:
                filename = os.path.basename(file_path)
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]

                if len(lines) < 2:
                    print(f"跳过文件 {filename}，有效行数不足（至少2行）")
                    continue

                # 解析湿度值
                try:
                    humidity_value = float(lines[0])
                    if not (0 <= humidity_value <= 100):
                        print(f"跳过文件 {filename}，湿度值 {humidity_value} 超出合理范围（0-100）")
                        continue
                except ValueError:
                    print(f"跳过文件 {filename}，第一行非有效湿度值: {lines[0]}")
                    continue

                # 解析特征值
                feature_values = []
                for i, line in enumerate(lines[1:]):
                    try:
                        feature_values.append(float(line))
                    except ValueError:
                        print(f"警告: 文件 {filename} 第{i + 2}行含非数值数据，已跳过")

                if not feature_values:
                    print(f"跳过文件 {filename}，无有效特征值")
                    continue

                # 特征数量校验
                if self.expected_feature_count is None:
                    self.expected_feature_count = len(feature_values)
                    print(f"确定预期特征数量: {self.expected_feature_count}")
                else:
                    if len(feature_values) != self.expected_feature_count:
                        print(
                            f"跳过文件 {filename}，特征数不符（实际: {len(feature_values)}, 预期: {self.expected_feature_count}）")
                        continue

                data_row = feature_values + [humidity_value]
                all_data.append(data_row)
                print(f"处理文件: {filename}, 湿度: {humidity_value}, 特征数: {len(feature_values)}")

            except Exception as e:
                print(f"处理文件 {file_path} 出错: {e}")
                continue

        if not all_data:
            raise ValueError("未加载到有效数据")

        # 创建DataFrame
        n_features = len(all_data[0]) - 1
        feature_columns = [f'feature_{i + 1}' for i in range(n_features)]
        self.combined_data = pd.DataFrame(all_data, columns=feature_columns + ['humidity'])
        self.used_features = n_features  # 记录全部特征数量
        print(f"将使用全部 {n_features} 个特征建模")

        # 数据校验与缺失值处理
        non_numeric_cols = self.combined_data.select_dtypes(exclude=['number']).columns
        if not non_numeric_cols.empty:
            print(f"警告：非数值列可能影响结果: {non_numeric_cols.tolist()}")

        if self.combined_data.isnull().sum().sum() > 0:
            print("\n检测到缺失值，用列均值填充")
            self.combined_data = self.combined_data.fillna(self.combined_data.mean())

        # 保存合并数据
        self.combined_data.to_csv(self.processed_file, index=False, encoding='GBK')
        print(f"\n合并数据保存到: {self.processed_file}")
        print(f"数据形状: {self.combined_data.shape} (样本数: {self.combined_data.shape[0]})")

        return self.combined_data

    def perform_gam(self):
        """执行GAM分析（使用全部特征）"""
        if self.combined_data is None:
            self.load_sensor_data()

        df = self.combined_data
        X = df.iloc[:, :-1].values
        y = df['humidity'].values
        n_features = self.used_features  # 使用全部特征

        print(f"\nGAM分析设置:")
        print(f"自变量 (特征) 形状: {X.shape}")
        print(f"因变量 (湿度) 形状: {y.shape}")
        print(f"样条函数节点数: {self.n_splines}")
        print(f"使用全部 {n_features} 个特征建模")

        # 构建模型项（显式创建每个特征的光滑项）
        terms = s(0, n_splines=self.n_splines)  # 初始项
        for i in range(1, n_features):
            terms += s(i, n_splines=self.n_splines)  # 逐项累加，确保索引连续

        # 训练模型（使用全部特征）
        self.model = LinearGAM(terms).fit(X, y)

        # 模型分析
        gam_analyzer = GAMAnalysis(df.iloc[:, :-1], df['humidity'], self.model, n_features)
        results = gam_analyzer.run_analysis()

        return results


class GAMAnalysis:
    def __init__(self, X, y, model, n_features):
        self.X = X
        self.y = y
        self.model = model
        self.feature_names = X.columns.tolist()
        self.n_features = n_features  # 全部特征数量

    def run_analysis(self):
        """运行GAM分析"""
        X_np = self.X.values
        y_pred = self.model.predict(X_np)

        # 相关系数矩阵
        data_matrix = pd.concat([self.X, self.y], axis=1)
        correlation_matrix = data_matrix.corr()
        correlation_matrix.to_csv("sensor_correlation_matrix.csv", encoding='GBK')
        print("相关系数矩阵已保存到: sensor_correlation_matrix.csv")

        # 保存结果
        self._save_results()

        # 绘制图表
        self._plot_results(y_pred)

        return {
            'r2': r2_score(self.y, y_pred),
            'rmse': np.sqrt(mean_squared_error(self.y, y_pred)),
            'model': self.model
        }

    def _get_partial_dependence(self, term_idx):
        """获取偏依赖值（确保term为有效整数索引）"""
        term_int = int(term_idx)  # 强制转换为整数
        if not (0 <= term_int < self.n_features):
            raise ValueError(f"特征索引 {term_int} 超出范围（0至{self.n_features - 1}）")

        # 生成该特征的取值网格
        XX = self.model.generate_X_grid(term=term_int)
        # 调用偏依赖计算（兼容返回值格式）
        result = self.model.partial_dependence(term=term_int, X=XX)
        return result if not isinstance(result, tuple) else result[0]

    def _save_results(self):
        """计算全部特征的重要性"""
        importance_scores = []
        y_total_var = np.var(self.y)  # 目标变量总方差

        for i in range(self.n_features):
            # 获取偏依赖值
            pdep = self._get_partial_dependence(term_idx=i)
            # 用偏依赖方差作为重要性指标
            feature_var = np.var(pdep)
            importance_scores.append(feature_var / y_total_var)  # 归一化

        # 保存结果
        result_data = [['feature', 'importance_score', 'importance_rank']]
        sorted_idx = np.argsort(importance_scores)[::-1]  # 按重要性排序

        for rank, idx in enumerate(sorted_idx, 1):
            result_data.append([
                self.feature_names[idx],
                f'{importance_scores[idx]:.6f}',
                rank
            ])

        with open("sensor_gam_results.csv", "w", newline="", encoding='GBK') as f:
            writer = csv.writer(f)
            writer.writerows(result_data)

        print("GAM分析结果已保存到: sensor_gam_results.csv")

        # 打印前10个重要特征（避免输出过长）
        print("\nGAM特征重要性（前10名，基于边际影响方差）:")
        print(f"{'特征':<15} {'重要性得分':<12} {'排名'}")
        print("-" * 35)
        for rank, idx in enumerate(sorted_idx[:10], 1):  # 仅显示前10
            print(f"{self.feature_names[idx]:<15} {importance_scores[idx]:<12.6f} {rank}")

    def _plot_results(self, y_pred):
        """可视化模型结果"""
        plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Micro Hei', 'Heiti TC']
        plt.rcParams['axes.unicode_minus'] = False

        residuals = self.y - y_pred
        # 最多显示4个重要特征的非线性图
        n_plots = 1 + min(4, self.n_features)
        fig, axes = plt.subplots(n_plots, 1, figsize=(12, 4 * n_plots))
        axes = [axes] if n_plots == 1 else axes

        # 1. 预测值vs实际值
        ax = axes[0]
        ax.scatter(y_pred, self.y, alpha=0.7, color='blue', s=50)
        y_min = min(self.y.min(), y_pred.min())
        y_max = max(self.y.max(), y_pred.max())
        ax.plot([y_min, y_max], [y_min, y_max], 'r--', alpha=0.8)
        ax.set_xlabel('预测湿度')
        ax.set_ylabel('实际湿度')
        ax.set_title('GAM模型预测效果（全部特征）')
        ax.grid(alpha=0.3)

        # 模型性能指标
        r2 = r2_score(self.y, y_pred)
        rmse = np.sqrt(mean_squared_error(self.y, y_pred))
        ax.text(0.05, 0.95, f'R² = {r2:.4f}\nRMSE = {rmse:.4f}',
                transform=ax.transAxes, fontsize=10,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

        # 2. 重要特征的非线性关系（前4名）
        # 计算重要性得分
        importance_scores = []
        for i in range(self.n_features):
            pdep = self._get_partial_dependence(term_idx=i)
            importance_scores.append(np.var(pdep) / np.var(self.y))
        sorted_idx = np.argsort(importance_scores)[::-1]
        top_features = sorted_idx[:4]

        for i, feature_idx in enumerate(top_features, 1):
            if i >= len(axes):
                break

            feature_name = self.feature_names[feature_idx]
            ax = axes[i]

            # 绘制非线性曲线
            term_int = int(feature_idx)
            XX = self.model.generate_X_grid(term=term_int)
            pdep = self._get_partial_dependence(term_idx=term_int)
            ax.plot(XX[:, term_int], pdep, 'b-', linewidth=2, label='非线性关系')
            ax.axhline(y=0, color='gray', linestyle='--')  # 基准线
            ax.set_xlabel(feature_name)
            ax.set_ylabel('对湿度的边际影响')
            ax.set_title(f'{feature_name}与湿度的非线性关系')
            ax.grid(alpha=0.3)
            ax.legend()

        plt.tight_layout()
        plt.savefig('sensor_gam_analysis.jpg', dpi=300, bbox_inches='tight')
        plt.show()

        # 打印性能指标
        print(f"\n模型性能:")
        print(f"R²分数: {r2:.4f}")
        print(f"RMSE: {rmse:.4f}")


def main():
    data_dir = "D:\\Desktop\\sensor_python\\data_output"  # 替换为你的数据目录

    try:
        # 若特征数量极多，可减小n_splines（如3-5）避免过拟合
        sensor_analyzer = SensorGAM(data_dir, n_splines=5)
        print("开始GAM分析（使用全部特征）...")
        results = sensor_analyzer.perform_gam()

        print("\n分析完成！")
        print("生成的文件:")
        print("- combined_sensor_data.csv: 合并后的数据")
        print("- sensor_correlation_matrix.csv: 相关系数矩阵")
        print("- sensor_gam_results.csv: 全部特征的重要性得分")
        print("- sensor_gam_analysis.jpg: 模型评估与非线性关系图")

    except Exception as e:
        print(f"分析出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()