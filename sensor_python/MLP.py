import os
import glob
import numpy as np
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPRegressor
from sklearn.metrics import r2_score, mean_squared_error


# 数据加载与标准化
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

            # 解析湿度
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

    # 标准化
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    return X_train_scaled, X_val_scaled, y_train, y_val


# 评估与可视化
def evaluate(y_true, y_pred, model):
    r2 = r2_score(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    print(f"浅层MLP评估：")
    print(f"  R^2：{r2:.4f} | RMSE：{rmse:.4f}")

    # 预测vs实际值
    plt.figure(figsize=(12, 5))
    plt.subplot(1, 2, 1)
    plt.scatter(y_pred, y_true, alpha=0.6)
    plt.plot([y_true.min(), y_true.max()], [y_true.min(), y_true.max()], 'r--')
    plt.xlabel('预测湿度')
    plt.ylabel('实际湿度')
    plt.title(f'预测vs实际值 (R^2={r2:.4f})')

    # 训练损失曲线
    plt.subplot(1, 2, 2)
    plt.plot(model.loss_curve_, label='训练损失')
    plt.xlabel('迭代次数')
    plt.ylabel('损失值')
    plt.title('MLP训练损失')
    plt.legend()

    plt.tight_layout()
    plt.savefig('mlp_results.png')
    plt.show()


# 主函数
def main():
    data_dir = "D:\\Desktop\\sensor_python\\data_output"  # 替换为你的数据目录
    selected_features = [
        'feature_1', 'feature_2', 'feature_6', 'feature_9', 'feature_11',
        'feature_16', 'feature_17', 'feature_19', 'feature_15', 'feature_18'
    ]

    X_train, X_val, y_train, y_val = load_data(data_dir, selected_features)

    # 训练模型（浅层网络避免过拟合）
    model = MLPRegressor(
        hidden_layer_sizes=(32, 16),
        activation='relu',
        solver='adam',
        learning_rate_init=0.001,
        max_iter=500,
        early_stopping=True,
        random_state=42,
        verbose=False
    )
    model.fit(X_train, y_train)

    # 评估
    y_pred = model.predict(X_val)
    evaluate(y_val, y_pred, model)


if __name__ == "__main__":
    main()