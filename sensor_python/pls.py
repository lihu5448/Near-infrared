import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from sklearn import preprocessing
from numpy.matlib import repmat
import csv
import os
import glob


class SensorPLS:
    def __init__(self, data_directory, polynomial=1):
        self.data_directory = data_directory
        self.polynomial = polynomial
        self.combined_data = None
        self.processed_file = "combined_sensor_data.csv"
        self.expected_feature_count = None  # 用于特征数量一致性校验

    def load_sensor_data(self):
        """加载所有传感器特征文件并合并，增加数据校验"""
        all_data = []

        # 查找所有的特征文件
        feature_files = glob.glob(os.path.join(self.data_directory, "*_feature.txt"))
        print(f"找到 {len(feature_files)} 个特征文件")

        for file_path in feature_files:
            try:
                filename = os.path.basename(file_path)

                # 读取特征数据
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]

                if len(lines) < 2:
                    print(f"跳过文件 {filename}，有效数据行数不足（至少需要2行）")
                    continue

                # 解析湿度值（第一行）并校验合理性
                try:
                    humidity_value = float(lines[0])
                    # 假设湿度范围为0-100%，超出范围视为异常
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

                # 检查特征值是否为空
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

                # 创建数据行：特征 + 湿度值
                data_row = feature_values + [humidity_value]
                all_data.append(data_row)
                print(f"处理文件: {filename}, 湿度: {humidity_value}, 特征数: {len(feature_values)}")

            except Exception as e:
                print(f"处理文件 {file_path} 时出错: {e}")
                continue

        if not all_data:
            raise ValueError("没有成功加载任何有效数据")

        # 创建DataFrame并设置列名
        n_features = len(all_data[0]) - 1
        feature_columns = [f'feature_{i + 1}' for i in range(n_features)]
        columns = feature_columns + ['humidity']

        self.combined_data = pd.DataFrame(all_data, columns=columns)

        # 数据类型校验
        non_numeric_cols = self.combined_data.select_dtypes(exclude=['number']).columns
        if not non_numeric_cols.empty:
            print(f"警告：以下列包含非数值数据，可能影响分析结果：{non_numeric_cols.tolist()}")

        # 缺失值统计
        missing_values = self.combined_data.isnull().sum()
        if missing_values.sum() > 0:
            print("\n缺失值统计:")
            for col, count in missing_values.items():
                if count > 0:
                    print(f"  {col}: {count} 个缺失值")

        # 保存合并后的数据
        self.combined_data.to_csv(self.processed_file, index=False, encoding='GBK')
        print(f"\n合并数据保存到: {self.processed_file}")
        print(f"数据形状: {self.combined_data.shape} (样本数: {self.combined_data.shape[0]}, 特征数: {self.combined_data.shape[1]-1})")

        # 显示完整数据统计
        print("\n数据统计概要:")
        print(self.combined_data.describe(include='all').transpose())  # 转置后更易读

        # 显示湿度值分布详情
        humidity_unique = sorted(self.combined_data['humidity'].unique())
        print(f"\n湿度值分布:")
        print(f"  范围: {self.combined_data['humidity'].min():.2f} - {self.combined_data['humidity'].max():.2f}")
        print(f"  均值: {self.combined_data['humidity'].mean():.2f} ± {self.combined_data['humidity'].std():.2f}")
        print(f"   unique值: {humidity_unique}")

        return self.combined_data

    def perform_pls(self):
        """执行PLS回归分析"""
        if self.combined_data is None:
            self.load_sensor_data()

        df = self.combined_data

        # 检查是否存在缺失值，若有则填充（避免PLS计算出错）
        if df.isnull().sum().sum() > 0:
            print("\n检测到缺失值，使用列均值填充")
            df = df.fillna(df.mean())

        # 准备数据：特征为自变量，湿度为因变量
        X = df.iloc[:, :-1]  # 所有特征列（去掉最后一列湿度）
        y = df.iloc[:, -1:]  # 湿度列（最后一列）

        print(f"\nPLS分析设置:")
        print(f"自变量 (特征) 形状: {X.shape}")
        print(f"因变量 (湿度) 形状: {y.shape}")
        print(f"特征名称: {list(X.columns)}")

        # 执行PLS
        pls_model = PLSAnalysis(X, y, polynomial=self.polynomial)
        results = pls_model.run_analysis()

        return results


