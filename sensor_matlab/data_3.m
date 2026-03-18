%refer文件的后半数据减去measure的前半数据  /  refer
%refer文件的前半数据减去measure的后半数据  /  refer

% 文件路径设置（请根据实际情况修改）
ref_file_path = 'D:\Desktop\sensor_data\refer_26.36.txt';
meas_file_path = 'D:\Desktop\sensor_data\measure_26.36.txt';
output_file_path = 'D:\Desktop\sensor_matlab\process_output\normalized_difference_output26.36.txt';

% 检查文件是否存在
if ~exist(ref_file_path, 'file')
    error('参考文件不存在: %s', ref_file_path);
end

if ~exist(meas_file_path, 'file')
    error('测量文件不存在: %s', meas_file_path);
end

% 读取参考文件
fid_ref = fopen(ref_file_path, 'r');
if fid_ref == -1
    error('无法打开参考文件: %s', ref_file_path);
end
ref_data = textscan(fid_ref, '%f', 'HeaderLines', 8); % 跳过前8行
fclose(fid_ref);

if isempty(ref_data{1})
    error('参考文件没有数据或格式不正确: %s', ref_file_path);
end
ref_values = ref_data{1};

% 读取测量文件
fid_meas = fopen(meas_file_path, 'r');
if fid_meas == -1
    error('无法打开测量文件: %s', meas_file_path);
end
meas_data = textscan(fid_meas, '%f', 'HeaderLines', 8); % 跳过前8行
fclose(fid_meas);

if isempty(meas_data{1})
    error('测量文件没有数据或格式不正确: %s', meas_file_path);
end
meas_values = meas_data{1};

% 显示文件信息
disp(['参考文件数据数量: ', num2str(length(ref_values))]);
disp(['测量文件数据数量: ', num2str(length(meas_values))]);

% 检查数据长度是否一致
if length(ref_values) ~= length(meas_values)
    error('两个文件的数据数量不一致，无法计算差值。');
end

n = length(ref_values);
half_point = floor(n/2); % 计算中点位置

% 判断数据个数是否为奇数
is_odd = mod(n, 2) == 1;

% 分割数据
if is_odd
    % 奇数情况：前后部分 + 中间点
    ref_first_half = ref_values(1:half_point);
    ref_second_half = ref_values(half_point+2:end);
    
    meas_first_half = meas_values(1:half_point);
    meas_second_half = meas_values(half_point+2:end);
else
    % 偶数情况：只有前后部分
    ref_first_half = ref_values(1:half_point);
    ref_second_half = ref_values(half_point+1:end);
    
    meas_first_half = meas_values(1:half_point);
    meas_second_half = meas_values(half_point+1:end);
end

% 确保数据长度匹配
min_len1 = min(length(ref_second_half), length(meas_first_half));
min_len2 = min(length(ref_first_half), length(meas_second_half));

ref_second_half = ref_second_half(1:min_len1);
meas_first_half = meas_first_half(1:min_len1);
ref_first_half = ref_first_half(1:min_len2);
meas_second_half = meas_second_half(1:min_len2);

% 计算差值并除以对应的refer数据
% 1. refer后半 - measure前半，然后除以refer后半
diff1_raw = ref_second_half - meas_first_half;
normalized_diff1 = diff1_raw ./ ref_second_half;

% 2. refer前半 - measure后半，然后除以refer前半
diff2_raw = ref_first_half - meas_second_half;
normalized_diff2 = diff2_raw ./ ref_first_half;

% 计算平均值
avg_normalized_diff1 = mean(normalized_diff1);  % 后半平均值
avg_normalized_diff2 = mean(normalized_diff2);  % 前半平均值

% 计算总平均值（所有吸光度数据的平均值）
all_normalized_diff = [normalized_diff1; normalized_diff2];
avg_normalized_total = mean(all_normalized_diff);  % 总平均值

% 输出结果到文件
fid_out = fopen(output_file_path, 'w');
if fid_out == -1
    error('无法创建输出文件: %s', output_file_path);
end

fprintf(fid_out, '# 吸光度分析结果 (差值 / refer值)\n');
fprintf(fid_out, '# 参考文件: %s\n', ref_file_path);
fprintf(fid_out, '# 测量文件: %s\n', meas_file_path);
fprintf(fid_out, '# 数据总数: %d\n', n);
fprintf(fid_out, '# 分割点位置: %d\n', half_point);
fprintf(fid_out, '# 数据个数是否为奇数: %s\n\n', string(is_odd));

% 输出平均值
fprintf(fid_out, '\n# 平均值统计\n');
fprintf(fid_out, '前半平均值: %.6f\n', avg_normalized_diff2);
fprintf(fid_out, '后半平均值: %.6f\n', avg_normalized_diff1);
fprintf(fid_out, '总平均值: %.6f\n', avg_normalized_total);

fprintf(fid_out, '\n# 平均值统计(百分比)\n');
fprintf(fid_out, '前半平均值: %.4f%%\n', avg_normalized_diff2 * 100);
fprintf(fid_out, '后半平均值: %.4f%%\n', avg_normalized_diff1 * 100);
fprintf(fid_out, '总平均值: %.4f%%\n', avg_normalized_total * 100);

% 输出前半和后半的吸光度值
fprintf(fid_out, '前半吸光度值:\n');
for i = 1:length(normalized_diff2)
    fprintf(fid_out, '%.6f\n', normalized_diff2(i));
end

fprintf(fid_out, '\n后半吸光度值:\n');
for i = 1:length(normalized_diff1)
    fprintf(fid_out, '%.6f\n', normalized_diff1(i));
end

fclose(fid_out);

% 在命令窗口显示结果
disp('=== 吸光度分析结果 ===');
disp(['数据总数: ', num2str(n)]);
disp(['分割点位置: ', num2str(half_point)]);
disp(['数据个数是否为奇数: ', string(is_odd)]);
disp('---');
disp(['前半数据数量: ', num2str(length(normalized_diff2))]);
disp(['后半数据数量: ', num2str(length(normalized_diff1))]);
disp(['前半平均值: ', num2str(avg_normalized_diff2), ' (', num2str(avg_normalized_diff2*100), '%)']);
disp(['后半平均值: ', num2str(avg_normalized_diff1), ' (', num2str(avg_normalized_diff1*100), '%)']);
disp(['总平均值: ', num2str(avg_normalized_total), ' (', num2str(avg_normalized_total*100), '%)']);
disp('---');
disp(['结果已保存至: ', output_file_path]);

% 显示文件保存成功信息
fprintf('\n文件保存成功！\n');
fprintf('输出文件: %s\n', output_file_path);