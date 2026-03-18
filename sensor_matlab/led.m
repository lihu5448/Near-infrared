%% TracePro专用LED方向图BPDF文件生成器（60°后强度强制为0）
% 作者：豆包编程助手
% 功能：生成轴对称LED辐射方向图的BPDF文件，直接导入TracePro

%% ===================== 1. 核心参数配置（替换为你的LED实测数据）=====================
%% 1. 输入目标角度-强度关键点（示例：替换为你的LED实测数据）
theta_key = [0, 10, 20, 30, 40, 60, 90];    % 关键角度（°）
I_key = [100, 89, 73, 35, 10, 0, 0];       % 对应强度（%）
theta_cutoff = 60;                          % 截止角度（>60°强度强制为0）
output_bpdf_path = 'LED_12771.bpdf';  % 输出BPDF文件路径

%% ===================== 2. 生成连续角度-强度数据 =====================
% 生成0°~180°连续角度（步长0.5°，兼顾精度和效率）
theta_range = 0:0.5:180;

% 三次样条插值生成平滑强度曲线（匹配实测关键点）
I_theta = interp1(theta_key, I_key, theta_range, 'cubic');

% 强制处理：截止角度后强度为0 + 剔除负强度（物理意义约束）
I_theta(theta_range > theta_cutoff) = 0;
I_theta(I_theta < 0) = 0;

% 归一化强度到0~1（TracePro BPDF要求）
I_theta_normalized = I_theta / max(I_theta(:));

%% ===================== 3. 写入TracePro标准BPDF文件 =====================
% BPDF文件格式说明：TracePro官方轴对称（Phi方向1个点）格式
fid = fopen(output_bpdf_path, 'w');
if fid == -1
    error('文件写入失败，请检查路径是否合法：%s', output_bpdf_path);
end

% 写入BPDF文件头（固定格式，TracePro必选）
fprintf(fid, 'BPDF Version 1.0\n');
fprintf(fid, 'Type = Angular\n');               % 类型：角度分布
fprintf(fid, 'Coordinate System = Spherical\n');% 坐标系：球坐标
fprintf(fid, 'Theta Min = 0.0\n');              % 极角最小值
fprintf(fid, 'Theta Max = 180.0\n');            % 极角最大值
fprintf(fid, 'Phi Min = 0.0\n');                % 方位角最小值
fprintf(fid, 'Phi Max = 360.0\n');              % 方位角最大值
fprintf(fid, 'Theta Points = %d\n', length(theta_range));  % 极角点数
fprintf(fid, 'Phi Points = 1\n');               % 方位角点数（轴对称仅需1个）
fprintf(fid, 'Data:\n');                        % 数据区开始标记

% 写入归一化后的强度数据（按Theta顺序）
for i = 1:length(I_theta_normalized)
    fprintf(fid, '%.8f\n', I_theta_normalized(i));  % 高精度输出，避免误差
end

fclose(fid);

%% ===================== 4. 验证与提示 =====================
% 绘图验证方向图（可选，直观检查）
figure('Color','white');
plot(theta_range, I_theta, 'b-', 'LineWidth', 1.8);
hold on;
scatter(theta_key, I_key, 100, 'r', 'filled', 'MarkerEdgeColor','k');
vline(theta_cutoff, 'r--', 'LineWidth', 1.2);  % 绘制截止角度线
xlabel('极角 (°)','FontSize',12);
ylabel('相对辐射强度 (%)','FontSize',12);
title(['LED方向图（截止角度：', num2str(theta_cutoff), '°）'],'FontSize',14);
xlim([0, 120]);  % 聚焦有效辐射范围
ylim([0, 105]);
grid on;
legend('拟合曲线','实测关键点','截止角度','Location','southwest');

% 输出完成提示
disp(['✅ BPDF文件生成成功：', output_bpdf_path]);
disp(['📌 关键参数：']);
disp(['   - 截止角度：', num2str(theta_cutoff), '°（>该角度强度为0）']);
disp(['   - 极角点数：', num2str(length(theta_range)), '（步长0.5°）']);
disp(['   - 归一化最大值：', num2str(max(I_theta_normalized))]);

%% ===================== 辅助函数：绘制垂直线 =====================
function vline(x, varargin)
    xlim = get(gca, 'XLim');
    ylim = get(gca, 'YLim');
    plot([x, x], ylim, varargin{:});
    set(gca, 'XLim', xlim, 'YLim', ylim);
end