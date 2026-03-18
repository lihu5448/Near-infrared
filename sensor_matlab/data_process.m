function protocolData = parseVoltageProtocol()
    % 解析电压数据协议 - 处理十六进制字符串格式
    % 协议格式: 
    % [0x5A] [0xA5] [TYPE] [DATA0] [DATA1] [DATA2] [DATA3] [CHECKSUM] [0x0D] [0x0A]
    
    % ==================== 全局路径设置 ====================
    DATA_FOLDER = 'D:\Desktop\sensor_data\';
    OUTPUT_FOLDER = 'D:\Desktop\sensor_matlab\process_output\';
    INPUT_FILE = '6.23_1.txt';                    % 输入数据文件
    
    % ==================== 湿度数据设置 ====================
    HUMIDITY_DATA = '6.23%';  % 湿度数据，可以根据需要修改
    % ==================== 湿度设置结束 ====================
    
    % 根据湿度值动态生成输出文件名
    humidity_value = strrep(HUMIDITY_DATA, '%', '');  % 去除百分号
    MEASURE_OUTPUT_FILE = sprintf('measure_%s.txt', humidity_value);  % 测量光输出文件
    REFER_OUTPUT_FILE = sprintf('refer_%s.txt', humidity_value);      % 参考光输出文件
    
    % 构建完整文件路径
    inputFilePath = fullfile(DATA_FOLDER, INPUT_FILE);
    measureFilePath = fullfile(OUTPUT_FOLDER, MEASURE_OUTPUT_FILE);
    referFilePath = fullfile(OUTPUT_FOLDER, REFER_OUTPUT_FILE);
    % ==================== 路径设置结束 ====================
    
    % 显示路径信息
    fprintf('=== 文件路径设置 ===\n');
    fprintf('输入文件: %s\n', inputFilePath);
    fprintf('测量光输出: %s\n', measureFilePath);
    fprintf('参考光输出: %s\n', referFilePath);
    fprintf('湿度数据: %s\n', HUMIDITY_DATA);
    fprintf('========================\n\n');
    
    % 检查文件是否存在
    if ~exist(inputFilePath, 'file')
        error('文件不存在: %s', inputFilePath);
    end
    
    % 读取文件内容（作为文本读取）
    fprintf('正在读取文件: %s\n', inputFilePath);
    
    try
        % 以文本方式读取文件
        fileID = fopen(inputFilePath, 'r');
        if fileID == -1
            error('无法打开文件');
        end
        
        % 读取整个文件内容
        textContent = fscanf(fileID, '%c');
        fclose(fileID);
        
        fprintf('文件读取成功，文本长度: %d 字符\n', length(textContent));
        
    catch ME
        error('文件读取失败: %s', ME.message);
    end
    
    % 将十六进制字符串转换为二进制数据
    rawData = hexStringToBinary(textContent);
    
    % 协议解析
    protocolData = parseVoltagePackets(rawData);
    
    % 计算统计信息
    protocolData = calculateStatistics(protocolData);
    
    % 显示解析结果
    displayVoltageResults(protocolData);
    
    % 绘制数据图形
    plotVoltageData(protocolData);
    
    % 保存数据到文件（传入文件路径和湿度数据）
    saveVoltageDataToFiles(protocolData, measureFilePath, referFilePath, HUMIDITY_DATA);
end

function rawData = hexStringToBinary(textContent)
    % 将十六进制字符串转换为二进制数据
    
    % 去除空格、换行等空白字符
    cleanText = regexprep(textContent, '\s', '');
    
    % 检查字符串长度是否为偶数（十六进制字节对）
    if mod(length(cleanText), 2) ~= 0
        warning('十六进制字符串长度不是偶数，可能数据不完整');
        % 截断到最后完整的字节
        cleanText = cleanText(1:end-1);
    end
    
    % 将十六进制字符串转换为二进制数据
    dataLength = length(cleanText) / 2;
    rawData = zeros(1, dataLength, 'uint8');
    
    for i = 1:dataLength
        hexByte = cleanText((i-1)*2 + 1 : i*2);
        rawData(i) = hex2dec(hexByte);
    end
    
    fprintf('十六进制转换完成，得到 %d 字节二进制数据\n', dataLength);
    
    % 显示原始十六进制数据（前100个字节）
    if dataLength > 0
        fprintf('前100字节十六进制数据: ');
        displayLength = min(100, dataLength);
        for i = 1:displayLength
            fprintf('%02X ', rawData(i));
        end
        if dataLength > displayLength
            fprintf('...');
        end
        fprintf('\n');
    end
