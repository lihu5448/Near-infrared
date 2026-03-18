import os
import glob
import numpy as np
import warnings
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split, KFold, cross_val_score, GridSearchCV
from sklearn.ensemble import RandomForestRegressor
from sklearn.cross_decomposition import PLSRegression
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.preprocessing import StandardScaler
from sklearn.exceptions import ConvergenceWarning

# 忽略收敛警告（PLS迭代可能出现）
warnings.filterwarnings('ignore', category=ConvergenceWarning)
warnings.filterwarnings('ignore', category=UserWarning)


# 数据加载（优化：添加特征标准化选项、增强日志）
def load_data(data_dir, selected_features=None, scale_features=True):
    """
    加载特征数据并预处理
    :param data_dir: 数据目录
    :param selected_features: 选中的特征列表
    :param scale_features: 是否标准化特征
    :return: 划分后的训练/验证集（X_train, X_val, y_train, y_val）
    """
    samples = []
    feature_count = None
    feature_files = glob.glob(os.path.join(data_dir, "*_feature.txt"))

    if not feature_files:
        raise FileNotFoundError(f"在 {data_dir} 中未找到任何特征文件")
    print(f"找到 {len(feature_files)} 个特征文件")

    for file_idx, file_path in enumerate(feature_files, 1):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]

            # 基础校验
            if len(lines) < 2:
                print(f"[{file_idx}/{len(feature_files)}] 跳过 {os.path.basename(file_path)}：行数不足")
                continue

            # 解析湿度值（目标变量）
            try:
                humidity = float(lines[0])
                if not (0 <= humidity <= 100):
                    print(
                        f"[{file_idx}/{len(feature_files)}] 跳过 {os.path.basename(file_path)}：湿度值({humidity})超出0-100范围")
                    continue
            except ValueError:
                print(f"[{file_idx}/{len(feature_files)}] 跳过 {os.path.basename(file_path)}：湿度值非数值")
                continue

            # 解析特征
            features = []
            invalid_feature = False
            for line in lines[1:]:
                try:
                    features.append(float(line))
                except ValueError:
                    print(
                        f"[{file_idx}/{len(feature_files)}] 警告：{os.path.basename(file_path)} 包含非数值特征，跳过该文件")
                    invalid_feature = True
                    break

            if invalid_feature or not features:
                continue

            # 特征数量一致性校验
            if feature_count is None:
                feature_count = len(features)
                print(f"检测到特征维度：{feature_count}")
            elif len(features) != feature_count:
                print(
                    f"[{file_idx}/{len(feature_files)}] 跳过 {os.path.basename(file_path)}：特征数量不符（期望{feature_count}，实际{len(features)}）")
                continue

            # 筛选指定特征
            if selected_features:
                try:
                    selected_idx = [int(f.split('_')[1]) - 1 for f in selected_features]
                    # 校验索引有效性
                    selected_idx = [i for i in selected_idx if 0 <= i < len(features)]
                    if not selected_idx:
                        print(
                            f"[{file_idx}/{len(feature_files)}] 警告：{os.path.basename(file_path)} 无有效选中特征，使用全部特征")
                    else:
                        features = [features[i] for i in selected_idx]
                except Exception as e:
                    print(f"[{file_idx}/{len(feature_files)}] 特征筛选失败：{e}，使用全部特征")

            samples.append((np.array(features), humidity))

        except Exception as e:
            print(f"[{file_idx}/{len(feature_files)}] 处理 {file_path} 出错：{e}")
            continue

    if not samples:
        raise ValueError("未加载到任何有效样本数据")

    # 转换为数组并标准化
    X = np.array([s[0] for s in samples])
    y = np.array([s[1] for s in samples])

    print(f"\n数据加载完成：有效样本数={len(X)}，特征维度={X.shape[1]}")

    # 特征标准化
    if scale_features:
        scaler = StandardScaler()
        X = scaler.fit_transform(X)
        print("已对特征进行标准化处理")

    # 划分训练集/验证集（8:2）
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, shuffle=True
    )

    print(f"训练集：{X_train.shape[0]} 样本 | 验证集：{X_val.shape[0]} 样本")
    return X_train, X_val, y_train, y_val