class PLSAnalysis:
    def __init__(self, X, y, polynomial=1):
        self.X = X.values if isinstance(X, pd.DataFrame) else X
        self.y = y.values if isinstance(y, pd.DataFrame) else y
        self.polynomial = polynomial
        self.n_samples, self.n_features = self.X.shape
        self.n_targets = self.y.shape[1] if len(self.y.shape) > 1 else 1
        self.feature_names = X.columns.tolist() if isinstance(X, pd.DataFrame) else [f'feature_{i + 1}' for i in
                                                                                     range(self.n_features)]

        if len(self.y.shape) == 1:
            self.y = self.y.reshape(-1, 1)

        print(f"PLS分析初始化:")
        print(f"样本数: {self.n_samples}, 特征数: {self.n_features}, 目标变量数: {self.n_targets}")

    def run_analysis(self):
        """运行完整的PLS分析"""
        # 数据标准化
        X_scaled = preprocessing.scale(self.X)
        y_scaled = preprocessing.scale(self.y)

        # 计算相关系数矩阵
        data_matrix = np.column_stack((self.X, self.y))
        df_combined = pd.DataFrame(data_matrix, columns=self.feature_names + ['humidity'])
        correlation_matrix = df_combined.corr()
        correlation_matrix.to_csv("sensor_correlation_matrix.csv", encoding='GBK')
        print("相关系数矩阵已保存到: sensor_correlation_matrix.csv")

        # PLS算法
        x0, y0, num, xishu, ch0, xish, sol = self._pls_algorithm(X_scaled, y_scaled)

        # 保存结果
        self._save_results(sol)

        # 绘制图表
        self._plot_results(x0, y0, xishu, ch0, xish)

        return {
            'coefficients': sol,
            'xishu': xishu,
            'intercept': ch0,
            'feature_importance': xish
        }

    def _pls_algorithm(self, e0, f0):
        """PLS核心算法"""
        n = self.n_features
        m = self.n_targets
        num = self.n_samples

        x0 = self.X
        y0 = self.y

        mu_x = np.mean(self.X, axis=0)
        mu_y = np.mean(self.y, axis=0)
        sig_x = np.std(self.X, axis=0)
        sig_y = np.std(self.y, axis=0)

        # 处理标准差为0的情况（避免除零错误）
        sig_x[sig_x == 0] = 1e-10
        sig_y[sig_y == 0] = 1e-10

        chg = np.identity(n)
        w = np.zeros([n, n])
        w_star = np.zeros([n, n])
        t = np.zeros([num, n])

        ss = []
        Q_h2 = []
        press_i = np.zeros(num)
        press = np.zeros(n)
        flag = False
        r = min(n, num - 1)  # 成分数不能超过样本数-1

        print(f"\n开始PLS计算，最大成分数: {r}")

        for i in range(r):
            # 计算特征值和特征向量
            matrix = e0.T @ f0 @ f0.T @ e0
            matrix = (matrix + matrix.T) / 2  # 确保矩阵对称

            try:
                val, vec = np.linalg.eig(matrix)
                val = np.real(val)
                vec = np.real(vec)
            except np.linalg.LinAlgError:
                print(f"成分 {i+1} 计算特征值失败，终止PLS迭代")
                r = i
                break

            max_idx = np.argmax(val)
            w[:, i] = vec[:, max_idx]
            w_star[:, i] = chg @ w[:, i]
            t[:, i] = e0 @ w[:, i]

            # 计算alpha并修正维度
            alpha_numerator = e0.T @ t[:, i]
            alpha_denominator = t[:, i].T @ t[:, i] + 1e-10  # 避免除零
            alpha = alpha_numerator / alpha_denominator

            w_col = w[:, i:i + 1]
            alpha_col = alpha.reshape(-1, 1)
            chg = chg @ (np.identity(n) - w_col @ alpha_col.T)

            # 更新残差矩阵
            e0 = e0 - t[:, i:i + 1] @ alpha_col.T

            # 计算回归系数
            try:
                if i == 0:
                    beta = np.linalg.pinv(t[:, :i + 1].reshape(-1, 1)) @ f0
                else:
                    beta = np.linalg.pinv(t[:, :i + 1]) @ f0
            except np.linalg.LinAlgError:
                print(f"成分 {i+1} 计算回归系数失败，终止PLS迭代")
                r = i
                break

            # 计算残差和交叉验证
            cancha = f0 - t[:, :i + 1] @ beta
            ss.append(np.sum(cancha **2))

            # 交叉验证计算
            for j in range(num):
                t1 = np.delete(t[:, :i + 1], j, axis=0)
                f1 = np.delete(f0, j, axis=0)

                try:
                    if i == 0:
                        beta1 = np.linalg.pinv(t1.reshape(-1, 1)) @ f1
                    else:
                        beta1 = np.linalg.pinv(t1) @ f1
                except np.linalg.LinAlgError:
                    press_i[j] = 0
                    continue

                she_t = t[:, :i + 1][j:j + 1, :]
                she_f = f0[j:j + 1, :]
                cancha_pred = she_f - she_t @ beta1
                press_i[j] = np.sum(cancha_pred** 2)

            press[i] = np.sum(press_i)

            # Q²准则判断
            if i > 0:
                Q_h2_val = 1 - press[i] / ss[i - 1]
                Q_h2.append(Q_h2_val)
                print(f'成分 {i + 1}: Q² = {Q_h2_val:.4f}')

                if Q_h2_val < 0.0975:
                    r = i
                    flag = True
                    print(f'选择成分数量: {r} (基于Q²准则)')
                    break
            else:
                Q_h2.append(1.0)

        if not flag:
            r = min(r, n - 1)
            print(f'使用成分数量: {r}')

        # 计算最终模型参数
        try:
            if r == 0:
                beta_z = np.linalg.pinv(t[:, :r + 1].reshape(-1, 1)) @ f0
            else:
                beta_z = np.linalg.pinv(t[:, :r + 1]) @ f0
        except np.linalg.LinAlgError:
            print("计算最终回归系数失败，使用最小二乘替代")
            beta_z = np.linalg.lstsq(t[:, :r + 1], f0, rcond=None)[0]

        xishu = w_star[:, :r + 1] @ beta_z

        # 计算原始尺度的系数
        ch0 = []
        for i in range(m):
            ch0_value = float(mu_y[i] - np.sum((mu_x / sig_x) * sig_y[i] * xishu[:, i]))
            ch0.append(ch0_value)

        xish = np.zeros([n, m])
        for i in range(m):
            xish[:, i] = (xishu[:, i] / sig_x) * sig_y[i]

        sol = np.column_stack([np.array(ch0), xish.T]).T

        return x0, y0, num, xishu, ch0, xish, sol

    def _save_results(self, sol):
        """保存结果到CSV文件"""
        target_names = ['humidity']

        # 构建结果矩阵
        result_data = []
        result_data.append(['intercept'] + [f'{sol[0, i]:.6f}' for i in range(self.n_targets)])

        for i in range(self.n_features):
            row = [self.feature_names[i]]
            for j in range(self.n_targets):
                row.append(f'{sol[i + 1, j]:.6f}')
            result_data.append(row)

        # 保存到CSV
        with open("sensor_pls_results.csv", "w", newline="", encoding='GBK') as f:
            writer = csv.writer(f)
            writer.writerow(['Variable'] + target_names)
            writer.writerows(result_data)

        print("PLS回归结果已保存到: sensor_pls_results.csv")

        # 打印系数
        print("\nPLS回归系数:")
        print(f"{'变量':<15} {'系数':<10}")
        print("-" * 25)
        print(f"{'截距':<15} {sol[0, 0]:.6f}")
        for i in range(self.n_features):
            print(f"{self.feature_names[i]:<15} {sol[i + 1, 0]:.6f}")

    def _plot_results(self, x0, y0, xishu, ch0, xish):
        """绘制结果图表"""
        plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Micro Hei', 'Heiti TC']
        plt.rcParams['axes.unicode_minus'] = False

        # 计算预测值
        ch0_rep = repmat(ch0, self.n_samples, 1)
        y_hat = ch0_rep + x0 @ xish

        fig, axes = plt.subplots(2, 2, figsize=(15, 12))

        # 1. 预测 vs 实际值
        axes[0, 0].scatter(y_hat, y0, alpha=0.7, color='blue', s=50)
        y_min = min(y0.min(), y_hat.min())
        y_max = max(y0.max(), y_hat.max())
        axes[0, 0].plot([y_min, y_max], [y_min, y_max], 'r--', alpha=0.8, linewidth=2)
        axes[0, 0].set_xlabel('预测湿度')
        axes[0, 0].set_ylabel('实际湿度')
        axes[0, 0].set_title('预测值 vs 实际值')
        axes[0, 0].grid(True, alpha=0.3)

        r2 = self._calculate_r2(y_hat.flatten(), y0.flatten())
        rmse = np.sqrt(np.mean((y_hat.flatten() - y0.flatten()) **2))
        axes[0, 0].text(0.05, 0.95, f'R² = {r2:.4f}\nRMSE = {rmse:.4f}',
                        transform=axes[0, 0].transAxes, fontsize=12,
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

        # 2. 残差图
        residuals = y0.flatten() - y_hat.flatten()
        axes[0, 1].scatter(y_hat, residuals, alpha=0.7, color='green', s=50)
        axes[0, 1].axhline(y=0, color='red', linestyle='--', linewidth=2)
        axes[0, 1].set_xlabel('预测湿度')
        axes[0, 1].set_ylabel('残差')
        axes[0, 1].set_title('残差图')
        axes[0, 1].grid(True, alpha=0.3)

        # 3. 特征重要性（系数绝对值）
        feature_importance = np.abs(xish.flatten())
        sorted_idx = np.argsort(feature_importance)[::-1]
        sorted_importance = feature_importance[sorted_idx]
        sorted_names = [self.feature_names[i] for i in sorted_idx]

        bars = axes[1, 0].bar(range(len(sorted_importance)), sorted_importance,
                              color='skyblue', alpha=0.7)
        axes[1, 0].set_xlabel('特征')
        axes[1, 0].set_ylabel('系数绝对值')
        axes[1, 0].set_title('特征重要性排序')
        axes[1, 0].set_xticks(range(len(sorted_names)))
        axes[1, 0].set_xticklabels(sorted_names, rotation=45, ha='right')

        # 添加数值标签
        for bar, importance in zip(bars, sorted_importance):
            axes[1, 0].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                            f'{importance:.3f}', ha='center', va='bottom', fontsize=8)

        # 4. 系数符号图
        coefficients = xish.flatten()[sorted_idx]
        colors = ['red' if coef < 0 else 'blue' for coef in coefficients]
        bars2 = axes[1, 1].bar(range(len(coefficients)), coefficients,
                               color=colors, alpha=0.7)
        axes[1, 1].axhline(y=0, color='black', linestyle='-')
        axes[1, 1].set_xlabel('特征')
        axes[1, 1].set_ylabel('系数值')
        axes[1, 1].set_title('特征系数（红色负相关，蓝色正相关）')
        axes[1, 1].set_xticks(range(len(sorted_names)))
        axes[1, 1].set_xticklabels(sorted_names, rotation=45, ha='right')

        # 添加数值标签
        for bar, coef in zip(bars2, coefficients):
            axes[1, 1].text(bar.get_x() + bar.get_width() / 2,
                            bar.get_height() + (0.01 if coef >= 0 else -0.01),
                            f'{coef:.3f}', ha='center',
                            va='bottom' if coef >= 0 else 'top', fontsize=8)

        plt.tight_layout()
        plt.savefig('sensor_pls_analysis.jpg', dpi=300, bbox_inches='tight')
        plt.show()

        print(f"\n模型性能:")
        print(f"R²分数: {r2:.4f}")
        print(f"RMSE: {rmse:.4f}")

    def _calculate_r2(self, y_pred, y_true):
        """计算R²分数"""
        ss_total = np.sum((y_true - np.mean(y_true)) **2)
        if ss_total == 0:
            return 0.0  # 所有真实值相同，R²无意义
        ss_residual = np.sum((y_true - y_pred)** 2)
        return 1 - ss_residual / ss_total


def main():
    """主函数"""
    # 设置数据目录路径（可根据实际情况修改）
    data_dir = "D:\\Desktop\\sensor_python\\data_output"

    try:
        # 创建传感器PLS分析器
        sensor_analyzer = SensorPLS(data_dir, polynomial=1)

        # 执行分析
        print("开始处理传感器数据...")
        results = sensor_analyzer.perform_pls()

        print("\n分析完成！")
        print("生成的文件:")
        print("- combined_sensor_data.csv: 合并后的数据")
        print("- sensor_correlation_matrix.csv: 相关系数矩阵")
        print("- sensor_pls_results.csv: PLS回归结果")
        print("- sensor_pls_analysis.jpg: 分析图表")

    except Exception as e:
        print(f"分析过程中出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()