end

function protocolData = parseVoltagePackets(rawData)
    % 解析电压数据包 - 完整版本
    % 数据包固定10字节: 0x5A 0xA5 + 1类型 + 4数据 + 1校验和 + 0x0D 0x0A
    
    START_BYTE1 = hex2dec('5A');  % 0x5A
    START_BYTE2 = hex2dec('A5');  % 0xA5
    END_BYTE1 = hex2dec('0D');    % 0x0D
    END_BYTE2 = hex2dec('0A');    % 0x0A
    PACKET_SIZE = 10;             % 完整数据包大小
    
    % 数据类型定义
    TYPE_NOTHING = hex2dec('00');  % 0x00 - 啥也不是
    TYPE_MEASURE = hex2dec('01');  % 0x01 - 测量光
    TYPE_REFER = hex2dec('02');    % 0x02 - 参考光
    
    % 无效数据值定义
    INVALID_DATA_1 = uint8([0x00, 0x00, 0x00, 0x00]);  % 0x00000000
    INVALID_DATA_2 = uint8([0xFF, 0xFF, 0xFF, 0xFF]);  % 0xFFFFFFFF
    
    protocolData = struct();
    protocolData.packets = {};
    protocolData.validPacketCount = 0;
    protocolData.corruptedPackets = 0;
    protocolData.invalidDataPackets = 0;  % 新增：无效数据包计数
    protocolData.voltageValues = [];
    protocolData.packetTypes = [];
    
    % 按类型统计
    protocolData.measureCount = 0;
    protocolData.referCount = 0;
    protocolData.nothingCount = 0;
    
    % 按类型存储电压值
    protocolData.measureVoltages = [];
    protocolData.referVoltages = [];
    
    i = 1;
    packetCount = 0;
    corruptedCount = 0;
    invalidDataCount = 0;  % 新增：无效数据计数
    voltageValues = [];
    packetTypes = [];
    
    measureCount = 0;
    referCount = 0;
    nothingCount = 0;
    
    measureVoltages = [];
    referVoltages = [];
    
    while i <= length(rawData) - PACKET_SIZE + 1
        % 检查起始位和终止位
        if rawData(i) == START_BYTE1 && ...
           rawData(i+1) == START_BYTE2 && ...
           rawData(i+8) == END_BYTE1 && ...
           rawData(i+9) == END_BYTE2
            
            % 提取数据包
            packet = rawData(i:i+PACKET_SIZE-1);
            
            % 提取数据类型 (第3字节)
            dataType = packet(3);
            
            % 提取数据字节 (索引4-7，对应SendBuf[3]-SendBuf[6])
            dataBytes = packet(4:7);  % 4个数据字节
            
            % 计算校验和 (SendBuf[3] + SendBuf[4] + SendBuf[5] + SendBuf[6])
            % 对应 packet(4) + packet(5) + packet(6) + packet(7)
            receivedChecksum = packet(8);
            calculatedChecksum = mod(sum(packet(4:7)), 256);  % 第4-7字节的和取低8位
            
            % 校验和检查
            checksumValid = (receivedChecksum == calculatedChecksum);
            
            % 检查是否为无效数据值 (0x00000000 或 0xFFFFFFFF)
            isInvalidData = isequal(dataBytes, INVALID_DATA_1) || isequal(dataBytes, INVALID_DATA_2);
            
            % 解析32位有符号整数（小端格式）
            % 对应: SendBuf[3]=(uint8_t)V (最低字节)
            %       SendBuf[6]=(uint8_t)(V>>24) (最高字节)
            voltageInt = typecast(uint8([packet(4), packet(5), packet(6), packet(7)]), 'int32');
            voltage = double(voltageInt) / 1000000.0;  % 转换为实际电压值
            
            packetCount = packetCount + 1;
            
            % 根据数据类型统计和存储（只存储有效数据）
            switch dataType
                case TYPE_MEASURE
                    measureCount = measureCount + 1;
                    typeStr = '测量光';
                    if ~isInvalidData && checksumValid
                        measureVoltages(end+1) = voltage;
                    end
                case TYPE_REFER
                    referCount = referCount + 1;
                    typeStr = '参考光';
                    if ~isInvalidData && checksumValid
                        referVoltages(end+1) = voltage;
                    end
                case TYPE_NOTHING
                    nothingCount = nothingCount + 1;
                    typeStr = '无类型';
                otherwise
                    typeStr = '未知类型';
            end
            
            % 存储数据包信息
            protocolData.packets{packetCount} = struct();
            protocolData.packets{packetCount}.rawData = packet;
            protocolData.packets{packetCount}.startIndex = i;
            protocolData.packets{packetCount}.dataType = dataType;
            protocolData.packets{packetCount}.dataTypeStr = typeStr;
            protocolData.packets{packetCount}.dataBytes = dataBytes;
            protocolData.packets{packetCount}.receivedChecksum = receivedChecksum;
            protocolData.packets{packetCount}.calculatedChecksum = calculatedChecksum;
            protocolData.packets{packetCount}.checksumValid = checksumValid;
            protocolData.packets{packetCount}.isInvalidData = isInvalidData;  % 新增：无效数据标志
            protocolData.packets{packetCount}.voltageInt = voltageInt;
            protocolData.packets{packetCount}.voltage = voltage;
            protocolData.packets{packetCount}.dataValid = checksumValid && ~isInvalidData;  % 新增：总体有效性标志
            
            % 收集电压值和类型（只收集有效数据）
            if checksumValid && ~isInvalidData
                voltageValues(end+1) = voltage;
                packetTypes(end+1) = dataType;
            end
            
            if ~checksumValid
                corruptedCount = corruptedCount + 1;
            end
            
            if isInvalidData
                invalidDataCount = invalidDataCount + 1;
            end
            
            % 移动到下一个数据包
            i = i + PACKET_SIZE;
        else
            i = i + 1;
        end
    end
    
    protocolData.validPacketCount = packetCount;
    protocolData.corruptedPackets = corruptedCount;
    protocolData.invalidDataPackets = invalidDataCount;  % 存储无效数据包计数
    protocolData.voltageValues = voltageValues;
    protocolData.packetTypes = packetTypes;
    protocolData.measureCount = measureCount;
    protocolData.referCount = referCount;
    protocolData.nothingCount = nothingCount;
    protocolData.measureVoltages = measureVoltages;
    protocolData.referVoltages = referVoltages;
    
    fprintf('协议解析完成:\n');
    fprintf('  找到 %d 个有效数据包\n', packetCount);
    fprintf('  校验和错误: %d 个数据包\n', corruptedCount);
    fprintf('  无效数据值: %d 个数据包 (0x00000000 或 0xFFFFFFFF)\n', invalidDataCount);
    fprintf('  数据类型统计: 测量光=%d, 参考光=%d, 无类型=%d\n', ...
        measureCount, referCount, nothingCount);