# 模型评估与可视化（优化：增加误差分布、完善图表标注）
def evaluate_model(y_true, y_pred, model_name="PLS+RF堆叠模型"):
    """
    评估模型性能并生成可视化图表
    :param y_true: 真实值
    :param y_pred: 预测值
    :param model_name: 模型名称（用于图表标注）
    """
    # 设置中文字体
    plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams['figure.dpi'] = 100
    plt.rcParams['savefig.dpi'] = 300

    # 计算评估指标
    r2 = r2_score(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = np.mean(np.abs(y_true - y_pred))
    mre = np.mean(np.abs((y_true - y_pred) / (y_true + 1e-8))) * 100  # 平均相对误差(%)

    # 打印评估结果
    print(f"\n{model_name} 性能评估：")
    print(f"  决定系数 (R²)：{r2:.4f}")
    print(f"  均方根误差 (RMSE)：{rmse:.4f}")
    print(f"  平均绝对误差 (MAE)：{mae:.4f}")
    print(f"  平均相对误差 (MRE)：{mre:.2f}%")

    # 创建2x1子图：预测对比 + 误差分布
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 10))

    # 1. 预测值vs真实值散点图
    ax1.scatter(y_pred, y_true, alpha=0.6, s=30, c='#2E86AB', edgecolors='white', linewidth=0.5)
    # 绘制理想预测线
    min_val = min(y_true.min(), y_pred.min())
    max_val = max(y_true.max(), y_pred.max())
    ax1.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='理想预测线')
    ax1.set_xlabel('预测湿度 (%)', fontsize=12)
    ax1.set_ylabel('实际湿度 (%)', fontsize=12)
    ax1.set_title(f'{model_name} - 预测值 vs 实际值\nR²={r2:.4f}, RMSE={rmse:.4f}', fontsize=14, pad=10)
    ax1.grid(True, alpha=0.3, linestyle='-')
    ax1.legend()

    # 2. 误差分布直方图
    errors = y_pred - y_true
    ax2.hist(errors, bins=20, color='#A23B72', alpha=0.7, edgecolor='white', linewidth=0.5)
    ax2.axvline(x=0, color='red', linestyle='--', linewidth=2, label='无误差线')
    ax2.set_xlabel('预测误差 (预测值 - 实际值)', fontsize=12)
    ax2.set_ylabel('样本数量', fontsize=12)
    ax2.set_title(f'{model_name} - 预测误差分布\nMAE={mae:.4f}, MRE={mre:.2f}%', fontsize=14, pad=10)
    ax2.grid(True, alpha=0.3, linestyle='-', axis='y')
    ax2.legend()

    plt.tight_layout()
    plt.savefig(f'{model_name}_results.png', bbox_inches='tight')
    plt.show()

    return {'r2': r2, 'rmse': rmse, 'mae': mae, 'mre': mre}


# 自动选择PLS最优主成分数
def select_best_pls_components(X, y, max_components=None, cv=5):
    """
    通过交叉验证选择PLS最优主成分数
    :param X: 特征矩阵
    :param y: 目标变量
    :param max_components: 最大主成分数（默认取特征维度）
    :param cv: 交叉验证折数
    :return: 最优主成分数、各成分数的R²得分
    """
    if max_components is None:
        max_components = X.shape[1]
    max_components = min(max_components, X.shape[1])

    if max_components < 1:
        return 1, {}

    component_scores = {}
    print(f"\n正在通过{cv}折交叉验证选择PLS最优主成分数（1~{max_components}）：")

    for n in range(1, max_components + 1):
        pls = PLSRegression(n_components=n, scale=True)
        scores = cross_val_score(pls, X, y, cv=cv, scoring='r2')
        mean_score = scores.mean()
        component_scores[n] = mean_score
        print(f"  主成分数={n}：平均R²={mean_score:.4f} (±{scores.std():.4f})")

    # 选择最优主成分数（R²最高）
    best_n = max(component_scores, key=component_scores.get)
    best_score = component_scores[best_n]
    print(f"\n最优PLS主成分数：{best_n}（R²={best_score:.4f}）")

    return best_n, component_scores


# 优化随机森林超参数（可选）
def optimize_rf_hyperparams(X, y, cv=5):
    """
    网格搜索优化随机森林超参数
    :param X: 特征矩阵
    :param y: 目标变量
    :param cv: 交叉验证折数
    :return: 最优参数的随机森林模型
    """
    param_grid = {
        'n_estimators': [50, 100, 150],
        'max_depth': [5, 10, None],
        'max_features': ['sqrt', 'log2', None],
        'min_samples_split': [2, 5, 10]
    }

    rf = RandomForestRegressor(random_state=42, n_jobs=-1)
    grid_search = GridSearchCV(
        estimator=rf,
        param_grid=param_grid,
        cv=cv,
        scoring='r2',
        n_jobs=-1,
        verbose=1
    )

    print("\n开始网格搜索优化随机森林超参数...")
    grid_search.fit(X, y)

    print(f"\n随机森林最优参数：{grid_search.best_params_}")
    print(f"最优交叉验证R²：{grid_search.best_score_:.4f}")

    return grid_search.best_estimator_


