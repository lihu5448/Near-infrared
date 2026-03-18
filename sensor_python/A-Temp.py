import os
import glob
import numpy as np
from sklearn.model_selection import train_test_split, KFold, GridSearchCV
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import r2_score, mean_squared_error


# 数据加载与预处理
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
                if not (0 <= humidity <= 90):
                    print(f"跳过 {os.path.basename(file_path)}：湿度值超出合理范围")
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
                    features.append(np.nan)
                    print(f"警告：{os.path.basename(file_path)} 含非数值特征")

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

    # 预处理
    X = SimpleImputer(strategy='median').fit_transform(X)
    X_scaled = StandardScaler().fit_transform(X)

    # 划分数据集
    bins = np.linspace(y.min(), y.max(), 5)
    y_binned = np.digitize(y, bins)
    X_train, X_val, y_train, y_val = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42, stratify=y_binned
    )

    return X_train, X_val, y_train, y_val


# 仅输出R²和RMSE的评估函数
def evaluate(y_true, y_pred, model_name):
    r2 = r2_score(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    print(f"{model_name} 性能：")
    print(f"  R²: {r2:.4f}")
    print(f"  RMSE: {rmse:.4f}\n")
    return r2


def main():
    data_dir = "D:\\Desktop\\sensor_python\\data_output"
    selected_features = [
        'feature_1', 'feature_2', 'feature_6', 'feature_9', 'feature_11',
        'feature_16', 'feature_17', 'feature_19', 'feature_15', 'feature_18'
    ]

    X_train, X_val, y_train, y_val = load_data(data_dir, selected_features)
    print(f"训练集样本数：{X_train.shape[0]}，验证集样本数：{X_val.shape[0]}\n")

    # 基模型
    base_models = [
        #RandomForestRegressor(n_estimators=600, max_depth=8, min_samples_leaf=4, random_state=42),
        RandomForestRegressor(n_estimators=600, random_state=42),
        #GradientBoostingRegressor(n_estimators=600, learning_rate=0.08, max_depth=5, subsample=0.8, random_state=43)
    ]
    model_names = ["随机森林", "梯度提升树"]

    # 生成元特征
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    meta_features_train = np.zeros((X_train.shape[0], len(base_models)))
    meta_features_val = np.zeros((X_val.shape[0], len(base_models)))

    # 训练基模型并评估
    base_r2 = []
    for i, (model, name) in enumerate(zip(base_models, model_names)):
        for train_idx, val_idx in kf.split(X_train):
            X_tr, X_vl = X_train[train_idx], X_train[val_idx]
            y_tr = y_train[train_idx]
            model.fit(X_tr, y_tr)
            meta_features_train[val_idx, i] = model.predict(X_vl)
        model.fit(X_train, y_train)
        val_pred = model.predict(X_val)
        r2 = evaluate(y_val, val_pred, name)
        base_r2.append(r2)
        meta_features_val[:, i] = val_pred

    # 元模型
    meta_model = GridSearchCV(Ridge(random_state=44), {'alpha': [0.5, 1, 5, 10]}, cv=3, scoring='r2')
    meta_model.fit(meta_features_train, y_train)
    print(f"最优元模型参数：{meta_model.best_params_}\n")

    # 最终预测与评估
    y_pred = meta_model.predict(meta_features_val)
    stack_r2 = evaluate(y_val, y_pred, "堆叠模型（随机森林+梯度提升）")

    # 性能对比 summary
    print("性能对比 summary：")
    for name, r2 in zip(model_names, base_r2):
        print(f"  {name} R²: {r2:.4f}")
    print(f"  堆叠模型 R²: {stack_r2:.4f}")


if __name__ == "__main__":
    main()