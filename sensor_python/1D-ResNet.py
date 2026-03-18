import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os
import glob
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader, random_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score, mean_squared_error


# 1D-ResNet核心模块
class ResidualBlock(nn.Module):
    """一维残差块：包含两个1D卷积层+跳跃连接"""

    def __init__(self, in_channels, out_channels, stride=1):
        super(ResidualBlock, self).__init__()
        # 第一个卷积层
        self.conv1 = nn.Conv1d(
            in_channels=in_channels,
            out_channels=out_channels,
            kernel_size=3,
            stride=stride,
            padding=1,
            bias=False
        )
        self.bn1 = nn.BatchNorm1d(out_channels)
        self.relu = nn.ReLU(inplace=True)

        # 第二个卷积层（不改变尺寸）
        self.conv2 = nn.Conv1d(
            in_channels=out_channels,
            out_channels=out_channels,
            kernel_size=3,
            stride=1,
            padding=1,
            bias=False
        )
        self.bn2 = nn.BatchNorm1d(out_channels)

        # 跳跃连接：若输入输出通道数不同，用1x1卷积调整维度
        self.downsample = None
        if stride != 1 or in_channels != out_channels:
            self.downsample = nn.Sequential(
                nn.Conv1d(in_channels, out_channels, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm1d(out_channels)
            )

    def forward(self, x):
        residual = x  # 保存输入用于跳跃连接

        # 第一个卷积块
        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        # 第二个卷积块
        out = self.conv2(out)
        out = self.bn2(out)

        # 调整跳跃连接维度（若需要）
        if self.downsample is not None:
            residual = self.downsample(residual)

        # 残差连接：输出+输入（跳跃连接）
        out += residual
        out = self.relu(out)
        return out


class ResNet1D(nn.Module):
    """1D-ResNet模型：用于传感器时序特征预测湿度"""

    def __init__(self, input_channels=1, num_blocks=[2, 2, 2], num_features=None, num_classes=1):
        super(ResNet1D, self).__init__()
        self.in_channels = 64  # 初始通道数

        # 初始卷积层：将输入特征映射到64通道
        self.conv1 = nn.Conv1d(
            in_channels=input_channels,
            out_channels=64,
            kernel_size=7,
            stride=2,
            padding=3,
            bias=False
        )
        self.bn1 = nn.BatchNorm1d(64)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool1d(kernel_size=3, stride=2, padding=1)

        # 堆叠残差块（3个阶段）
        self.layer1 = self._make_layer(64, num_blocks[0], stride=1)
        self.layer2 = self._make_layer(128, num_blocks[1], stride=2)
        self.layer3 = self._make_layer(256, num_blocks[2], stride=2)

        # 全局平均池化
        self.avgpool = nn.AdaptiveAvgPool1d(1)

        # 全连接层：输出湿度预测值
        self.fc = nn.Linear(256, num_classes)

    def _make_layer(self, out_channels, num_blocks, stride):
        """构建残差块序列"""
        strides = [stride] + [1] * (num_blocks - 1)  # 仅第一个块可能改变尺寸
        layers = []
        for stride in strides:
            layers.append(ResidualBlock(self.in_channels, out_channels, stride))
            self.in_channels = out_channels  # 更新输入通道数
        return nn.Sequential(*layers)

    def forward(self, x):
        # 输入形状：(batch_size, input_channels, seq_len)
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)

        x = self.avgpool(x)  # 输出形状：(batch_size, 256, 1)
        x = torch.flatten(x, 1)  # 展平为(batch_size, 256)

        x = self.fc(x)  # 输出湿度预测值：(batch_size, 1)
        return x