# 主函数（堆叠模型：PLS基模型 + RF元模型）
def main():
    # 配置参数
    DATA_DIR = "D:\\Desktop\\sensor_python\\data_output"
    # SELECTED_FEATURES = [
    #     'feature_1', 'feature_2', 'feature_6', 'feature_9', 'feature_11',
    #     'feature_16', 'feature_17', 'feature_19', 'feature_15', 'feature_18'
    # ]
    SELECTED_FEATURES = None
    N_FOLDS = 5  # 交叉验证折数
    OPTIMIZE_RF = True  # 是否优化随机森林超参数

    try:
        # 1. 加载并预处理数据
        print("=" * 60)
        print("开始加载数据...")
        X_train, X_val, y_train, y_val = load_data(
            data_dir=DATA_DIR,
            selected_features=SELECTED_FEATURES,
            scale_features=True
        )

        # 2. 定义第一层基模型（多参数PLS）
        print("\n" + "=" * 60)
        print("训练第一层基模型（PLS）...")

        # 为不同PLS模型选择最优主成分数
        pls_components = []
        max_comp_candidates = [1 , 2 , 3, 4, 5, 6, 7, 8, 9, 10]  # 不同的最大主成分数候选
        for i, max_comp in enumerate(max_comp_candidates):
            best_n, _ = select_best_pls_components(
                X=X_train,
                y=y_train,
                max_components=max_comp,
                cv=N_FOLDS
            )
            pls_components.append(best_n)

        # 构建多个PLS基模型（不同主成分数）
        base_models = [
            PLSRegression(n_components=pls_components[0], scale=True),
            PLSRegression(n_components=pls_components[1], scale=True),
            PLSRegression(n_components=pls_components[2], scale=True),
            PLSRegression(n_components=pls_components[3], scale=True),
            PLSRegression(n_components=pls_components[4], scale=True),
            PLSRegression(n_components=pls_components[5], scale=True),
            PLSRegression(n_components=pls_components[6], scale=True),
            PLSRegression(n_components=pls_components[7], scale=True),
            PLSRegression(n_components=pls_components[8], scale=True),
            PLSRegression(n_components=pls_components[9], scale=True)
        ]
        print(f"\n基模型数量：{len(base_models)}")
        for i, model in enumerate(base_models):
            print(f"  PLS基模型 {i + 1}：主成分数={model.n_components}")

        # 3. 生成元特征（通过KFold交叉验证）
        kf = KFold(n_splits=N_FOLDS, shuffle=True, random_state=42)
        meta_features_train = np.zeros((X_train.shape[0], len(base_models)))
        meta_features_val = np.zeros((X_val.shape[0], len(base_models)))

        for idx, model in enumerate(base_models):
            print(f"\n训练基模型 {idx + 1}/{len(base_models)}...")
            # 对训练集进行交叉验证，生成元特征
            for train_idx, val_idx in kf.split(X_train):
                X_tr, X_vl = X_train[train_idx], X_train[val_idx]
                y_tr = y_train[train_idx]

                model.fit(X_tr, y_tr)
                meta_features_train[val_idx, idx] = model.predict(X_vl).ravel()

            # 用全量训练集训练，预测验证集元特征
            model.fit(X_train, y_train)
            meta_features_val[:, idx] = model.predict(X_val).ravel()

        print(f"\n元特征维度 - 训练集：{meta_features_train.shape} | 验证集：{meta_features_val.shape}")

        # 4. 训练第二层RF元模型（可选超参数优化）
        print("\n" + "=" * 60)
        print("训练第二层随机森林元模型...")
        if OPTIMIZE_RF:
            meta_model = optimize_rf_hyperparams(meta_features_train, y_train, cv=N_FOLDS)
        else:
            # 使用默认参数的随机森林
            meta_model = RandomForestRegressor(
                n_estimators=500,
                max_depth=None,
                random_state=42,
                n_jobs=-1
            )
            meta_model.fit(meta_features_train, y_train)

        # 5. 模型预测与评估
        print("\n" + "=" * 60)
        print("模型预测与评估...")
        y_pred = meta_model.predict(meta_features_val).ravel()
        metrics = evaluate_model(y_val, y_pred, model_name="PLS+RF堆叠模型")

        # 输出特征重要性（随机森林特有）
        print("\n" + "=" * 60)
        print("随机森林元模型特征重要性（对应各PLS基模型）：")
        for i, imp in enumerate(meta_model.feature_importances_):
            print(f"  PLS基模型 {i + 1}：{imp:.4f}")

        print("\n" + "=" * 60)
        print("所有流程执行完成！")

    except Exception as e:
        print(f"\n程序执行出错：{e}")
        raise


if __name__ == "__main__":
    main()