end

function protocolData = calculateStatistics(protocolData)
    % 计算测量光和参考光的统计信息
    
    % 计算测量光统计信息
    if ~isempty(protocolData.measureVoltages)
        measure_min = min(protocolData.measureVoltages);
        measure_max = max(protocolData.measureVoltages);
        measure_mean = mean(protocolData.measureVoltages);
        measure_std = std(protocolData.measureVoltages);
    else
        measure_min = NaN;
        measure_max = NaN;
        measure_mean = NaN;
        measure_std = NaN;
    end
    
    % 计算参考光统计信息
    if ~isempty(protocolData.referVoltages)
        refer_min = min(protocolData.referVoltages);
        refer_max = max(protocolData.referVoltages);
        refer_mean = mean(protocolData.referVoltages);
        refer_std = std(protocolData.referVoltages);
    else
        refer_min = NaN;
        refer_max = NaN;
        refer_mean = NaN;
        refer_std = NaN;
    end
    
    % 存储统计信息到protocolData
    protocolData.measure_stats = struct('min', measure_min, 'max', measure_max, 'mean', measure_mean, 'std', measure_std);
    protocolData.refer_stats = struct('min', refer_min, 'max', refer_max, 'mean', refer_mean, 'std', refer_std);
    
    return;
end

function displayVoltageResults(protocolData)
    % 显示电压数据解析结果
    
    fprintf('\n=== 电压数据协议解析结果 ===\n');
    fprintf('有效数据包数量: %d\n', protocolData.validPacketCount);
    fprintf('校验和错误数据包: %d\n', protocolData.corruptedPackets);
    fprintf('无效数据值数据包: %d (0x00000000 或 0xFFFFFFFF)\n', protocolData.invalidDataPackets);
    fprintf('有效数据包数量: %d\n', protocolData.validPacketCount - protocolData.corruptedPackets - protocolData.invalidDataPackets);
    fprintf('数据类型统计:\n');
    fprintf('  测量光 (0x01): %d 个\n', protocolData.measureCount);
    fprintf('  参考光 (0x02): %d 个\n', protocolData.referCount);
    fprintf('  无类型 (0x00): %d 个\n', protocolData.nothingCount);
    
    % 显示测量光统计信息
    if ~isempty(protocolData.measureVoltages)
        fprintf('\n=== 测量光统计信息 (排除无效数据) ===\n');
        fprintf('最小值: %.6f V\n', protocolData.measure_stats.min);
        fprintf('最大值: %.6f V\n', protocolData.measure_stats.max);
        fprintf('平均值: %.6f V\n', protocolData.measure_stats.mean);
        fprintf('标准差: %.6f V\n', protocolData.measure_stats.std);
        fprintf('有效数据数量: %d\n', length(protocolData.measureVoltages));
    else
        fprintf('\n=== 测量光统计信息 ===\n');
        fprintf('无有效的测量光数据\n');
    end
    
    % 显示参考光统计信息
    if ~isempty(protocolData.referVoltages)
        fprintf('\n=== 参考光统计信息 (排除无效数据) ===\n');
        fprintf('最小值: %.6f V\n', protocolData.refer_stats.min);
        fprintf('最大值: %.6f V\n', protocolData.refer_stats.max);
        fprintf('平均值: %.6f V\n', protocolData.refer_stats.mean);
        fprintf('标准差: %.6f V\n', protocolData.refer_stats.std);
        fprintf('有效数据数量: %d\n', length(protocolData.referVoltages));
    else
        fprintf('\n=== 参考光统计信息 ===\n');
        fprintf('无有效的参考光数据\n');
    end
    
    if protocolData.validPacketCount > 0
        fprintf('\n数据包详细信息:\n');
        fprintf('%-6s %-8s %-30s %-12s %-15s %-12s %s\n', ...
            '序号', '类型', '原始数据(十六进制)', '整数值', '电压值(V)', '校验和', '状态');
        fprintf('%s\n', repmat('-', 1, 120));
        
        for i = 1:min(20, protocolData.validPacketCount)  % 只显示前20个包
            packet = protocolData.packets{i};
            
            % 格式化原始数据
            hexData = sprintf('%02X ', packet.rawData);
            hexData = strtrim(hexData);
            
            % 高亮显示数据类型字节
            hexParts = split(hexData, ' ');
            if length(hexParts) >= 3
                hexParts{3} = ['[' hexParts{3} ']'];  % 用方括号标记数据类型字节
                hexData = strjoin(hexParts, ' ');
            end
            
            % 显示状态
            if packet.checksumValid && ~packet.isInvalidData
                status = '✓ 有效';
            elseif ~packet.checksumValid
                status = '✗ 校验和错误';
            elseif packet.isInvalidData
                status = '✗ 无效数据值';
            else
                status = '✗ 其他错误';
            end
            
            fprintf('%-6d %-8s %-30s %-12d %-15.6f 0x%02X/0x%02X %s\n', ...
                i, packet.dataTypeStr, hexData, packet.voltageInt, packet.voltage, ...
                packet.receivedChecksum, packet.calculatedChecksum, status);
        end
        
        if protocolData.validPacketCount > 20
            fprintf('... (仅显示前20个数据包)\n');
        end
    else
        fprintf('未找到有效数据包！\n');
    end