# 数据加载与预处理（遵循原文件协议）
class SensorDataset(Dataset):
    """传感器数据集：加载*_feature.txt文件并转换为模型输入格式"""

    def __init__(self, data_directory, selected_features=None, scaler=None):
        self.data_directory = data_directory
        self.selected_features = selected_features
        self.samples = []  # 存储(特征序列, 湿度值)
        self.feature_count = None  # 特征数量校验
        self.scaler = scaler if scaler is not None else StandardScaler()

        self._load_data()
        self._fit_scaler()

    def _load_data(self):
        """加载所有特征文件，遵循原协议（首行湿度，后续特征）"""
        feature_files = glob.glob(os.path.join(self.data_directory, "*_feature.txt"))
        print(f"找到 {len(feature_files)} 个特征文件")

        for file_path in feature_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]

                # 校验数据行数
                if len(lines) < 2:
                    print(f"跳过 {os.path.basename(file_path)}：有效行数不足")
                    continue

                # 解析湿度值（首行）
                try:
                    humidity = float(lines[0])
                    if not (0 <= humidity <= 100):
                        print(f"跳过 {os.path.basename(file_path)}：湿度值超出0-100范围")
                        continue
                except ValueError:
                    print(f"跳过 {os.path.basename(file_path)}：首行非有效湿度值")
                    continue

                # 解析特征值（第2行及以后）
                features = []
                for line in lines[1:]:
                    try:
                        features.append(float(line))
                    except ValueError:
                        print(f"警告：{os.path.basename(file_path)} 含非数值特征，已跳过")
                        break

                # 特征数量一致性校验
                if not features:
                    continue
                if self.feature_count is None:
                    self.feature_count = len(features)
                    print(f"确定特征数量：{self.feature_count}")
                elif len(features) != self.feature_count:
                    print(
                        f"跳过 {os.path.basename(file_path)}：特征数量不符（实际{len(features)}，预期{self.feature_count}）")
                    continue

                # 筛选指定特征
                if self.selected_features is not None:
                    selected_idx = [int(f.split('_')[1]) - 1 for f in self.selected_features]
                    features = [features[i] for i in selected_idx if 0 <= i < len(features)]

                self.samples.append((np.array(features), humidity))

            except Exception as e:
                print(f"处理 {file_path} 出错：{e}")
                continue

        if not self.samples:
            raise ValueError("未加载到有效数据")
        print(f"成功加载 {len(self.samples)} 个样本")

    def _fit_scaler(self):
        """拟合特征标准化器"""
        features = np.array([s[0] for s in self.samples])
        self.scaler.fit(features)

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        """返回标准化后的特征序列（形状：[1, seq_len]）和湿度值"""
        features, humidity = self.samples[idx]
        features_scaled = self.scaler.transform(features.reshape(1, -1)).flatten()
        # 转换为1D卷积输入格式：[通道数=1, 序列长度=特征数]
        return torch.tensor(features_scaled, dtype=torch.float32).unsqueeze(0), torch.tensor(humidity,
                                                                                             dtype=torch.float32)


