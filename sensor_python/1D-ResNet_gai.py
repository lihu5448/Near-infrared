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


# 1. 多尺度卷积模块（参考多尺度特征融合论文）
class MultiScaleConv(nn.Module):
    """多尺度卷积层：并行使用不同大小的卷积核，捕捉不同时间粒度的特征"""

    def __init__(self, in_channels, out_channels):
        super(MultiScaleConv, self).__init__()
        # 不同尺寸的卷积核（1D场景下，核大小对应时间步长）
        self.conv1 = nn.Conv1d(in_channels, out_channels // 4, kernel_size=1, padding=0)  # 1步长（局部点特征）
        self.conv3 = nn.Conv1d(in_channels, out_channels // 4, kernel_size=3, padding=1)  # 3步长（短程依赖）
        self.conv5 = nn.Conv1d(in_channels, out_channels // 4, kernel_size=5, padding=2)  # 5步长（中程依赖）
        self.conv7 = nn.Conv1d(in_channels, out_channels // 4, kernel_size=7, padding=3)  # 7步长（长程依赖）
        self.bn = nn.BatchNorm1d(out_channels)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        # 并行卷积后拼接特征（融合多尺度信息）
        x1 = self.conv1(x)
        x3 = self.conv3(x)
        x5 = self.conv5(x)
        x7 = self.conv7(x)
        out = torch.cat([x1, x3, x5, x7], dim=1)  # 按通道维度拼接
        out = self.bn(out)
        return self.relu(out)


# 2. 通道注意力模块（参考CBAM论文）
class ChannelAttention(nn.Module):
    """通道注意力：突出重要特征通道的权重（如传感器中与湿度强相关的特征维度）"""

    def __init__(self, in_channels, reduction=16):
        super(ChannelAttention, self).__init__()
        self.avg_pool = nn.AdaptiveAvgPool1d(1)  # 全局平均池化
        self.max_pool = nn.AdaptiveMaxPool1d(1)  # 全局最大池化
        # 压缩-激励机制
        self.fc = nn.Sequential(
            nn.Linear(in_channels, in_channels // reduction, bias=False),
            nn.ReLU(),
            nn.Linear(in_channels // reduction, in_channels, bias=False),
            nn.Sigmoid()  # 输出通道权重（0-1）
        )

    def forward(self, x):
        b, c, _ = x.size()
        # 平均池化路径
        avg_out = self.avg_pool(x).view(b, c)
        # 最大池化路径
        max_out = self.max_pool(x).view(b, c)
        # 融合两个路径的注意力权重
        out = self.fc(avg_out + max_out).view(b, c, 1)
        return x * out  # 通道加权（逐通道相乘）


# 3. 改进的残差块（融合多尺度卷积与注意力）
class ImprovedResidualBlock(nn.Module):
    """改进残差块：多尺度卷积+通道注意力+跳跃连接"""

    def __init__(self, in_channels, out_channels, stride=1):
        super(ImprovedResidualBlock, self).__init__()
        # 第一个卷积层替换为多尺度卷积
        self.conv1 = MultiScaleConv(in_channels, out_channels)
        # 第二个卷积层保持常规1D卷积（细化特征）
        self.conv2 = nn.Conv1d(
            in_channels=out_channels,
            out_channels=out_channels,
            kernel_size=3,
            stride=stride,
            padding=1,
            bias=False
        )
        self.bn2 = nn.BatchNorm1d(out_channels)
        self.relu = nn.ReLU(inplace=True)

        # 通道注意力模块（放在卷积后，强化重要特征）
        self.ca = ChannelAttention(out_channels)

        # 跳跃连接：调整维度（若需要）
        self.downsample = None
        if stride != 1 or in_channels != out_channels:
            self.downsample = nn.Sequential(
                nn.Conv1d(in_channels, out_channels, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm1d(out_channels)
            )

    def forward(self, x):
        residual = x

        # 多尺度特征提取
        out = self.conv1(x)
        # 特征细化与注意力加权
        out = self.conv2(out)
        out = self.bn2(out)
        out = self.ca(out)  # 应用通道注意力

        # 调整跳跃连接维度
        if self.downsample is not None:
            residual = self.downsample(residual)

        # 残差连接
        out += residual
        out = self.relu(out)
        return out


# 4. 改进的1D-ResNet模型
class ImprovedResNet1D(nn.Module):
    """融合多尺度卷积与注意力机制的1D-ResNet"""

    def __init__(self, input_channels=1, num_blocks=[2, 2, 2], num_classes=1):
        super(ImprovedResNet1D, self).__init__()
        self.in_channels = 64

        # 初始卷积：先用标准卷积压缩维度，再进入多尺度模块
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

        # 堆叠改进的残差块
        self.layer1 = self._make_layer(64, num_blocks[0], stride=1)  # 输出通道64
        self.layer2 = self._make_layer(128, num_blocks[1], stride=2)  # 输出通道128（下采样）
        self.layer3 = self._make_layer(256, num_blocks[2], stride=2)  # 输出通道256（下采样）

        # 全局平均池化+全连接层
        self.avgpool = nn.AdaptiveAvgPool1d(1)
        self.fc = nn.Linear(256, num_classes)

    def _make_layer(self, out_channels, num_blocks, stride):
        strides = [stride] + [1] * (num_blocks - 1)
        layers = []
        for stride in strides:
            layers.append(ImprovedResidualBlock(self.in_channels, out_channels, stride))
            self.in_channels = out_channels
        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)

        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        x = self.fc(x)
        return x


# 数据加载部分与原代码一致（确保兼容性）
class SensorDataset(Dataset):
    def __init__(self, data_directory, selected_features=None, scaler=None):
        self.data_directory = data_directory
        self.selected_features = selected_features
        self.samples = []
        self.feature_count = None
        self.scaler = scaler if scaler is not None else StandardScaler()
        self._load_data()
        self._fit_scaler()

    def _load_data(self):
        feature_files = glob.glob(os.path.join(self.data_directory, "*_feature.txt"))
        print(f"找到 {len(feature_files)} 个特征文件")

        for file_path in feature_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]

                if len(lines) < 2:
                    print(f"跳过 {os.path.basename(file_path)}：有效行数不足")
                    continue

                try:
                    humidity = float(lines[0])
                    if not (0 <= humidity <= 100):
                        print(f"跳过 {os.path.basename(file_path)}：湿度值超出范围")
                        continue
                except ValueError:
                    print(f"跳过 {os.path.basename(file_path)}：首行非有效湿度值")
                    continue

                features = []
                for line in lines[1:]:
                    try:
                        features.append(float(line))
                    except ValueError:
                        print(f"警告：{os.path.basename(file_path)} 含非数值特征")
                        break

                if not features:
                    continue
                if self.feature_count is None:
                    self.feature_count = len(features)
                    print(f"确定特征数量：{self.feature_count}")
                elif len(features) != self.feature_count:
                    print(f"跳过 {os.path.basename(file_path)}：特征数量不符")
                    continue

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
        features = np.array([s[0] for s in self.samples])
        self.scaler.fit(features)

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        features, humidity = self.samples[idx]
        features_scaled = self.scaler.transform(features.reshape(1, -1)).flatten()
        return torch.tensor(features_scaled, dtype=torch.float32).unsqueeze(0), torch.tensor(humidity,
                                                                                             dtype=torch.float32)


# 训练器（适配改进模型，保持接口一致）
class SensorResNetTrainer:
    def __init__(self, data_dir, selected_features=None, epochs=50, batch_size=32, lr=0.001):
        self.data_dir = data_dir
        self.selected_features = selected_features
        self.epochs = epochs
        self.batch_size = batch_size
        self.lr = lr
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"使用设备：{self.device}")

        self.dataset = SensorDataset(data_dir, selected_features)
        self.train_size = int(0.8 * len(self.dataset))
        self.val_size = len(self.dataset) - self.train_size
        self.train_dataset, self.val_dataset = random_split(
            self.dataset, [self.train_size, self.val_size]
        )

        self.train_loader = DataLoader(self.train_dataset, batch_size=batch_size, shuffle=True)
        self.val_loader = DataLoader(self.val_dataset, batch_size=batch_size, shuffle=False)

        # 使用改进模型
        self.model = ImprovedResNet1D(input_channels=1).to(self.device)
        self.criterion = nn.MSELoss()
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr)

    def train(self):
        train_losses = []
        val_losses = []
        val_r2_scores = []

        for epoch in range(self.epochs):
            self.model.train()
            train_loss = 0.0
            for features, humidity in self.train_loader:
                features, humidity = features.to(self.device), humidity.to(self.device).unsqueeze(1)

                outputs = self.model(features)
                loss = self.criterion(outputs, humidity)

                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()

                train_loss += loss.item() * features.size(0)

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

            train_loss_avg = train_loss / self.train_size
            val_loss_avg = val_loss / self.val_size
            val_r2 = r2_score(all_labels, all_preds)

            train_losses.append(train_loss_avg)
            val_losses.append(val_loss_avg)
            val_r2_scores.append(val_r2)

            print(f"Epoch {epoch + 1}/{self.epochs}")
            print(f"  训练损失：{train_loss_avg:.4f}")
            print(f"  验证损失：{val_loss_avg:.4f}")
            print(f"  验证R^2：{val_r2:.4f}")

        torch.save(self.model.state_dict(), "improved_resnet1d_model.pth")
        print("改进模型已保存为：improved_resnet1d_model.pth")

        self._plot_metrics(train_losses, val_losses, val_r2_scores)
        self._evaluate_final()

    def _plot_metrics(self, train_losses, val_losses, val_r2):
        plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        plt.figure(figsize=(12, 5))
        plt.subplot(1, 2, 1)
        plt.plot(train_losses, label='训练损失')
        plt.plot(val_losses, label='验证损失')
        plt.xlabel('Epoch')
        plt.ylabel('MSE损失')
        plt.title('训练与验证损失曲线')
        plt.legend()

        plt.subplot(1, 2, 2)
        plt.plot(val_r2, label='验证R^2分数', color='green')
        plt.xlabel('Epoch')
        plt.ylabel('R^2')
        plt.title('验证集R^2曲线')
        plt.legend()

        plt.tight_layout()
        plt.savefig('improved_resnet_training_metrics.png')
        plt.show()

    def _evaluate_final(self):
        plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        self.model.eval()
        all_preds = []
        all_labels = []
        with torch.no_grad():
            for features, humidity in self.val_loader:
                features = features.to(self.device)
                outputs = self.model(features).cpu().numpy()
                all_preds.extend(outputs)
                all_labels.extend(humidity.numpy())

        rmse = np.sqrt(mean_squared_error(all_labels, all_preds))
        r2 = r2_score(all_labels, all_preds)
        print(f"\n最终评估指标：")
        print(f"  RMSE：{rmse:.4f}")
        print(f"  R^2分数：{r2:.4f}")

        plt.figure(figsize=(12, 5))
        plt.subplot(1, 2, 1)
        plt.scatter(all_preds, all_labels, alpha=0.6)
        plt.plot([min(all_labels), max(all_labels)], [min(all_labels), max(all_labels)], 'r--')
        plt.xlabel('预测湿度')
        plt.ylabel('实际湿度')
        plt.title(f'预测vs实际值 (R^2={r2:.4f})')

        residuals = np.array(all_labels) - np.array(all_preds).flatten()
        plt.subplot(1, 2, 2)
        plt.scatter(all_preds, residuals, alpha=0.6)
        plt.axhline(y=0, color='r', linestyle='--')
        plt.xlabel('预测湿度')
        plt.ylabel('残差')
        plt.title(f'残差分布 (RMSE={rmse:.4f})')

        plt.tight_layout()
        plt.savefig('improved_resnet_prediction_analysis.png')
        plt.show()


# 主函数
def main():
    data_dir = "D:\\Desktop\\sensor_python\\data_output"  # 替换为你的数据目录
    selected_features = [
        'feature_1', 'feature_2', 'feature_6', 'feature_9', 'feature_11',
        'feature_16', 'feature_17', 'feature_19', 'feature_15', 'feature_18'
    ]

    try:
        trainer = SensorResNetTrainer(
            data_dir=data_dir,
            selected_features=selected_features,
            epochs=50,
            batch_size=32,
            lr=0.001
        )
        print("开始训练改进的1D-ResNet模型...")
        trainer.train()

        print("\n分析完成！生成文件：")
        print("- improved_resnet1d_model.pth：改进模型权重文件")
        print("- improved_resnet_training_metrics.png：训练指标曲线")
        print("- improved_resnet_prediction_analysis.png：预测分析图")

    except Exception as e:
        print(f"运行出错：{e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()