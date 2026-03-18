import os
import glob
import numpy as np
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import r2_score, mean_squared_error


# 数据加载（同前，复用逻辑）
def load_data(data_dir, selected_features=None):
    samples = []
    feature_count = None
    feature_files = glob.glob(os.path.join(data_dir, "*_feature.txt"))
    print(f"找到 {len(feature_files)} 个特征文件")

    for file_path in feature_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]

            if len(lines) < 2:
                print(f"跳过 {os.path.basename(file_path)}：行数不足")
                continue

            # 解析湿度值
            try:
                humidity = float(lines[0])
                if not (0 <= humidity <= 100):
                    print(f"跳过 {os.path.basename(file_path)}：湿度值无效")
                    continue
            except ValueError:
                print(f"跳过 {os.path.basename(file_path)}：湿度值非数值")
                continue

            # 解析特征
            features = []
            for line in lines[1:]:
                try:
                    features.append(float(line))
                except ValueError:
                    print(f"警告：{os.path.basename(file_path)} 含非数值特征")
                    break

            if not features:
                continue

            # 特征数量校验
            if feature_count is None:
                feature_count = len(features)
                print(f"特征数量：{feature_count}")
            elif len(features) != feature_count:
                print(f"跳过 {os.path.basename(file_path)}：特征数量不符")
                continue

            # 筛选特征
            if selected_features:
                selected_idx = [int(f.split('_')[1]) - 1 for f in selected_features]
                features = [features[i] for i in selected_idx if 0 <= i < len(features)]

            samples.append((np.array(features), humidity))
        except Exception as e:
            print(f"处理 {file_path} 出错：{e}")
            continue

    if not samples:
        raise ValueError("无有效数据")
    X = np.array([s[0] for s in samples])
    y = np.array([s[1] for s in samples])
    return train_test_split(X, y, test_size=0.2, random_state=42)


# 评估与可视化
def evaluate(y_true, y_pred, model_name):
    plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]
    plt.rcParams["axes.unicode_minus"] = False

    r2 = r2_score(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    print(f"{model_name} 评估：")
    print(f"  R^2：{r2:.4f} | RMSE：{rmse:.4f}")

    # 预测vs实际值
    plt.figure(figsize=(8, 6))
    plt.scatter(y_pred, y_true, alpha=0.6)
    plt.plot([y_true.min(), y_true.max()], [y_true.min(), y_true.max()], 'r--')
    plt.xlabel('预测湿度')
    plt.ylabel('实际湿度')
    plt.title(f'{model_name} 预测vs实际值 (R^2={r2:.4f})')
    plt.tight_layout()
    plt.savefig(f'{model_name.lower().replace(" ", "_")}_results.png')
    plt.show()


# 主函数（梯度提升随机森林：先用随机森林，再用GBDT拟合残差）
def main():
    data_dir = "D:\\Desktop\\sensor_python\\data_output"
    selected_features = [
        'feature_1', 'feature_2', 'feature_6', 'feature_9', 'feature_11',
        'feature_16', 'feature_17', 'feature_19', 'feature_15', 'feature_18'
    ]

    X_train, X_val, y_train, y_val = load_data(data_dir, selected_features)

    # 第一步：训练基础随机森林
    rf = RandomForestRegressor(n_estimators=500, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)

    # 计算残差（实际值 - 随机森林预测值）
    y_train_residual = y_train - rf.predict(X_train)
    y_val_residual = y_val - rf.predict(X_val)

    # 第二步：用GBDT拟合残差
    gbdt = GradientBoostingRegressor(n_estimators=500, learning_rate=0.1, random_state=42)
    gbdt.fit(X_train, y_train_residual)

    # 最终预测：随机森林预测 + GBDT残差预测
    y_pred = rf.predict(X_val) + gbdt.predict(X_val)

    # 评估
    evaluate(y_val, y_pred, "梯度提升随机森林（GBRF）")


if __name__ == "__main__":
    main()