end

function plotVoltageData(protocolData)
    % 绘制电压数据图形
    if protocolData.validPacketCount > 1
        figure('Position', [100, 100, 1200, 800]);
        
        % 按数据类型分离数据（只显示校验和正确且数据有效的）
        measureVoltages = [];
        measureIndices = [];
        referVoltages = [];
        referIndices = [];
        nothingVoltages = [];
        nothingIndices = [];
        
        validPacketCount = 0;
        
        for i = 1:protocolData.validPacketCount
            packet = protocolData.packets{i};
            if packet.checksumValid && ~packet.isInvalidData  % 只显示校验和正确且数据有效的
                validPacketCount = validPacketCount + 1;
                switch packet.dataType
                    case hex2dec('01')  % 测量光
                        measureVoltages(end+1) = packet.voltage;
                        measureIndices(end+1) = validPacketCount;
                    case hex2dec('02')  % 参考光
                        referVoltages(end+1) = packet.voltage;
                        referIndices(end+1) = validPacketCount;
                    case hex2dec('00')  % 无类型
                        nothingVoltages(end+1) = packet.voltage;
                        nothingIndices(end+1) = validPacketCount;
                end
            end
        end
        
        % 绘制所有数据类型的数据
        subplot(2,2,1);
        hold on;
        if ~isempty(measureIndices)
            plot(measureIndices, measureVoltages, 'go-', 'LineWidth', 1.5, 'MarkerSize', 4, 'DisplayName', '测量光');
        end
        if ~isempty(referIndices)
            plot(referIndices, referVoltages, 'bo-', 'LineWidth', 1.5, 'MarkerSize', 4, 'DisplayName', '参考光');
        end
        if ~isempty(nothingIndices)
            plot(nothingIndices, nothingVoltages, 'ro-', 'LineWidth', 1, 'MarkerSize', 3, 'DisplayName', '无类型');
        end
        title('按数据类型分类的电压数据 (校验和正确且数据有效)');
        xlabel('有效数据包序号');
        ylabel('电压值 (V)');
        legend('show');
        grid on;
        hold off;
        
        % 绘制测量光数据
        if length(measureVoltages) > 1
            subplot(2,2,2);
            plot(measureIndices, measureVoltages, 'go-', 'LineWidth', 1.5, 'MarkerSize', 4);
            title('测量光电压数据 (有效数据)');
            xlabel('有效数据包序号');
            ylabel('电压值 (V)');
            grid on;
        else
            subplot(2,2,2);
            text(0.5, 0.5, '无有效的测量光数据', 'HorizontalAlignment', 'center', 'FontSize', 14);
            title('测量光电压数据');
            axis off;
        end
        
        % 绘制参考光数据
        if length(referVoltages) > 1
            subplot(2,2,3);
            plot(referIndices, referVoltages, 'bo-', 'LineWidth', 1.5, 'MarkerSize', 4);
            title('参考光电压数据 (有效数据)');
            xlabel('有效数据包序号');
            ylabel('电压值 (V)');
            grid on;
        else
            subplot(2,2,3);
            text(0.5, 0.5, '无有效的参考光数据', 'HorizontalAlignment', 'center', 'FontSize', 14);
            title('参考光电压数据');
            axis off;
        end
        
        % 绘制数据分布直方图
        subplot(2,2,4);
        hold on;
        if ~isempty(measureVoltages)
            histogram(measureVoltages, 20, 'FaceColor', 'green', 'FaceAlpha', 0.7, 'DisplayName', '测量光');
        end
        if ~isempty(referVoltages)
            histogram(referVoltages, 20, 'FaceColor', 'blue', 'FaceAlpha', 0.7, 'DisplayName', '参考光');
        end
        if isempty(measureVoltages) && isempty(referVoltages)
            text(0.5, 0.5, '无有效数据', 'HorizontalAlignment', 'center', 'FontSize', 14);
        end
        title('电压数据分布 (按类型, 仅有效数据)');
        xlabel('电压值 (V)');
        ylabel('频次');
        legend('show');
        grid on;
        hold off;
        
        % 添加数据质量统计
        sgtitle(sprintf('电压数据分析 (总计: %d 包, 有效: %d, 测量光: %d, 参考光: %d, 无类型: %d)', ...
            protocolData.validPacketCount, validPacketCount, protocolData.measureCount, protocolData.referCount, protocolData.nothingCount));
        
    else
        fprintf('有效数据不足，无法绘制图形\n');
    end