# 模型训练与评估
class SensorResNetTrainer:
    def __init__(self, data_dir, selected_features=None, epochs=50, batch_size=32, lr=0.001):
        self.data_dir = data_dir
        self.selected_features = selected_features
        self.epochs = epochs
        self.batch_size = batch_size
        self.lr = lr
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"使用设备：{self.device}")

        # 加载数据集并划分训练/验证集
        self.dataset = SensorDataset(data_dir, selected_features)
        self.train_size = int(0.8 * len(self.dataset))
        self.val_size = len(self.dataset) - self.train_size
        self.train_dataset, self.val_dataset = random_split(
            self.dataset, [self.train_size, self.val_size]
        )

        # 数据加载器
        self.train_loader = DataLoader(self.train_dataset, batch_size=batch_size, shuffle=True)
        self.val_loader = DataLoader(self.val_dataset, batch_size=batch_size, shuffle=False)

        # 初始化模型、损失函数、优化器
        input_channels = 1
        num_features = len(self.dataset.samples[0][0])
        self.model = ResNet1D(input_channels, num_features=num_features).to(self.device)
        self.criterion = nn.MSELoss()  # 回归任务：均方误差
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr)

    def train(self):
        """训练模型并记录训练/验证指标"""
        train_losses = []
        val_losses = []
        val_r2_scores = []

        for epoch in range(self.epochs):
            # 训练阶段
            self.model.train()
            train_loss = 0.0
            for features, humidity in self.train_loader:
                features, humidity = features.to(self.device), humidity.to(self.device).unsqueeze(1)

                # 前向传播
                outputs = self.model(features)
                loss = self.criterion(outputs, humidity)

                # 反向传播与优化
                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()

                train_loss += loss.item() * features.size(0)

            # 验证阶段
            self.model.eval()
            val_loss = 0.0
            all_preds = []
            all_labels = []
            with torch.no_grad():
                for features, humidity in self.val_loader:
                    features, humidity = features.to(self.device), humidity.to(self.device).unsqueeze(1)
                    outputs = self.model(features)
                    loss = self.criterion(outputs, humidity)
                    val_loss += loss.item() * features.size(0)

                    all_preds.extend(outputs.cpu().numpy())
                    all_labels.extend(humidity.cpu().numpy())

            # 计算平均损失与R²分数
            train_loss_avg = train_loss / self.train_size
            val_loss_avg = val_loss / self.val_size
            val_r2 = r2_score(all_labels, all_preds)

            train_losses.append(train_loss_avg)
            val_losses.append(val_loss_avg)
            val_r2_scores.append(val_r2)

            print(f"Epoch {epoch + 1}/{self.epochs}")
            print(f"  训练损失：{train_loss_avg:.4f}")
            print(f"  验证损失：{val_loss_avg:.4f}")
            print(f"  验证R²：{val_r2:.4f}")

        # 保存模型
        torch.save(self.model.state_dict(), "sensor_resnet1d_model.pth")
        print("模型已保存为：sensor_resnet1d_model.pth")

        # 绘制训练曲线
        self._plot_metrics(train_losses, val_losses, val_r2_scores)

        # 评估最终性能
        self._evaluate_final()

    def _plot_metrics(self, train_losses, val_losses, val_r2):
        """绘制训练/验证损失与R²曲线"""
        # 配置支持中文和上标符号的字体
        plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题

        plt.figure(figsize=(12, 5))

        # 损失曲线
        plt.subplot(1, 2, 1)
        plt.plot(train_losses, label='训练损失')
        plt.plot(val_losses, label='验证损失')
        plt.xlabel('Epoch')
        plt.ylabel('MSE损失')
        plt.title('训练与验证损失曲线')
        plt.legend()

        # R²曲线（将标题中的“R²”改为“R^2”，避免直接使用上标符号）
        plt.subplot(1, 2, 2)
        plt.plot(val_r2, label='验证R^2分数', color='green')  # 这里用 R^2 替代 R²
        plt.xlabel('Epoch')
        plt.ylabel('R^2')  # 用 R^2 替代 R²
        plt.title('验证集R^2曲线')  # 用 R^2 替代 R²
        plt.legend()

        plt.tight_layout()
        plt.savefig('resnet_training_metrics.png')
        plt.show()

    def _evaluate_final(self):
        """最终评估：绘制预测vs实际值与残差图"""
        # 配置支持中文和上标符号的字体
        plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题

        self.model.eval()
        all_preds = []
        all_labels = []
        with torch.no_grad():
            for features, humidity in self.val_loader:
                features = features.to(self.device)
                outputs = self.model(features).cpu().numpy()
                all_preds.extend(outputs)
                all_labels.extend(humidity.numpy())

        # 计算指标
        rmse = np.sqrt(mean_squared_error(all_labels, all_preds))
        r2 = r2_score(all_labels, all_preds)
        print(f"\n最终评估指标：")
        print(f"  RMSE：{rmse:.4f}")
        print(f"  R^2分数：{r2:.4f}")  # 用 R^2 替代 R²

        # 绘制预测vs实际值
        plt.figure(figsize=(12, 5))

        plt.subplot(1, 2, 1)
        plt.scatter(all_preds, all_labels, alpha=0.6)
        plt.plot([min(all_labels), max(all_labels)], [min(all_labels), max(all_labels)], 'r--')
        plt.xlabel('预测湿度')
        plt.ylabel('实际湿度')
        plt.title(f'预测vs实际值 (R^2={r2:.4f})')  # 用 R^2 替代 R²

        # 绘制残差图
        residuals = np.array(all_labels) - np.array(all_preds).flatten()
        plt.subplot(1, 2, 2)
        plt.scatter(all_preds, residuals, alpha=0.6)
        plt.axhline(y=0, color='r', linestyle='--')
        plt.xlabel('预测湿度')
        plt.ylabel('残差')
        plt.title(f'残差分布 (RMSE={rmse:.4f})')

        plt.tight_layout()
        plt.savefig('resnet_prediction_analysis.png')
        plt.show()


# 主函数
def main():
    data_dir = "D:\\Desktop\\sensor_python\\data_output"  # 替换为你的数据目录

    # 可选：指定特征（与原PLS代码兼容）
    selected_features = [
        'feature_1', 'feature_2', 'feature_6', 'feature_9', 'feature_11',
        'feature_16', 'feature_17', 'feature_19', 'feature_15', 'feature_18'
    ]

    try:
        # 初始化并训练模型
        trainer = SensorResNetTrainer(
            data_dir=data_dir,
            selected_features=selected_features,
            epochs=50,
            batch_size=32,
            lr=0.001
        )
        print("开始训练1D-ResNet模型...")
        trainer.train()

        print("\n分析完成！生成文件：")
        print("- sensor_resnet1d_model.pth：模型权重文件")
        print("- resnet_training_metrics.png：训练指标曲线")
        print("- resnet_prediction_analysis.png：预测分析图")

    except Exception as e:
        print(f"运行出错：{e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()