end

function saveVoltageDataToFiles(protocolData, measureFilePath, referFilePath, humidityData)
    % 根据数据类型保存电压值到不同文件，如果没有数据则不创建文件
    
    measureCount = 0;
    referCount = 0;
    
    % 统计有效数据数量（校验和正确且数据有效）
    for i = 1:protocolData.validPacketCount
        packet = protocolData.packets{i};
        if packet.checksumValid && ~packet.isInvalidData
            switch packet.dataType
                case hex2dec('01')  % 测量光
                    measureCount = measureCount + 1;
                case hex2dec('02')  % 参考光
                    referCount = referCount + 1;
            end
        end
    end
    
    % 保存测量光数据（如果有数据）
    if measureCount > 0
        measureFileID = fopen(measureFilePath, 'w');
        if measureFileID == -1
            error('无法创建测量光数据文件: %s', measureFilePath);
        end
        
        % 在文件开头写入湿度值和统计信息
        fprintf(measureFileID, '# Humidity: %s\n', humidityData);
        if ~isempty(protocolData.measureVoltages)
            fprintf(measureFileID, '# Measurement Light Statistics:\n');
            fprintf(measureFileID, '# Min: %.6f V\n', protocolData.measure_stats.min);
            fprintf(measureFileID, '# Max: %.6f V\n', protocolData.measure_stats.max);
            fprintf(measureFileID, '# Mean: %.6f V\n', protocolData.measure_stats.mean);
            fprintf(measureFileID, '# Std: %.6f V\n', protocolData.measure_stats.std);
            fprintf(measureFileID, '# Data Count: %d\n', measureCount);
            fprintf(measureFileID, '# Valid Data Count: %d (after filtering invalid values)\n', length(protocolData.measureVoltages));
            fprintf(measureFileID, '# \n');
        end
        
        % 写入测量光数据（只写入有效数据）
        for i = 1:protocolData.validPacketCount
            packet = protocolData.packets{i};
            if packet.checksumValid && ~packet.isInvalidData && packet.dataType == hex2dec('01')
                fprintf(measureFileID, '%.6f\n', packet.voltage);
            end
        end
        fclose(measureFileID);
        fprintf('测量光数据保存到: %s (%d 条有效数据)\n', measureFilePath, measureCount);
        
        % 显示测量光数据预览
        fprintf('测量光数据前10条:\n');
        previewFileContent(measureFilePath, 10);
    else
        fprintf('无有效的测量光数据，不创建文件: %s\n', measureFilePath);
    end
    
    % 保存参考光数据（如果有数据）
    if referCount > 0
        referFileID = fopen(referFilePath, 'w');
        if referFileID == -1
            error('无法创建参考光数据文件: %s', referFilePath);
        end
        
        % 在文件开头写入湿度值和统计信息
        fprintf(referFileID, '# Humidity: %s\n', humidityData);
        if ~isempty(protocolData.referVoltages)
            fprintf(referFileID, '# Reference Light Statistics:\n');
            fprintf(referFileID, '# Min: %.6f V\n', protocolData.refer_stats.min);
            fprintf(referFileID, '# Max: %.6f V\n', protocolData.refer_stats.max);
            fprintf(referFileID, '# Mean: %.6f V\n', protocolData.refer_stats.mean);
            fprintf(referFileID, '# Std: %.6f V\n', protocolData.refer_stats.std);
            fprintf(referFileID, '# Data Count: %d\n', referCount);
            fprintf(referFileID, '# Valid Data Count: %d (after filtering invalid values)\n', length(protocolData.referVoltages));
            fprintf(referFileID, '# \n');
        end
        
        % 写入参考光数据（只写入有效数据）
        for i = 1:protocolData.validPacketCount
            packet = protocolData.packets{i};
            if packet.checksumValid && ~packet.isInvalidData && packet.dataType == hex2dec('02')
                fprintf(referFileID, '%.6f\n', packet.voltage);
            end
        end
        fclose(referFileID);
        fprintf('参考光数据保存到: %s (%d 条有效数据)\n', referFilePath, referCount);
        
        % 显示参考光数据预览
        fprintf('参考光数据前10条:\n');
        previewFileContent(referFilePath, 10);
    else
        fprintf('无有效的参考光数据，不创建文件: %s\n', referFilePath);
    end
    
    fprintf('\n数据保存完成:\n');
    fprintf('  测量光有效数据: %d 条\n', measureCount);
    fprintf('  参考光有效数据: %d 条\n', referCount);
    fprintf('  过滤掉的无效数据: %d 条 (校验和错误或数据值为0x00000000/0xFFFFFFFF)\n', ...
        protocolData.corruptedPackets + protocolData.invalidDataPackets);
    
    % 如果两个文件都没有创建，给出提示
    if measureCount == 0 && referCount == 0
        fprintf('注意: 没有找到任何有效的测量光或参考光数据，未创建任何输出文件。\n');
    end
end

function previewFileContent(filePath, maxLines)
    % 预览文件内容
    if exist(filePath, 'file')
        fileID = fopen(filePath, 'r');
        lineCount = 0;
        while ~feof(fileID) && lineCount < maxLines
            line = fgetl(fileID);
            if ischar(line)
                fprintf('  %s\n', line);
                lineCount = lineCount + 1;
            end
        end
        fclose(fileID);
        
        % 如果文件行数多于预览行数，显示提示
        if lineCount == maxLines
            % 检查是否还有更多行
            fileID = fopen(filePath, 'r');
            totalLines = 0;
            while ~feof(fileID)
                fgetl(fileID);
                totalLines = totalLines + 1;
            end
            fclose(fileID);
            
            if totalLines > maxLines
                fprintf('  ... (还有 %d 条数据)\n', totalLines - maxLines);
            end
        end
    end
end